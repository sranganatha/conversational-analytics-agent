"""Pinned Ragas adapters. These imports belong only to the evaluation image."""

import asyncio
import math
import time

from ragas.dataset_schema import SingleTurnSample
from ragas.llms.base import InstructorBaseRagasLLM
from ragas.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall
from ragas.metrics.collections import Faithfulness, ToolCallAccuracy

from .contracts import ContractError, require
from .evaluation import evidence_contexts
from .tools import canonical


class LocalJudge(InstructorBaseRagasLLM):
    def __init__(self, model):
        self.model = model
        self.calls = []
        self.deadline = 0

    def generate(self, prompt, response_model):
        require(len(self.calls) < 2, "JUDGE_CALL_LIMIT")
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "JUDGE_TIMEOUT")
        call = {"prompt": prompt, "schema": response_model.model_json_schema(), "usage": None}
        self.calls.append(call)
        raw, usage = self.model.generate([
            {"role": "system", "content": "Evaluate only the supplied answer and context. Return the required JSON."},
            {"role": "user", "content": prompt}], call["schema"], remaining)
        call.update(output=raw, usage=usage)
        return response_model.model_validate(raw, strict=True)

    async def agenerate(self, prompt, response_model):
        return await asyncio.to_thread(self.generate, prompt, response_model)

    async def score(self, question, response, contexts):
        self.calls = []
        self.deadline = time.monotonic() + 60
        try:
            metric = Faithfulness(llm=self)
            score = (await metric.ascore(user_input=question, response=response,
                                        retrieved_contexts=contexts)).value
            require(math.isfinite(score) and 0 <= score <= 1, "JUDGE_INVALID_SCORE")
            require(len(self.calls) == 2, "JUDGE_MISSING_CLAIMS")
            claims = self.calls[0]["output"]["statements"]
            verdicts = self.calls[1]["output"]["statements"]
            require(bool(claims) and [item["statement"] for item in verdicts] == claims,
                    "JUDGE_CLAIM_MISMATCH")
            return {"state": "SCORED", "value": score, "error_code": None, "calls": self.calls}
        except Exception as exc:
            return {"state": "ERROR", "value": None,
                    "error_code": exc.code if isinstance(exc, ContractError) else "JUDGE_INVALID_RESPONSE",
                    "calls": self.calls}


async def retrieval_scores(expected, outcome):
    refs = [item for item in expected["evidence_ids"] if not item.startswith("aggregate:")]
    if not refs:
        return {"state": "NOT_APPLICABLE", "precision": None, "recall": None}
    ids = [item["evidence_id"] for receipt in outcome["receipts"]
           if receipt["tool_name"] == "search_procedures" for item in receipt["result"]["evidence"]]
    sample = SingleTurnSample(retrieved_context_ids=ids, reference_context_ids=refs)
    precision = await IDBasedContextPrecision().single_turn_ascore(sample)
    recall = await IDBasedContextRecall().single_turn_ascore(sample)
    return {"state": "SCORED" if math.isfinite(precision) else "UNDEFINED_NO_RETRIEVAL",
            "precision": precision if math.isfinite(precision) else None, "recall": recall}


async def dialogue_tools(turns):
    messages, references = [], []
    for turn in turns:
        outcome, label = turn["outcome"], turn["expected"]
        messages.append(HumanMessage(content=turn["message"]))
        # Search wording is unconstrained; only its scope/date arguments are scored.
        for attempt in outcome["tool_attempts"]:
            call = attempt["call"]
            args = {key: value for key, value in call["arguments"].items() if key != "query"}
            messages.append(AIMessage(content="", tool_calls=[ToolCall(name=call["name"], args=args)]))
            messages.append(ToolMessage(content=canonical({"outcome": attempt["outcome"]})))
        messages.append(AIMessage(content=outcome["answer"]["message"]))
        for name in turn["expected_tools"]:
            args = {key: label[key] for key in ("queue", "start_date", "end_date")}
            if name == "read_service_metrics":
                args["metric_id"] = label["metric_id"]
            references.append(ToolCall(name=name, args=args))
    return (await ToolCallAccuracy(strict_order=True).ascore(
        user_input=messages, reference_tool_calls=references)).value


async def score_faithfulness(judge, message, outcome):
    if outcome["answer"]["status"] != "ANSWERED":
        return {"state": "NOT_APPLICABLE", "value": None, "error_code": None, "calls": []}
    return await judge.score(message, outcome["answer"]["message"],
                             [canonical(item) for item in evidence_contexts(outcome)])
