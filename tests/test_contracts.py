import copy
import unittest
from datetime import datetime, timezone

from conversational_analytics_agent.contracts import (
    Caller, ContractError, Session, ToolCall, TurnRequest, validate_retrieval_sample, validate_turn,
)
from conversational_analytics_agent.fixtures import FIXTURES, load_json


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.caller = Caller.parse({"subject": "analyst", "allowed_queues": ["intake"]})
        self.session = {"session_id": "s1", "owner": "analyst", "version": 2,
                        "turn_count": 1, "expires_at": "2026-11-07T17:00:00+00:00"}
        self.now = datetime(2026, 11, 7, 16, tzinfo=timezone.utc)
        self.tool = {"name": "read_service_metrics", "arguments": {
            "queue": "intake", "metric_id": "first_response_breaches",
            "start_date": "2026-09-01", "end_date": "2026-10-01"}}
        self.turn = {"status": "ANSWERED", "message": "There were 120 breaches.",
                     "evidence_ids": ["receipt-1"], "tool_calls": [self.tool], "error_code": None}

    def assert_code(self, code, function, *arguments):
        with self.assertRaises(ContractError) as caught:
            function(*arguments)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)

    def test_caller_rejects_unknown_duplicate_or_empty_scope(self):
        for queues in ([], ["admin"], ["intake", "intake"], "intake", [None]):
            with self.subTest(queues=queues), self.assertRaises(ContractError):
                Caller.parse({"subject": "analyst", "allowed_queues": queues})

    def test_unknown_fields_cannot_supply_authority(self):
        self.assert_code("INVALID_FIELDS", Caller.parse,
                         {"subject": "analyst", "allowed_queues": ["intake"], "role": "admin"})

    def test_valid_session_authorization(self):
        Session.parse(self.session).authorize(self.caller, 2, self.now)

    def test_turn_request_accepts_message_but_not_embedded_authority(self):
        request = {"session_id": "s1", "expected_version": 2, "message": "Which rule applies?"}
        self.assertEqual(TurnRequest.parse(request).session_id, "s1")
        request["allowed_queues"] = ["intake", "review"]
        self.assert_code("INVALID_FIELDS", TurnRequest.parse, request)

    def test_turn_request_enforces_message_and_version_limits(self):
        for value in ("", "x" * 1201, None):
            request = {"session_id": "s1", "expected_version": 2, "message": value}
            self.assert_code("INVALID_TEXT", TurnRequest.parse, request)
        request = {"session_id": "s1", "expected_version": True, "message": "A question"}
        self.assert_code("INVALID_INTEGER", TurnRequest.parse, request)

    def test_foreign_owner_is_denied_before_other_session_checks(self):
        self.session["owner"] = "another-person"
        self.assert_code("SESSION_DENIED", Session.parse(self.session).authorize,
                         self.caller, 999, self.now)

    def test_stale_version_is_rejected(self):
        self.assert_code("SESSION_CONFLICT", Session.parse(self.session).authorize,
                         self.caller, 1, self.now)

    def test_expiry_is_exclusive(self):
        session = Session.parse(self.session)
        self.assert_code("SESSION_EXPIRED", session.authorize,
                         self.caller, 2, session.expires_at)

    def test_naive_and_malformed_timestamps_fail(self):
        for expiry in ("2026-11-07T17:00:00", "invalid", None):
            self.session["expires_at"] = expiry
            with self.subTest(expiry=expiry), self.assertRaises(ContractError):
                Session.parse(self.session)

    def test_six_completed_turns_prevent_another_turn(self):
        self.session["turn_count"] = 6
        self.assert_code("TURN_LIMIT", Session.parse(self.session).authorize,
                         self.caller, 2, self.now)

    def test_boolean_versions_and_negative_counts_are_rejected(self):
        for field, value in (("version", True), ("turn_count", -1), ("turn_count", 7)):
            session = {**self.session, field: value}
            self.assert_code("INVALID_INTEGER", Session.parse, session)

    def test_valid_read_tools(self):
        call = ToolCall.parse(self.tool, self.caller)
        self.assertEqual(call.arguments["metric_id"], "first_response_breaches")
        search = copy.deepcopy(self.tool)
        search["name"] = "search_procedures"
        del search["arguments"]["metric_id"]
        search["arguments"]["query"] = "first response deadline"
        self.assertEqual(ToolCall.parse(search, self.caller).name, "search_procedures")

    def test_forbidden_queue_fails_before_dispatch(self):
        self.tool["arguments"]["queue"] = "review"
        self.assert_code("SCOPE_DENIED", ToolCall.parse, self.tool, self.caller)

    def test_arbitrary_tool_or_sql_is_rejected(self):
        self.tool["name"] = "run_sql"
        self.assert_code("UNKNOWN_TOOL", ToolCall.parse, self.tool, self.caller)
        self.tool["name"] = "read_service_metrics"
        self.tool["arguments"]["sql"] = "SELECT * FROM secrets"
        self.assert_code("INVALID_FIELDS", ToolCall.parse, self.tool, self.caller)

    def test_unknown_metric_cannot_be_guessed(self):
        self.tool["arguments"]["metric_id"] = "overdue"
        self.assert_code("INVALID_METRIC", ToolCall.parse, self.tool, self.caller)

    def test_invalid_dates_and_intervals(self):
        for start, end in (("2026-09-01", "2026-09-01"), ("2026-10-01", "2026-09-01"),
                           ("2026-01-01", "2026-10-01"), ("2026-02-30", "2026-03-01"),
                           ("20260901", "2026-10-01")):
            self.tool["arguments"].update(start_date=start, end_date=end)
            with self.subTest(start=start, end=end), self.assertRaises(ContractError):
                ToolCall.parse(self.tool, self.caller)

    def test_answer_requires_available_evidence(self):
        validate_turn(self.turn, self.caller, {"receipt-1"})
        self.assert_code("UNKNOWN_EVIDENCE", validate_turn, self.turn, self.caller, set())
        self.turn["evidence_ids"] = []
        self.assert_code("INVALID_ANSWER", validate_turn, self.turn, self.caller, set())

    def test_error_and_nonanswer_states(self):
        for status in ("CLARIFY", "ABSTAIN", "ERROR"):
            self.turn.update(status=status, evidence_ids=[], tool_calls=[],
                             error_code="MODEL_TIMEOUT" if status == "ERROR" else None)
            validate_turn(self.turn, self.caller, set())
            self.turn["evidence_ids"] = ["receipt-1"]
            self.assert_code("INVALID_ANSWER", validate_turn, self.turn, self.caller, {"receipt-1"})

    def test_unknown_status_and_excess_tool_calls(self):
        self.turn["status"] = "SUCCESS"
        self.assert_code("INVALID_STATUS", validate_turn, self.turn, self.caller, {"receipt-1"})
        self.turn["status"] = "ANSWERED"
        self.turn["tool_calls"] = [self.tool] * 4
        self.assert_code("TOOL_LIMIT", validate_turn, self.turn, self.caller, {"receipt-1"})

    def test_saved_retrieval_sample_has_parallel_context_and_id_lists(self):
        sample = load_json(FIXTURES / "retrieval-sample.json")
        validate_retrieval_sample(sample)
        sample["retrieved_contexts"] = []
        self.assert_code("CONTEXT_MISMATCH", validate_retrieval_sample, sample)

    def test_context_budget_is_total_not_only_per_passage(self):
        sample = load_json(FIXTURES / "retrieval-sample.json")
        sample["retrieved_contexts"] = ["a" * 5000, "b" * 5000]
        sample["retrieved_context_ids"] = ["a", "b"]
        self.assert_code("CONTEXT_LIMIT", validate_retrieval_sample, sample)

    def test_blank_or_oversized_fields_are_rejected(self):
        for message in (" ", "a" * 4001, [], None):
            self.turn["message"] = message
            self.assert_code("INVALID_TEXT", validate_turn, self.turn, self.caller, {"receipt-1"})


if __name__ == "__main__":
    unittest.main()
