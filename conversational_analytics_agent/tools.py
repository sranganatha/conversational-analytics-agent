"""Scoped procedure retrieval and fixed analytical queries over local snapshots."""

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import duckdb

from .contracts import Caller, ToolCall, day, require
from .fixtures import load_json, validate_catalog
from .prepare import digest

DATA = Path(__file__).resolve().parent.parent / "data"
METRIC_SQL = {
    "first_response_breaches": "SELECT count(*), sum(case_count), sum(first_response_breaches) "
                              "FROM daily WHERE queue = ? AND service_date >= ? AND service_date < ?",
    "resolution_breaches": "SELECT count(*), sum(case_count), sum(resolution_breaches) "
                          "FROM daily WHERE queue = ? AND service_date >= ? AND service_date < ?",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class EvidenceTools:
    def __init__(self, data: Path = DATA):
        self.data = data
        self.metadata = load_json(data / "metadata.json")
        validate_catalog(self.metadata["catalog"])
        require(digest(data / "procedures.sqlite") == self.metadata["index_digest"]
                and digest(data / "metrics.duckdb") == self.metadata["database_digest"],
                "SNAPSHOT_DIGEST_MISMATCH")
        self.metrics = {item["metric_id"]: item for item in self.metadata["catalog"]["metrics"]}

    def _index(self) -> sqlite3.Connection:
        connection = sqlite3.connect((self.data / "procedures.sqlite").resolve().as_uri() + "?mode=ro",
                                     uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def execute(self, value: Any, caller: Caller) -> dict[str, Any]:
        call = ToolCall.parse(value, caller)
        result = self._search(call.arguments) if call.name == "search_procedures" else self._metrics(call.arguments)
        receipt = {"tool_name": call.name, "arguments": call.arguments,
                   "source_digests": {name: self.metadata[name] for name in
                                      ("corpus_digest", "dataset_digest", "catalog_digest")},
                   "result": result}
        return {"receipt_id": hashlib.sha256(canonical(receipt).encode()).hexdigest(), **receipt}

    @staticmethod
    def _conflicting(records: list[dict[str, Any]]) -> bool:
        for position, left in enumerate(records):
            for right in records[position + 1:]:
                if (left["metric_id"] is not None and left["metric_id"] == right["metric_id"]
                        and left["threshold_hours"] != right["threshold_hours"]
                        and left["effective_from"] < right["effective_to"]
                        and right["effective_from"] < left["effective_to"]):
                    return True
        return False

    def _search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        tokens = list(dict.fromkeys(re.findall(r"[^\W_]+", arguments["query"].lower())))[:20]
        if not tokens:
            return {"status": "NO_EVIDENCE", "evidence": []}
        expression = " OR ".join('"' + token + '"' for token in tokens)
        connection = self._index()
        try:
            rows = connection.execute(
                "SELECT p.* FROM procedure_search JOIN procedures p ON p.rowid = procedure_search.rowid "
                "WHERE procedure_search MATCH ? AND p.queue = ? "
                "AND p.effective_from < ? AND p.effective_to > ? "
                "ORDER BY rank, p.evidence_id",
                (expression, arguments["queue"], arguments["end_date"], arguments["start_date"])).fetchall()
        finally:
            connection.close()
        evidence = [dict(row) for row in rows]
        if self._conflicting(evidence):
            return {"status": "CONFLICT", "evidence": evidence}
        return {"status": "OK" if evidence else "NO_EVIDENCE", "evidence": evidence[:5]}

    def _metrics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        metric_id = arguments["metric_id"]
        require(metric_id in self.metrics, "INVALID_METRIC")
        connection = self._index()
        try:
            rules = [dict(row) for row in connection.execute(
                "SELECT * FROM procedures WHERE queue = ? AND metric_id = ? "
                "AND effective_from < ? AND effective_to > ? ORDER BY effective_from, evidence_id",
                (arguments["queue"], metric_id, arguments["end_date"], arguments["start_date"]))]
        finally:
            connection.close()
        if self._conflicting(rules):
            return {"status": "CONFLICT", "evidence": [], "threshold_evidence": rules}
        first, last = day(arguments["start_date"]), day(arguments["end_date"])
        covered_until = arguments["start_date"]
        for rule in rules:
            if rule["effective_from"] > covered_until:
                break
            covered_until = max(covered_until, rule["effective_to"])
        if covered_until < arguments["end_date"]:
            return {"status": "MISSING_RULE", "evidence": [], "threshold_evidence": rules}
        database = duckdb.connect(str(self.data / "metrics.duckdb"), read_only=True,
                                  config={"enable_external_access": "false", "threads": "1"})
        try:
            count, denominator, numerator = database.execute(
                METRIC_SQL[metric_id], [arguments["queue"], first, last]).fetchone()
        finally:
            database.close()
        if count != (last - first).days:
            return {"status": "MISSING_DATA", "evidence": [], "threshold_evidence": rules}
        period = (first.strftime("%Y-%m") if first.day == last.day == 1
                  and ((last.year - first.year) * 12 + last.month - first.month) == 1
                  else f"{first}:{last}")
        evidence = {"evidence_id": f"aggregate:{arguments['queue']}:{metric_id}:{period}",
                    **arguments, "value": numerator, "numerator": numerator,
                    "denominator": denominator, "unit": self.metrics[metric_id]["unit"]}
        return {"status": "OK", "evidence": [evidence], "threshold_evidence": rules}
