"""Owner-bound sessions and append-only tool receipts in SQLite."""

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .contracts import (
    MAX_TOOL_CALLS, METRICS, Caller, ContractError, Session, ToolCall, TurnRequest,
    record, require, text,
)
from .tools import EvidenceTools, canonical

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY, owner TEXT NOT NULL, version INTEGER NOT NULL,
    turn_count INTEGER NOT NULL, expires_at TEXT NOT NULL, state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts (receipt_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS turns (
    session_id TEXT NOT NULL REFERENCES sessions(session_id), version INTEGER NOT NULL,
    request TEXT NOT NULL, receipt_ids TEXT NOT NULL, PRIMARY KEY (session_id, version)
);
CREATE TRIGGER IF NOT EXISTS receipts_no_update BEFORE UPDATE ON receipts
BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
CREATE TRIGGER IF NOT EXISTS receipts_no_delete BEFORE DELETE ON receipts
BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
CREATE TRIGGER IF NOT EXISTS turns_no_update BEFORE UPDATE ON turns
BEGIN SELECT RAISE(ABORT, 'immutable turn'); END;
CREATE TRIGGER IF NOT EXISTS turns_no_delete BEFORE DELETE ON turns
BEGIN SELECT RAISE(ABORT, 'immutable turn'); END;
"""


def _session(row: sqlite3.Row) -> Session:
    return Session.parse({key: row[key] for key in
                          ("session_id", "owner", "version", "turn_count", "expires_at")})


def _state(payload: str) -> dict[str, Any]:
    try:
        state = record(json.loads(payload), {"selection", "active_evidence"})
        if state["selection"] is not None:
            selection = record(state["selection"], {"queue", "start_date", "end_date", "metric_id"})
            metric = selection["metric_id"]
            arguments = {key: selection[key] for key in ("queue", "start_date", "end_date")}
            if metric is None:
                ToolCall.parse({"name": "search_procedures", "arguments": {**arguments, "query": "state"}},
                               Caller("state", ("intake", "review")))
            else:
                ToolCall.parse({"name": "read_service_metrics", "arguments": {**arguments, "metric_id": metric}},
                               Caller("state", ("intake", "review")))
        require(type(state["active_evidence"]) is dict and len(state["active_evidence"]) <= 20,
                "INVALID_SESSION_STATE")
        require(state["selection"] is not None or not state["active_evidence"], "INVALID_SESSION_STATE")
        for evidence_id, evidence in state["active_evidence"].items():
            text(evidence_id, 200)
            record(evidence, {"metric_id", "receipt_id"})
            text(evidence["receipt_id"], 64)
            require(evidence["metric_id"] is None or
                    (type(evidence["metric_id"]) is str and evidence["metric_id"] in METRICS),
                    "INVALID_SESSION_STATE")
        return state
    except (ValueError, TypeError) as exc:
        raise ContractError("INVALID_SESSION_STATE") from exc


def _advance(state: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    arguments = receipt["arguments"]
    selection = {key: arguments[key] for key in ("queue", "start_date", "end_date")}
    selection["metric_id"] = arguments.get("metric_id")
    previous = state["selection"]
    active = dict(state["active_evidence"])
    if (previous is None or any(previous[key] != selection[key] for key in
                                ("queue", "start_date", "end_date"))
            or receipt["tool_name"] == "search_procedures"
            or (previous["metric_id"] is not None and previous["metric_id"] != selection["metric_id"])):
        active = {}
    metric_id = selection["metric_id"]
    if metric_id is not None:
        active = {key: value for key, value in active.items()
                  if value["metric_id"] in (None, metric_id)}
    if receipt["result"]["status"] != "OK":
        return {"selection": selection, "active_evidence": {}}
    for evidence in receipt["result"]["evidence"] + receipt["result"].get("threshold_evidence", []):
        if metric_id is None or evidence["metric_id"] in (None, metric_id):
            active[evidence["evidence_id"]] = {"metric_id": evidence["metric_id"],
                                               "receipt_id": receipt["receipt_id"]}
    return {"selection": selection, "active_evidence": active}


class SessionStore:
    def __init__(self, path: Path):
        self.path = path
        with closing(self._connect()) as database:
            database.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        database = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        return database

    def create(self, caller: Caller, now: datetime) -> Session:
        require(now.tzinfo is not None and now.utcoffset() is not None, "INVALID_TIMESTAMP")
        session = Session.parse({"session_id": uuid4().hex, "owner": caller.subject,
                                 "version": 0, "turn_count": 0,
                                 "expires_at": (now + timedelta(hours=1)).isoformat()})
        with closing(self._connect()) as database:
            database.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
                             (session.session_id, session.owner, 0, 0, session.expires_at.isoformat(),
                              canonical({"selection": None, "active_evidence": {}})))
        return session

    @staticmethod
    def _load(database: sqlite3.Connection, session_id: str, caller: Caller) -> sqlite3.Row:
        row = database.execute("SELECT * FROM sessions WHERE session_id = ? AND owner = ?",
                               (session_id, caller.subject)).fetchone()
        require(row is not None, "SESSION_DENIED")
        return row

    @staticmethod
    def _receipt(database: sqlite3.Connection, receipt_id: str, caller: Caller) -> dict[str, Any]:
        row = database.execute("SELECT payload FROM receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
        require(row is not None, "UNKNOWN_EVIDENCE")
        try:
            receipt = json.loads(row["payload"])
            require(hashlib.sha256(canonical(receipt).encode()).hexdigest() == receipt_id,
                    "RECEIPT_DIGEST_MISMATCH")
        except (ValueError, TypeError) as exc:
            raise ContractError("RECEIPT_DIGEST_MISMATCH") from exc
        ToolCall.parse({"name": receipt["tool_name"], "arguments": receipt["arguments"]}, caller)
        return {"receipt_id": receipt_id, **receipt}

    def execute(self, value: Any, caller: Caller, calls: list[Any], now: datetime,
                tools: EvidenceTools) -> dict[str, Any]:
        request = TurnRequest.parse(value)
        require(type(calls) is list and 0 < len(calls) <= MAX_TOOL_CALLS, "TOOL_LIMIT")
        parsed = [ToolCall.parse(call, caller) for call in calls]
        calls = [{"name": call.name, "arguments": call.arguments} for call in parsed]
        with closing(self._connect()) as database:
            try:
                database.execute("BEGIN IMMEDIATE")
                row = self._load(database, request.session_id, caller)
                session = _session(row)
                session.authorize(caller, request.expected_version, now)
                state = _state(row["state"])
                receipts = []
                for call in calls:
                    receipt = tools.execute(call, caller)
                    payload = canonical({key: val for key, val in receipt.items() if key != "receipt_id"})
                    database.execute("INSERT OR IGNORE INTO receipts VALUES (?, ?)",
                                     (receipt["receipt_id"], payload))
                    receipts.append(self._receipt(database, receipt["receipt_id"], caller))
                    state = _advance(state, receipts[-1])
                version = session.version + 1
                database.execute("INSERT INTO turns VALUES (?, ?, ?, ?)",
                                 (session.session_id, version, canonical(asdict(request)),
                                  canonical([receipt["receipt_id"] for receipt in receipts])))
                database.execute("UPDATE sessions SET version = ?, turn_count = ?, state = ? "
                                 "WHERE session_id = ? AND version = ?",
                                 (version, session.turn_count + 1, canonical(state), session.session_id,
                                  session.version))
                database.commit()
                return {"session_id": session.session_id, "version": version,
                        "state": state, "receipts": receipts}
            except sqlite3.OperationalError as exc:
                database.rollback()
                if exc.sqlite_errorcode in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                    raise ContractError("SESSION_BUSY") from exc
                raise
            except BaseException:
                database.rollback()
                raise

    def get(self, session_id: str, caller: Caller, now: datetime) -> dict[str, Any]:
        text(session_id, 100)
        with closing(self._connect()) as database:
            database.execute("BEGIN")
            row = self._load(database, session_id, caller)
            session = _session(row)
            require(now.tzinfo is not None and now.utcoffset() is not None, "INVALID_TIMESTAMP")
            require(now < session.expires_at, "SESSION_EXPIRED")
            history = []
            for turn in database.execute("SELECT * FROM turns WHERE session_id = ? ORDER BY version",
                                         (session_id,)):
                history.append({"version": turn["version"], "request": json.loads(turn["request"]),
                                "receipts": [self._receipt(database, identity, caller)
                                             for identity in json.loads(turn["receipt_ids"])]})
            return {"session": {**asdict(session), "expires_at": session.expires_at.isoformat()},
                    "state": _state(row["state"]), "turns": history}
