import json
import shutil
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import duckdb

from conversational_analytics_agent.contracts import Caller, ContractError
from conversational_analytics_agent.fixtures import FIXTURES, load_json
from conversational_analytics_agent.prepare import digest, prepare
from conversational_analytics_agent.tools import DATA, EvidenceTools


class EvidenceToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = EvidenceTools()
        cls.caller = Caller.parse({"subject": "analyst", "allowed_queues": ["intake", "review"]})

    def call(self, name="read_service_metrics", queue="intake", start="2026-09-01",
             end="2026-10-01", metric="first_response_breaches", query="first response"):
        arguments = {"queue": queue, "start_date": start, "end_date": end}
        arguments["query" if name == "search_procedures" else "metric_id"] = (
            query if name == "search_procedures" else metric)
        return {"name": name, "arguments": arguments}

    def test_search_filters_queue_and_effective_date(self):
        result = self.tools.execute(self.call("search_procedures"), self.caller)["result"]
        self.assertEqual(result["status"], "OK")
        identities = {item["evidence_id"] for item in result["evidence"]}
        self.assertIn("intake-response-09", identities)
        self.assertNotIn("intake-response-08", identities)
        for evidence in result["evidence"]:
            self.assertEqual(evidence["queue"], "intake")
            self.assertLess(evidence["effective_from"], "2026-10-01")
            self.assertGreater(evidence["effective_to"], "2026-09-01")

    def test_search_returns_exact_source_text(self):
        original = {item["evidence_id"]: item for item in load_json(FIXTURES / "procedures.json")["procedures"]}
        result = self.tools.execute(self.call("search_procedures"), self.caller)["result"]
        for evidence in result["evidence"]:
            self.assertEqual(evidence, original[evidence["evidence_id"]])

    def test_fts_syntax_is_not_executed_from_query_text(self):
        for query in ('" OR *', "NEAR(unknownneedle) NOT abcxyz", "'; DROP TABLE procedures; --", "!!!"):
            with self.subTest(query=query):
                result = self.tools.execute(self.call("search_procedures", query=query), self.caller)["result"]
                self.assertIn(result["status"], {"OK", "NO_EVIDENCE"})
                self.assertTrue(all(item["queue"] == "intake" for item in result["evidence"]))

    def test_absent_search_result_is_visible(self):
        result = self.tools.execute(self.call("search_procedures", query="unfindablexyz"), self.caller)["result"]
        self.assertEqual(result, {"status": "NO_EVIDENCE", "evidence": []})

    def test_conflicting_rules_never_produce_a_numeric_answer(self):
        for name in ("search_procedures", "read_service_metrics"):
            result = self.tools.execute(self.call(name, start="2026-10-01", end="2026-11-01"), self.caller)["result"]
            self.assertEqual(result["status"], "CONFLICT")
            self.assertFalse(any("value" in item for item in result["evidence"]))

    def test_monthly_counts_match_independent_expectations(self):
        for expected in load_json(FIXTURES / "expected-totals.json")["monthly"]:
            for metric in ("first_response_breaches", "resolution_breaches"):
                result = self.tools.execute(self.call(queue=expected["queue"], start=expected["start_date"],
                    end=expected["end_date"], metric=metric), self.caller)["result"]
                self.assertEqual(result["status"], "OK")
                self.assertEqual(result["evidence"][0]["value"], expected[metric])
                self.assertEqual(result["evidence"][0]["denominator"], expected["case_count"])
                self.assertTrue(result["threshold_evidence"])

    def test_interval_is_half_open(self):
        result = self.tools.execute(self.call(start="2026-08-31", end="2026-09-02"), self.caller)["result"]
        self.assertEqual(result["evidence"][0]["value"], 7)
        self.assertEqual(result["evidence"][0]["denominator"], 22)
        self.assertEqual({row["evidence_id"] for row in result["threshold_evidence"]},
                         {"intake-response-08", "intake-response-09"})

    def test_missing_rule_is_not_a_zero_count(self):
        result = self.tools.execute(self.call(start="2026-07-01", end="2026-08-01"), self.caller)["result"]
        self.assertEqual(result["status"], "MISSING_RULE")
        self.assertEqual(result["evidence"], [])

    def test_scope_and_metric_rejection_precede_database_access(self):
        caller = Caller.parse({"subject": "restricted", "allowed_queues": ["intake"]})
        for call, code in ((self.call(queue="review"), "SCOPE_DENIED"),
                           (self.call(metric="overdue"), "INVALID_METRIC")):
            with self.subTest(code=code), patch.object(self.tools, "_index") as index, \
                    patch("conversational_analytics_agent.tools.duckdb.connect") as database:
                with self.assertRaises(ContractError) as caught:
                    self.tools.execute(call, caller)
                self.assertEqual(caught.exception.code, code)
                index.assert_not_called()
                database.assert_not_called()

    def test_receipts_are_repeatable_and_bound_to_arguments(self):
        first = self.tools.execute(self.call(), self.caller)
        self.assertEqual(first, self.tools.execute(self.call(), self.caller))
        other = self.tools.execute(self.call(metric="resolution_breaches"), self.caller)
        self.assertNotEqual(first["receipt_id"], other["receipt_id"])
        self.assertEqual(len(first["receipt_id"]), 64)

    def test_source_instruction_cannot_expand_scope(self):
        caller = Caller.parse({"subject": "reviewer", "allowed_queues": ["review"]})
        result = self.tools.execute(self.call("search_procedures", queue="review", query="imported"), caller)["result"]
        self.assertIn("ignore access rules", result["evidence"][0]["text"])
        with self.assertRaises(ContractError) as caught:
            self.tools.execute(self.call(queue="intake"), caller)
        self.assertEqual(caught.exception.code, "SCOPE_DENIED")

    def test_snapshots_are_opened_read_only(self):
        connection = self.tools._index()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM procedures")
        finally:
            connection.close()
        database = duckdb.connect(str(DATA / "metrics.duckdb"), read_only=True,
                                  config={"enable_external_access": "false", "threads": "1"})
        try:
            with self.assertRaises(duckdb.Error):
                database.execute("DELETE FROM daily")
        finally:
            database.close()

    def test_query_binds_untrusted_values_and_disables_external_access(self):
        original = duckdb.connect
        with patch("conversational_analytics_agent.tools.duckdb.connect", wraps=original) as connect:
            self.tools.execute(self.call(), self.caller)
        self.assertTrue(connect.call_args.kwargs["read_only"])
        self.assertEqual(connect.call_args.kwargs["config"]["enable_external_access"], "false")

    def test_missing_day_is_not_returned_as_a_partial_total(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("metadata.json", "procedures.sqlite", "metrics.duckdb"):
                shutil.copyfile(DATA / name, directory / name)
            database = duckdb.connect(str(directory / "metrics.duckdb"))
            try:
                database.execute("DELETE FROM daily WHERE service_date = '2026-09-01' AND queue = 'intake'")
            finally:
                database.close()
            metadata = load_json(directory / "metadata.json")
            metadata["database_digest"] = digest(directory / "metrics.duckdb")
            (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            result = EvidenceTools(directory).execute(self.call(), self.caller)["result"]
            self.assertEqual(result["status"], "MISSING_DATA")
            self.assertEqual(result["evidence"], [])

    def test_changed_snapshot_bytes_are_rejected(self):
        with patch("conversational_analytics_agent.tools.digest", return_value="wrong"):
            with self.assertRaises(ContractError) as caught:
                EvidenceTools()
            self.assertEqual(caught.exception.code, "SNAPSHOT_DIGEST_MISMATCH")

    def test_preparation_needs_only_sources_not_evaluation_labels(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "sources"
            source.mkdir()
            for name in ("daily.csv", "metrics.json", "procedures.json"):
                shutil.copyfile(FIXTURES / name, source / name)
            destination = Path(temporary) / "data"
            prepare(source, destination)
            result = EvidenceTools(destination).execute(self.call(), self.caller)
            self.assertEqual(result["result"]["evidence"][0]["value"], 120)
            with self.assertRaises(ContractError) as caught:
                prepare(source, destination)
            self.assertEqual(caught.exception.code, "SNAPSHOT_EXISTS")
