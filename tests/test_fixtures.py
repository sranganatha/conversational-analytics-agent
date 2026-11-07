import copy
import csv
import json
import unittest
from unittest.mock import patch

from conversational_analytics_agent.contracts import ContractError
from conversational_analytics_agent.fixtures import (
    FIXTURES, load_json, validate_catalog, validate_daily, validate_dialogues,
    validate_fixture_directory, validate_procedures,
)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.procedures = load_json(FIXTURES / "procedures.json")
        self.evidence = validate_procedures(self.procedures)
        with (FIXTURES / "daily.csv").open(encoding="utf-8", newline="") as stream:
            self.rows = list(csv.DictReader(stream))
        for row in self.rows:
            for field in ("case_count", "first_response_breaches", "resolution_breaches"):
                row[field] = int(row[field])
        self.expected = load_json(FIXTURES / "expected-totals.json")
        self.aggregates = validate_daily(self.rows, self.expected)
        self.dialogues = [json.loads(line) for line in
                          (FIXTURES / "dialogues.jsonl").read_text(encoding="utf-8").splitlines()]

    def assert_code(self, code, function, *arguments):
        with self.assertRaises(ContractError) as caught:
            function(*arguments)
        self.assertEqual(caught.exception.code, code)

    def test_complete_frozen_corpus(self):
        validate_fixture_directory()

    def test_golden_totals_are_independent_of_daily_row_changes(self):
        self.rows[0]["first_response_breaches"] += 1
        self.assert_code("AGGREGATE_MISMATCH", validate_daily, self.rows, self.expected)

    def test_changed_expected_totals_also_fail(self):
        self.expected["monthly"][0]["first_response_breaches"] = 0
        self.assert_code("AGGREGATE_MISMATCH", validate_daily, self.rows, self.expected)

    def test_duplicate_daily_key_is_rejected(self):
        self.rows[1] = copy.deepcopy(self.rows[0])
        self.assert_code("DUPLICATE_DAILY_RECORD", validate_daily, self.rows, self.expected)

    def test_missing_day_and_impossible_count_are_rejected(self):
        self.assert_code("INVALID_DAILY_COUNT", validate_daily, self.rows[:-1], self.expected)
        self.rows[0]["resolution_breaches"] = self.rows[0]["case_count"] + 1
        self.assert_code("INVALID_INTEGER", validate_daily, self.rows, self.expected)

    def test_expected_total_period_must_match_its_month(self):
        self.expected["monthly"][0]["end_date"] = "2026-09-02"
        self.assert_code("INVALID_EXPECTED_TOTALS", validate_daily, self.rows, self.expected)

    def test_duplicate_procedure_identity_fails(self):
        self.procedures["procedures"][1]["evidence_id"] = self.procedures["procedures"][0]["evidence_id"]
        self.assert_code("DUPLICATE_EVIDENCE", validate_procedures, self.procedures)

    def test_catalog_cannot_redefine_a_metric_silently(self):
        catalog = load_json(FIXTURES / "metrics.json")
        catalog["metrics"][0]["numerator"] = "case_count"
        self.assert_code("INVALID_METRIC_DEFINITION", validate_catalog, catalog)

    def test_family_cannot_cross_splits(self):
        first = self.dialogues[0]
        sibling = next(row for row in self.dialogues[1:] if row["family_id"] == first["family_id"])
        sibling["split"] = "holdout"
        self.assert_code("SPLIT_LEAKAGE", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)

    def test_incorrect_dialogue_numeric_expectation_fails(self):
        self.dialogues[0]["turns"][1]["expected"]["value"] = 119
        self.assert_code("AGGREGATE_MISMATCH", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)

    def test_fabricated_and_wrong_scope_evidence_fail(self):
        label = self.dialogues[0]["turns"][0]["expected"]
        label["evidence_ids"] = ["made-up"]
        self.assert_code("UNKNOWN_EVIDENCE", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)
        label["evidence_ids"] = ["review-response-09"]
        self.assert_code("LABEL_EVIDENCE_MISMATCH", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)

    def test_stale_evidence_in_answer_label_fails(self):
        self.dialogues[0]["turns"][0]["expected"]["evidence_ids"] = ["intake-response-08"]
        self.assert_code("STALE_EVIDENCE", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)

    def test_nonanswer_cannot_hide_an_expected_answer(self):
        turn = self.dialogues[0]["turns"][0]
        turn["expected"]["status"] = "ABSTAIN"
        self.assert_code("INVALID_LABEL", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)

    def test_dialogue_duplicates_and_missing_turns_fail(self):
        self.dialogues[1]["dialogue_id"] = self.dialogues[0]["dialogue_id"]
        self.assert_code("DUPLICATE_DIALOGUE", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)
        self.dialogues[0]["turns"].pop()
        self.assert_code("INVALID_TURNS", validate_dialogues, self.dialogues,
                         self.evidence, self.aggregates)

    def test_fixture_digest_detects_byte_changes(self):
        with patch("conversational_analytics_agent.fixtures.Path.read_bytes", return_value=b"changed"):
            self.assert_code("FIXTURE_DIGEST_MISMATCH", validate_fixture_directory)


if __name__ == "__main__":
    unittest.main()
