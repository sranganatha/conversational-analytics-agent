import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from conversational_analytics_agent.contracts import Caller, ContractError
from conversational_analytics_agent.store import SessionStore
from conversational_analytics_agent.tools import EvidenceTools


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "sessions.sqlite"
        self.store = SessionStore(self.path)
        self.tools = EvidenceTools()
        self.now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
        self.caller = Caller.parse({"subject": "analyst", "allowed_queues": ["intake", "review"]})
        self.session = self.store.create(self.caller, self.now)
        self.request = {"session_id": self.session.session_id, "expected_version": 0,
                        "message": "Read September first-response breaches for intake."}
        self.call = {"name": "read_service_metrics", "arguments": {"queue": "intake",
                     "metric_id": "first_response_breaches", "start_date": "2026-09-01",
                     "end_date": "2026-10-01"}}

    def execute(self, version=0, call=None, now=None):
        return self.store.execute({**self.request, "expected_version": version}, self.caller,
                                  [call or self.call], now or self.now, self.tools)

    def assert_code(self, code, function, *arguments):
        with self.assertRaises(ContractError) as caught:
            function(*arguments)
        self.assertEqual(caught.exception.code, code)

    def test_session_receipts_and_turns_survive_reopen(self):
        result = self.execute()
        saved = SessionStore(self.path).get(self.session.session_id, self.caller, self.now)
        self.assertEqual(saved["session"]["version"], 1)
        self.assertEqual(saved["session"]["turn_count"], 1)
        self.assertEqual(saved["turns"][0]["receipts"], result["receipts"])
        self.assertEqual(saved["turns"][0]["request"], self.request)

    def test_scope_denial_does_not_dispatch_or_commit(self):
        restricted = Caller.parse({"subject": "analyst", "allowed_queues": ["review"]})
        with patch.object(self.tools, "execute") as dispatch:
            self.assert_code("SCOPE_DENIED", self.store.execute, self.request, restricted,
                             [self.call], self.now, self.tools)
            dispatch.assert_not_called()
        self.assertEqual(self.store.get(self.session.session_id, self.caller, self.now)["session"]["version"], 0)

    def test_entire_batch_is_validated_before_dispatch(self):
        wrong = {**self.call, "arguments": {**self.call["arguments"], "metric_id": "unknown"}}
        with patch.object(self.tools, "execute") as dispatch:
            self.assert_code("INVALID_METRIC", self.store.execute, self.request, self.caller,
                             [self.call, wrong], self.now, self.tools)
            dispatch.assert_not_called()

    def test_foreign_or_unknown_session_is_denied(self):
        other = Caller.parse({"subject": "other", "allowed_queues": ["intake", "review"]})
        for session_id in (self.session.session_id, "nonexistent"):
            request = {**self.request, "session_id": session_id}
            with patch.object(self.tools, "execute") as dispatch:
                self.assert_code("SESSION_DENIED", self.store.execute, request, other,
                                 [self.call], self.now, self.tools)
                dispatch.assert_not_called()
            self.assert_code("SESSION_DENIED", self.store.get, session_id, other, self.now)

    def test_expired_and_stale_requests_never_dispatch(self):
        with patch.object(self.tools, "execute") as dispatch:
            self.assert_code("SESSION_EXPIRED", self.execute, 0, None, self.now + timedelta(hours=1))
            self.assert_code("SESSION_CONFLICT", self.execute, 9)
            dispatch.assert_not_called()

    def test_expired_history_is_not_returned(self):
        self.execute()
        self.assert_code("SESSION_EXPIRED", self.store.get, self.session.session_id,
                         self.caller, self.now + timedelta(hours=1))

    def test_response_loss_is_reconciled_from_persisted_history(self):
        self.execute()
        self.assert_code("SESSION_CONFLICT", self.execute)
        saved = self.store.get(self.session.session_id, self.caller, self.now)
        self.assertEqual(len(saved["turns"]), 1)
        self.assertEqual(saved["turns"][0]["receipts"][0]["result"]["evidence"][0]["value"], 120)

    def test_date_queue_and_metric_changes_drop_active_evidence(self):
        result = self.execute()
        prior = set(result["state"]["active_evidence"])
        self.call["arguments"].update(start_date="2026-08-01", end_date="2026-09-01")
        for version, change in ((1, {}), (2, {"queue": "review"}),
                                (3, {"metric_id": "resolution_breaches"})):
            self.call["arguments"].update(change)
            result = self.execute(version)
            active = set(result["state"]["active_evidence"])
            self.assertFalse(active & prior)
            prior = active
        saved = self.store.get(self.session.session_id, self.caller, self.now)
        self.assertEqual(len(saved["turns"]), 4)
        self.assertIn("aggregate:intake:first_response_breaches:2026-09",
                      saved["turns"][0]["receipts"][0]["result"]["evidence"][0]["evidence_id"])

    def test_search_then_metrics_keeps_compatible_rule_evidence(self):
        search = {"name": "search_procedures", "arguments": {
            key: value for key, value in self.call["arguments"].items() if key != "metric_id"}}
        search["arguments"]["query"] = "first response resolution"
        result = self.store.execute(self.request, self.caller, [search, self.call], self.now, self.tools)
        active = result["state"]["active_evidence"]
        self.assertIn("intake-response-09", active)
        self.assertIn("aggregate:intake:first_response_breaches:2026-09", active)
        self.assertNotIn("intake-resolution-09", active)

    def test_conflict_invalidates_previous_answer_evidence(self):
        self.execute()
        self.call["arguments"].update(start_date="2026-10-01", end_date="2026-11-01")
        result = self.execute(1)
        self.assertEqual(result["receipts"][0]["result"]["status"], "CONFLICT")
        self.assertEqual(result["state"]["active_evidence"], {})

    def test_failed_second_tool_rolls_back_first_receipt_and_session(self):
        receipt = self.tools.execute(self.call, self.caller)
        with patch.object(self.tools, "execute", side_effect=[receipt, ContractError("READ_FAILED")]):
            self.assert_code("READ_FAILED", self.store.execute, self.request, self.caller,
                             [self.call, self.call], self.now, self.tools)
        saved = self.store.get(self.session.session_id, self.caller, self.now)
        self.assertEqual(saved["session"]["version"], 0)
        self.assertEqual(saved["turns"], [])
        with sqlite3.connect(self.path) as database:
            self.assertEqual(database.execute("SELECT count(*) FROM receipts").fetchone()[0], 0)

    def test_concurrent_same_version_has_one_commit(self):
        barrier = Barrier(2)

        def attempt():
            barrier.wait(timeout=5)
            try:
                self.execute()
                return "COMMITTED"
            except ContractError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt) for _ in range(2)]
            outcomes = [future.result(timeout=10) for future in futures]
        self.assertCountEqual(outcomes, ["COMMITTED", "SESSION_CONFLICT"])
        self.assertEqual(len(self.store.get(self.session.session_id, self.caller, self.now)["turns"]), 1)

    def test_repeated_reads_reuse_receipt_without_overwriting_history(self):
        first = self.execute()
        second = self.execute(1)
        self.assertEqual(first["receipts"], second["receipts"])
        with sqlite3.connect(self.path) as database:
            self.assertEqual(database.execute("SELECT count(*) FROM receipts").fetchone()[0], 1)
            self.assertEqual(database.execute("SELECT count(*) FROM turns").fetchone()[0], 2)
            for statement in ("UPDATE receipts SET payload = '{}'", "DELETE FROM receipts",
                              "UPDATE turns SET request = '{}'", "DELETE FROM turns"):
                with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                    database.execute(statement)

    def test_seventh_turn_fails_but_history_remains_readable(self):
        for version in range(6):
            self.execute(version)
        self.assert_code("TURN_LIMIT", self.execute, 6)
        saved = self.store.get(self.session.session_id, self.caller, self.now)
        self.assertEqual(len(saved["turns"]), 6)

    def test_current_scope_is_checked_when_reading_historical_receipts(self):
        self.execute()
        restricted = Caller.parse({"subject": "analyst", "allowed_queues": ["review"]})
        self.assert_code("SCOPE_DENIED", self.store.get, self.session.session_id, restricted, self.now)

    def test_malformed_persisted_state_is_rejected(self):
        with sqlite3.connect(self.path) as database:
            database.execute("UPDATE sessions SET state = '{}' WHERE session_id = ?",
                             (self.session.session_id,))
        self.assert_code("INVALID_SESSION_STATE", self.execute)

    def test_empty_and_excessive_tool_batches_are_rejected(self):
        for calls in ([], [self.call] * 4):
            self.assert_code("TOOL_LIMIT", self.store.execute, self.request, self.caller,
                             calls, self.now, self.tools)

    def test_changed_receipt_payload_is_rejected(self):
        self.execute()
        with sqlite3.connect(self.path) as database:
            database.execute("DROP TRIGGER receipts_no_update")
            database.execute("UPDATE receipts SET payload = '{}' ")
        self.assert_code("RECEIPT_DIGEST_MISMATCH", self.store.get,
                         self.session.session_id, self.caller, self.now)


if __name__ == "__main__":
    unittest.main()
