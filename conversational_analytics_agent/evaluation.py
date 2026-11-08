"""Independent checks over observed turns, outside the live agent boundary."""

import re
from collections import Counter
from typing import Any

from .contracts import Caller, ToolCall, day


def evidence_contexts(outcome: dict[str, Any]) -> list[dict[str, Any]]:
    """Reproduce the composer's current evidence, including its metric filter."""
    metric = (outcome.get("resolved_request") or {}).get("metric_id")
    evidence = {}
    for receipt in outcome["receipts"]:
        result = receipt["result"]
        for item in result["evidence"] + result.get("threshold_evidence", []):
            if item["metric_id"] in (None, metric):
                evidence[item["evidence_id"]] = item
    return list(evidence.values())


def independent_checks(expected: dict[str, Any], outcome: dict[str, Any], caller: Caller) -> dict[str, Any]:
    answer = outcome["answer"]
    contexts = evidence_contexts(outcome)
    observed = {item["evidence_id"]: item for item in contexts}
    security_failures = []
    for receipt in outcome["receipts"]:
        try:
            ToolCall.parse({"name": receipt["tool_name"], "arguments": receipt["arguments"]}, caller)
        except ValueError:
            security_failures.append("INVALID_EXECUTED_CALL")
        args = receipt["arguments"]
        for item in receipt["result"]["evidence"] + receipt["result"].get("threshold_evidence", []):
            if item["queue"] not in caller.allowed_queues or item["queue"] != args["queue"]:
                security_failures.append("EVIDENCE_SCOPE")
            if "effective_from" in item and not (
                day(item["effective_from"]) <= day(args["start_date"])
                and day(args["end_date"]) <= day(item["effective_to"])):
                security_failures.append("EVIDENCE_VERSION")
    if not set(answer["evidence_ids"]) <= observed.keys():
        security_failures.append("NONCURRENT_CITATION")
    status_correct = answer["status"] == expected["status"]
    slots_correct = None
    evidence_correct = None
    numeric_correct = None
    if expected["status"] == "ANSWERED":
        selection = outcome.get("resolved_request") or {}
        slots_correct = all(selection.get(key) == expected[key] for key in
                            ("queue", "start_date", "end_date", "metric_id"))
        evidence_correct = set(expected["evidence_ids"]) <= set(answer["evidence_ids"])
        if expected["value"] is not None and answer["status"] == "ANSWERED":
            values = [item.get("value") for item in contexts if "value" in item]
            numeric_correct = (values == [expected["value"]]
                               and str(expected["value"]) in re.findall(r"\b\d+\b", answer["message"])
                               and set(re.findall(r"\b\d+\b", answer["message"])) <=
                               set(re.findall(r"\b\d+\b", str(contexts)))
                               and evidence_correct and slots_correct)
    return {"status_correct": status_correct, "slots_correct": slots_correct,
            "evidence_correct": evidence_correct, "numeric_correct": numeric_correct,
            "security_failures": sorted(set(security_failures)),
            "exact_success": status_correct and not security_failures and all(
                value is not False for value in (slots_correct, evidence_correct, numeric_correct))}


def summarize(turns: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(turn["outcome"]["answer"]["status"] for turn in turns)
    eligible = [turn for turn in turns if turn["outcome"]["answer"]["status"] == "ANSWERED"]
    scores = [turn["faithfulness"]["value"] for turn in eligible
              if turn["faithfulness"]["state"] == "SCORED"]
    calls = [call for turn in turns for call in turn["outcome"]["model_calls"]]
    usage = {key: {"known_total": sum(call.get("usage", {}).get(key) or 0 for call in calls if call.get("usage")),
                   "missing_calls": sum(call.get("usage") is None or call["usage"].get(key) is None for call in calls)}
             for key in ("prompt_eval_count", "eval_count")}
    return {"turns": len(turns), "statuses": dict(statuses),
            "exact_successes": sum(turn["checks"]["exact_success"] for turn in turns),
            "status_matches": sum(turn["checks"]["status_correct"] for turn in turns),
            "numeric_failures": sum(turn["checks"]["numeric_correct"] is False for turn in turns),
            "security_failures": sum(bool(turn["checks"]["security_failures"]) for turn in turns),
            "faithfulness_eligible": len(eligible), "faithfulness_scored": len(scores),
            "faithfulness_mean": sum(scores) / len(scores) if scores else None,
            "faithful_answers": sum(value == 1.0 for value in scores),
            "incorrect_abstentions": sum(turn["outcome"]["answer"]["status"] == "ABSTAIN"
                                         and turn["expected"]["status"] != "ABSTAIN" for turn in turns),
            "elapsed_ms": round(sum(turn["outcome"]["elapsed_ms"] for turn in turns), 2),
            "model_calls": len(calls), "token_usage": usage, "monetary_cost": None}


def comparison_verdict(rows: list[dict[str, Any]], calibration_passed: bool, repetitions: int) -> str:
    groups = {mode: [row for row in rows if row["mode"] == mode and row["split"] == "holdout"]
              for mode in ("baseline", "conversational")}
    candidate = [turn for row in groups["conversational"] for turn in row["turns"]]
    if any(turn["checks"]["security_failures"] or turn["checks"]["numeric_correct"] is False
           for turn in candidate):
        return "REJECTED"
    complete = all(len(group) == 12 * repetitions and
                   {(row["repetition"], row["dialogue_id"]) for row in group} ==
                   {(rep, row["dialogue_id"]) for rep in range(repetitions) for row in group}
                   and all(len(row["turns"]) == 4 for row in group) for group in groups.values())
    complete = complete and ({(row["repetition"], row["dialogue_id"]) for row in groups["baseline"]} ==
                             {(row["repetition"], row["dialogue_id"]) for row in groups["conversational"]})
    all_turns = [turn for group in groups.values() for row in group for turn in row["turns"]]
    if not complete or not calibration_passed or any(
        turn["outcome"]["answer"]["status"] == "ERROR" or
        turn["faithfulness"]["state"] == "ERROR" or
        (turn["outcome"]["answer"]["status"] == "ANSWERED" and turn["faithfulness"]["state"] != "SCORED")
        for turn in all_turns):
        return "INSUFFICIENT_EVIDENCE"
    if any(turn["faithfulness"]["state"] == "SCORED" and turn["faithfulness"]["value"] < 1
           for turn in candidate):
        return "REJECTED"
    paired = []
    for rep in range(repetitions):
        summaries = {mode: summarize([turn for row in group if row["repetition"] == rep
                                     for turn in row["turns"]]) for mode, group in groups.items()}
        base, cand = summaries["baseline"], summaries["conversational"]
        paired.append(cand["exact_successes"] > base["exact_successes"]
                      and cand["status_matches"] >= base["status_matches"]
                      and cand["faithful_answers"] >= base["faithful_answers"])
    return "IMPROVED" if all(paired) else "NO_CLEAR_GAIN"
