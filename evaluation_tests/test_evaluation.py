import asyncio
import copy
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from conversational_analytics_agent.contracts import Caller
from conversational_analytics_agent.evaluate import run_dialogue
from conversational_analytics_agent.evaluation import comparison_verdict, independent_checks, summarize
from conversational_analytics_agent.fixtures import load_json
from conversational_analytics_agent.ragas_metrics import LocalJudge, dialogue_tools, retrieval_scores
from conversational_analytics_agent.store import SessionStore
from conversational_analytics_agent.tools import EvidenceTools


def example():
    caller = Caller.parse({"subject": "analyst", "allowed_queues": ["intake"]})
    args = {"queue": "intake", "start_date": "2026-09-01", "end_date": "2026-10-01",
            "metric_id": "first_response_breaches"}
    receipt = EvidenceTools().execute({"name": "read_service_metrics", "arguments": args}, caller)
    label = {"status": "ANSWERED", **args, "value": 120,
             "evidence_ids": ["aggregate:intake:first_response_breaches:2026-09"]}
    outcome = {"answer": {"status": "ANSWERED", "message": "Intake had 120 breaches in September 2026.",
                          "evidence_ids": label["evidence_ids"][:]}, "resolved_request": args,
               "receipts": [receipt], "tool_attempts": [{"call": {"name": "read_service_metrics", "arguments": args},
                                                          "outcome": "OK"}],
               "model_calls": [], "elapsed_ms": 10}
    return caller, label, outcome


class EvaluationTests(unittest.TestCase):
    def test_calibration_citation_identities_exist_in_supplied_context(self):
        root = Path(__file__).resolve().parent.parent
        cases = load_json(root / "config" / "judge-calibration.json")["cases"]
        self.assertEqual(len({case["id"] for case in cases}), 12)
        self.assertEqual(sum(case["supported"] is True for case in cases), 6)
        self.assertEqual(sum(case["supported"] is False for case in cases), 6)
        for case in cases:
            for evidence_id in re.findall(r"\[([^\]]+)\]", case["answer"]):
                self.assertIn(evidence_id, case["context"], case["id"])

    def test_independent_checks_reject_wrong_number_with_valid_citation(self):
        caller, label, outcome = example()
        self.assertTrue(independent_checks(label, outcome, caller)["exact_success"])
        outcome["answer"]["message"] = "Intake had 121 breaches. The denominator is 120."
        self.assertFalse(independent_checks(label, outcome, caller)["numeric_correct"])

    def test_fluent_wrong_period_and_foreign_evidence_are_rejected(self):
        caller, label, outcome = example()
        outcome["resolved_request"] = {**outcome["resolved_request"], "start_date": "2026-08-01"}
        self.assertFalse(independent_checks(label, outcome, caller)["exact_success"])
        outcome["receipts"][0]["result"]["evidence"][0]["queue"] = "review"
        self.assertIn("EVIDENCE_SCOPE", independent_checks(label, outcome, caller)["security_failures"])

    def test_stale_evidence_and_noncurrent_citation_are_failures(self):
        caller, label, outcome = example()
        outcome["answer"]["evidence_ids"] += ["unseen"]
        outcome["receipts"][0]["result"]["threshold_evidence"][0]["effective_to"] = "2026-09-15"
        failures = independent_checks(label, outcome, caller)["security_failures"]
        self.assertEqual(failures, ["EVIDENCE_VERSION", "NONCURRENT_CITATION"])

    def test_actual_ragas_id_metrics_include_empty_retrieval(self):
        _, label, outcome = example()
        label["evidence_ids"] = ["intake-response-09"]
        empty = asyncio.run(retrieval_scores(label, outcome))
        self.assertEqual(empty["recall"], 0)
        self.assertIsNone(empty["precision"])
        receipt = outcome["receipts"][0]
        receipt["tool_name"] = "search_procedures"
        receipt["result"]["evidence"] = receipt["result"]["threshold_evidence"]
        scored = asyncio.run(retrieval_scores(label, outcome))
        self.assertEqual((scored["precision"], scored["recall"]), (1, 1))

    def test_actual_ragas_dialogue_metric_catches_wrong_arguments_and_extra_tools(self):
        _, label, outcome = example()
        turn = {"message": "Count breaches", "expected": label,
                "expected_tools": ["read_service_metrics"], "outcome": outcome}
        self.assertEqual(asyncio.run(dialogue_tools([turn, turn])), 1)
        outcome["tool_attempts"][0]["call"]["arguments"] = {
            **outcome["tool_attempts"][0]["call"]["arguments"], "queue": "review"}
        self.assertLess(asyncio.run(dialogue_tools([turn])), 1)
        outcome["tool_attempts"] *= 2
        self.assertEqual(asyncio.run(dialogue_tools([turn])), 0)

    def test_ragas_judge_pipeline_records_two_calls_and_rejects_missing_claims(self):
        class Model:
            def __init__(self, outputs):
                self.outputs = iter(outputs)

            def generate(self, messages, schema, timeout):
                return next(self.outputs), {"eval_count": 5}

        claims = {"statements": ["Intake had 120 breaches."]}
        verdicts = {"statements": [{"statement": "Intake had 120 breaches.", "reason": "Supported", "verdict": 1}]}
        result = asyncio.run(LocalJudge(Model([claims, verdicts])).score("Count?", "120", ["120 breaches"]))
        self.assertEqual((result["state"], result["value"], len(result["calls"])), ("SCORED", 1, 2))
        verdicts["statements"] = []
        result = asyncio.run(LocalJudge(Model([claims, verdicts])).score("Count?", "120", ["120 breaches"]))
        self.assertEqual(result["state"], "ERROR")
        self.assertIsNone(result["value"])

    def test_judge_invalid_json_is_not_retried_or_converted_to_success(self):
        class Model:
            def generate(self, *args):
                return {"bad": "shape"}, {}

        result = asyncio.run(LocalJudge(Model()).score("Count?", "120", ["120 breaches"]))
        self.assertEqual((result["state"], len(result["calls"])), ("ERROR", 1))

    def test_labels_never_enter_agent_request(self):
        class Agent:
            def __init__(self):
                self.requests = []

            def run(self, request, caller):
                self.requests.append(request)
                return {"version": request["expected_version"] + 1}

        agent = Agent()
        with TemporaryDirectory() as temporary:
            store = SessionStore(Path(temporary) / "sessions.sqlite")
            run_dialogue(agent, store, {"caller": {"subject": "analyst", "allowed_queues": ["intake"]},
                                      "turns": [{"message": "Count?", "expected": {"secret": 120}}]})
        self.assertEqual(set(agent.requests[0]), {"session_id", "expected_version", "message"})

    def test_errors_and_abstentions_remain_in_denominators(self):
        caller, label, outcome = example()
        turn = {"expected": label, "outcome": outcome,
                "checks": independent_checks(label, outcome, caller),
                "faithfulness": {"state": "ERROR", "value": None}}
        summary = summarize([turn])
        self.assertEqual((summary["turns"], summary["faithfulness_eligible"], summary["faithfulness_scored"]), (1, 1, 0))
        outcome["answer"]["status"] = "ABSTAIN"
        self.assertEqual(summarize([turn])["incorrect_abstentions"], 1)

    def test_missing_runs_and_failed_calibration_never_claim_improvement(self):
        self.assertEqual(comparison_verdict([], True, 3), "INSUFFICIENT_EVIDENCE")
        caller, label, outcome = example()
        turn = {"expected": label, "outcome": outcome,
                "checks": independent_checks(label, outcome, caller),
                "faithfulness": {"state": "SCORED", "value": 1}}
        rows = [{"mode": mode, "split": "holdout", "repetition": rep, "dialogue_id": str(index),
                 "turns": [copy.deepcopy(turn) for _ in range(4)]}
                for mode in ("baseline", "conversational") for rep in range(3) for index in range(12)]
        self.assertEqual(comparison_verdict(rows, True, 3), "NO_CLEAR_GAIN")
        self.assertEqual(comparison_verdict(rows, False, 3), "INSUFFICIENT_EVIDENCE")
        for row in rows:
            if row["mode"] == "baseline" and row["dialogue_id"] == "0":
                row["turns"][0]["checks"]["exact_success"] = False
        self.assertEqual(comparison_verdict(rows, True, 3), "IMPROVED")
        rows[-1]["turns"][0]["faithfulness"]["state"] = "NOT_APPLICABLE"
        self.assertEqual(comparison_verdict(rows, True, 3), "INSUFFICIENT_EVIDENCE")
        rows[-1]["turns"][0]["checks"]["numeric_correct"] = False
        self.assertEqual(comparison_verdict(rows, False, 3), "REJECTED")


if __name__ == "__main__":
    unittest.main()
