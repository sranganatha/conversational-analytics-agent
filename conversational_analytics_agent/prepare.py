"""Build local read-only evidence snapshots from source fixtures, without labels."""

import csv
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import duckdb

from .contracts import METRICS, QUEUES, day, integer, record, require
from .fixtures import load_json, validate_catalog, validate_procedures


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source: Path, destination: Path) -> None:
    catalog = load_json(source / "metrics.json")
    validate_catalog(catalog)
    procedures = validate_procedures(load_json(source / "procedures.json"))
    with (source / "daily.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 122, "INVALID_DAILY_COUNT")
    seen = set()
    for row in rows:
        record(row, {"service_date", "queue", "case_count", *METRICS})
        service_day = day(row["service_date"])
        require(day("2026-08-01") <= service_day < day("2026-10-01"), "INVALID_DATA_DATE")
        require(row["queue"] in QUEUES, "INVALID_QUEUE")
        key = (row["service_date"], row["queue"])
        require(key not in seen, "DUPLICATE_DAILY_RECORD")
        seen.add(key)
        for name in {"case_count", *METRICS}:
            raw = row[name]
            require(type(raw) is str and raw.isascii() and raw.isdecimal(), "INVALID_INTEGER")
            row[name] = int(raw)
            integer(row[name])
        for metric in METRICS:
            integer(row[metric], maximum=row["case_count"])
    destination.mkdir(parents=True, exist_ok=True)
    require(not any(destination.iterdir()), "SNAPSHOT_EXISTS")
    with closing(sqlite3.connect(destination / "procedures.sqlite")) as index, index:
        index.execute("CREATE TABLE procedures (evidence_id TEXT PRIMARY KEY, queue TEXT, "
                      "effective_from TEXT, effective_to TEXT, metric_id TEXT, "
                      "threshold_hours INTEGER, text TEXT)")
        index.execute("CREATE VIRTUAL TABLE procedure_search USING fts5(text)")
        for procedure in procedures.values():
            rowid = index.execute("INSERT INTO procedures VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  [procedure[key] for key in ("evidence_id", "queue", "effective_from",
                                   "effective_to", "metric_id", "threshold_hours", "text")]).lastrowid
            index.execute("INSERT INTO procedure_search(rowid, text) VALUES (?, ?)",
                          (rowid, procedure["text"]))
    database = duckdb.connect(str(destination / "metrics.duckdb"))
    try:
        database.execute("CREATE TABLE daily (service_date DATE, queue VARCHAR, case_count BIGINT, "
                         "first_response_breaches BIGINT, resolution_breaches BIGINT, "
                         "PRIMARY KEY (service_date, queue))")
        database.executemany("INSERT INTO daily VALUES (?, ?, ?, ?, ?)", [
            [row[name] for name in ("service_date", "queue", "case_count",
                                   "first_response_breaches", "resolution_breaches")]
            for row in rows])
    finally:
        database.close()
    metadata = {"corpus_digest": digest(source / "procedures.json"),
                "dataset_digest": digest(source / "daily.csv"),
                "catalog_digest": digest(source / "metrics.json"),
                "index_digest": digest(destination / "procedures.sqlite"),
                "database_digest": digest(destination / "metrics.duckdb"),
                "catalog": catalog}
    (destination / "metadata.json").write_text(json.dumps(metadata, sort_keys=True) + "\n",
                                               encoding="utf-8")


if __name__ == "__main__":
    require(len(sys.argv) == 3, "INVALID_ARGUMENTS")
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
