"""Validate the synthetic corpus and independently specified expectations."""

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .contracts import (
    METRICS, QUEUES, STATUSES, Caller, day, integer, interval, record, require,
    strings, text, validate_retrieval_sample,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CATEGORIES = {"temporal", "queue_switch", "clarification", "missing_data", "versioning", "injection"}


def load_json(path: Path) -> Any:
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_FIELD")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def validate_catalog(data: Any) -> None:
    catalog = record(data, {"version", "metrics"})
    require(type(catalog["version"]) is int and catalog["version"] == 1, "INVALID_VERSION")
    require(type(catalog["metrics"]) is list and len(catalog["metrics"]) == 2, "INVALID_CATALOG")
    seen: set[str] = set()
    for metric in catalog["metrics"]:
        record(metric, {"metric_id", "description", "unit", "numerator", "denominator",
                        "allowed_filters", "threshold_kind"})
        metric_id = text(metric["metric_id"], 60)
        require(metric_id in METRICS and metric_id not in seen, "INVALID_METRIC")
        seen.add(metric_id)
        text(metric["description"])
        expected_kind = "first_response_hours" if metric_id == "first_response_breaches" else "resolution_hours"
        require(metric["unit"] == "cases" and metric["numerator"] == metric_id
                and metric["denominator"] == "case_count"
                and metric["threshold_kind"] == expected_kind, "INVALID_METRIC_DEFINITION")
        require(strings(metric["allowed_filters"]) == ["queue", "start_date", "end_date"],
                "INVALID_FILTERS")


def validate_procedures(data: Any) -> dict[str, dict[str, Any]]:
    record(data, {"version", "procedures"})
    require(type(data["version"]) is int and data["version"] == 1, "INVALID_VERSION")
    require(type(data["procedures"]) is list and len(data["procedures"]) == 12, "INVALID_CORPUS")
    evidence: dict[str, dict[str, Any]] = {}
    for procedure in data["procedures"]:
        record(procedure, {"evidence_id", "queue", "effective_from", "effective_to",
                           "metric_id", "threshold_hours", "text"})
        evidence_id = text(procedure["evidence_id"], 100)
        require(evidence_id not in evidence, "DUPLICATE_EVIDENCE")
        text(procedure["queue"], 30)
        require(procedure["queue"] in QUEUES, "INVALID_QUEUE")
        interval(procedure["effective_from"], procedure["effective_to"])
        if procedure["metric_id"] is None:
            require(procedure["threshold_hours"] is None, "INVALID_THRESHOLD")
        else:
            text(procedure["metric_id"], 60)
            require(procedure["metric_id"] in METRICS, "INVALID_METRIC")
            integer(procedure["threshold_hours"], 1, 168)
        text(procedure["text"], 2000)
        evidence[evidence_id] = procedure
    return evidence


def validate_daily(rows: list[dict[str, Any]], expected: Any) -> dict[str, dict[str, Any]]:
    require(len(rows) == 122, "INVALID_DAILY_COUNT")
    daily_keys: set[tuple[str, str]] = set()
    sums: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for row in rows:
        record(row, {"service_date", "queue", "case_count", *METRICS})
        service_day = day(row["service_date"])
        require(day("2026-08-01") <= service_day < day("2026-10-01"), "INVALID_DATA_DATE")
        text(row["queue"], 30)
        require(row["queue"] in QUEUES, "INVALID_QUEUE")
        key = (row["service_date"], row["queue"])
        require(key not in daily_keys, "DUPLICATE_DAILY_RECORD")
        daily_keys.add(key)
        count = integer(row["case_count"])
        for metric in METRICS:
            integer(row[metric], maximum=count)
        sums[(row["queue"], service_day.strftime("%Y-%m"))].update(
            {name: row[name] for name in {"case_count", *METRICS}})
    record(expected, {"version", "monthly"})
    require(type(expected["version"]) is int and expected["version"] == 1, "INVALID_VERSION")
    require(type(expected["monthly"]) is list and len(expected["monthly"]) == 4,
            "INVALID_EXPECTED_TOTALS")
    references: dict[str, dict[str, Any]] = {}
    observed: set[tuple[str, str]] = set()
    for total in expected["monthly"]:
        record(total, {"queue", "start_date", "end_date", "case_count", *METRICS})
        first, last = interval(total["start_date"], total["end_date"])
        text(total["queue"], 30)
        key = (total["queue"], first.strftime("%Y-%m"))
        require(key in sums and key not in observed and first.day == 1 and last.day == 1,
                "INVALID_EXPECTED_TOTALS")
        require((first.month, last.month) in {(8, 9), (9, 10)} and last.year == first.year,
                "INVALID_EXPECTED_TOTALS")
        observed.add(key)
        for field in {"case_count", *METRICS}:
            require(integer(total[field]) == sums[key][field], "AGGREGATE_MISMATCH")
        for metric in METRICS:
            evidence_id = f"aggregate:{total['queue']}:{metric}:{first:%Y-%m}"
            references[evidence_id] = {**total, "metric_id": metric, "value": total[metric]}
    require(observed == set(sums), "INVALID_EXPECTED_TOTALS")
    return references


def validate_dialogues(dialogues: list[Any], evidence: dict[str, dict[str, Any]],
                       aggregates: dict[str, dict[str, Any]], *, validation: bool = False) -> None:
    require(len(dialogues) == (12 if validation else 24), "INVALID_DIALOGUE_COUNT")
    families: dict[str, str] = {}
    identities: set[str] = set()
    counts: Counter = Counter()
    for dialogue in dialogues:
        record(dialogue, {"dialogue_id", "family_id", "category", "split", "caller", "turns"})
        identity = text(dialogue["dialogue_id"], 100)
        require(identity not in identities, "DUPLICATE_DIALOGUE")
        identities.add(identity)
        family = text(dialogue["family_id"], 100)
        split = text(dialogue["split"], 20)
        category = text(dialogue["category"], 30)
        require(split in {"development", "holdout"} and category in CATEGORIES, "INVALID_SPLIT")
        require(family not in families or families[family] == split, "SPLIT_LEAKAGE")
        families[family] = split
        counts[(split, category)] += 1
        caller = Caller.parse(dialogue["caller"])
        require(type(dialogue["turns"]) is list and len(dialogue["turns"]) == 4, "INVALID_TURNS")
        for turn in dialogue["turns"]:
            record(turn, {"message", "expected", "expected_tools"})
            text(turn["message"])
            tools = strings(turn["expected_tools"], 3, allow_empty=True)
            require(set(tools) <= {"search_procedures", "read_service_metrics"}, "UNKNOWN_TOOL")
            label = record(turn["expected"], {"status", "queue", "start_date", "end_date",
                                              "metric_id", "evidence_ids", "value"})
            text(label["status"], 20)
            require(label["status"] in STATUSES, "INVALID_STATUS")
            refs = strings(label["evidence_ids"], allow_empty=True)
            if label["status"] != "ANSWERED":
                require(not refs and label["value"] is None, "INVALID_LABEL")
                if tools:
                    require(label["status"] == "ABSTAIN", "INVALID_LABEL")
                    require(label["queue"] in caller.allowed_queues and label["metric_id"] in METRICS, "INVALID_LABEL")
                    interval(label["start_date"], label["end_date"])
                else:
                    require(all(label[field] is None for field in
                                ("queue", "start_date", "end_date", "metric_id")), "INVALID_LABEL")
                continue
            text(label["queue"], 30)
            require(label["queue"] in caller.allowed_queues, "SCOPE_DENIED")
            text(label["metric_id"], 60)
            require(label["metric_id"] in METRICS, "INVALID_METRIC")
            first, last = interval(label["start_date"], label["end_date"])
            require(bool(refs), "UNKNOWN_EVIDENCE")
            for evidence_id in refs:
                source = evidence.get(evidence_id) or aggregates.get(evidence_id)
                require(source is not None, "UNKNOWN_EVIDENCE")
                require(source["queue"] == label["queue"]
                        and source["metric_id"] == label["metric_id"], "LABEL_EVIDENCE_MISMATCH")
                if evidence_id in aggregates:
                    require(source["start_date"] == label["start_date"]
                            and source["end_date"] == label["end_date"]
                            and integer(label["value"]) == source["value"], "AGGREGATE_MISMATCH")
                    require("read_service_metrics" in tools, "INVALID_LABEL")
                else:
                    require(day(source["effective_from"]) <= first
                            and last <= day(source["effective_to"]), "STALE_EVIDENCE")
                    require("search_procedures" in tools, "INVALID_LABEL")
            required_tools = (["search_procedures"] if any(ref in evidence for ref in refs) else []) + (
                ["read_service_metrics"] if any(ref in aggregates for ref in refs) else [])
            require(tools == required_tools and (any(ref in aggregates for ref in refs) or label["value"] is None),
                    "INVALID_LABEL")
    require(len(families) == (6 if validation else 12), "INVALID_FAMILY_COUNT")
    require(all(counts[(split, category)] == 2 for split in ("development", "holdout")
                if not validation or split == "holdout" for category in CATEGORIES)
            and (not validation or all(row["split"] == "holdout" for row in dialogues)), "INVALID_SPLIT_COUNTS")


def validate_fixture_directory(root: Path = FIXTURES) -> tuple[dict, dict]:
    validate_catalog(load_json(root / "metrics.json"))
    evidence = validate_procedures(load_json(root / "procedures.json"))
    with (root / "daily.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for field in {"case_count", *METRICS}:
            raw = row.get(field)
            require(type(raw) is str and raw.isascii() and raw.isdecimal(), "INVALID_INTEGER")
            row[field] = int(raw)
    aggregates = validate_daily(rows, load_json(root / "expected-totals.json"))
    dialogues = [json.loads(line) for line in (root / "dialogues.jsonl").read_text(encoding="utf-8").splitlines()]
    validate_dialogues(dialogues, evidence, aggregates)
    sample = load_json(root / "retrieval-sample.json")
    validate_retrieval_sample(sample)
    require(set(sample["reference_context_ids"]) <= evidence.keys()
            and set(sample["retrieved_context_ids"]) <= evidence.keys(), "UNKNOWN_EVIDENCE")
    for evidence_id, context in zip(sample["retrieved_context_ids"], sample["retrieved_contexts"]):
        require(evidence[evidence_id]["text"] == context, "CONTEXT_MISMATCH")
    manifest = load_json(root / "manifest.json")
    record(manifest, {"version", "sha256"})
    require(type(manifest["version"]) is int and manifest["version"] == 1, "INVALID_VERSION")
    names = {"metrics.json", "procedures.json", "daily.csv", "expected-totals.json",
             "dialogues.jsonl", "retrieval-sample.json"}
    record(manifest["sha256"], names)
    for name in names:
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        require(manifest["sha256"][name] == digest, "FIXTURE_DIGEST_MISMATCH")
    return evidence, aggregates


def evaluation_cases(root: Path = FIXTURES) -> dict[str, list[dict[str, Any]]]:
    evidence, aggregates = validate_fixture_directory(root)
    manifest = load_json(root / "validation-v2.manifest.json")
    record(manifest, {"version", "authored_before_runtime_revision", "method", "sha256"})
    require(manifest["version"] == 2, "INVALID_VERSION")
    record(manifest["sha256"], {"validation-v2.jsonl", "reference-errata.json"})
    for name, expected in manifest["sha256"].items():
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, "FIXTURE_DIGEST_MISMATCH")
    original = [json.loads(line) for line in (root / "dialogues.jsonl").read_text().splitlines()]
    fresh = [json.loads(line) for line in (root / "validation-v2.jsonl").read_text().splitlines()]
    require(not ({row["family_id"] for row in original} & {row["family_id"] for row in fresh}), "SPLIT_LEAKAGE")
    require(not ({turn["message"] for row in original for turn in row["turns"]} &
                 {turn["message"] for row in fresh for turn in row["turns"]}), "DUPLICATE_VALIDATION_INPUT")
    validate_dialogues(fresh, evidence, aggregates, validation=True)
    errata = load_json(root / "reference-errata.json")
    record(errata, {"version", "reason", "corrections"})
    require(errata["version"] == 1 and type(errata["corrections"]) is list, "INVALID_ERRATA")
    by_id = {row["dialogue_id"]: row for row in original}
    seen = set()
    for item in errata["corrections"]:
        record(item, {"dialogue_id", "turn_index", "expected", "expected_tools"})
        identity, index = item["dialogue_id"], integer(item["turn_index"], maximum=3)
        require(identity in by_id and (identity, index) not in seen, "INVALID_ERRATA")
        seen.add((identity, index))
        by_id[identity]["turns"][index].update(expected=item["expected"], expected_tools=item["expected_tools"])
    validate_dialogues(original, evidence, aggregates)
    return {"development": [row for row in original if row["split"] == "development"],
            "regression": [row for row in original if row["split"] == "holdout"], "holdout": fresh}


if __name__ == "__main__":
    evaluation_cases()
    print("Validated 12 procedures, 122 daily records, and 24 dialogues (12 development, 12 holdout).")
    print("Validated 12 fresh validation dialogues and versioned reference errata.")
