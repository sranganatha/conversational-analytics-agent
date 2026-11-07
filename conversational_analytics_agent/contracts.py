"""Boundary validation without storage, model calls, or evaluation side effects."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

QUEUES = frozenset({"intake", "review"})
METRICS = frozenset({"first_response_breaches", "resolution_breaches"})
STATUSES = frozenset({"ANSWERED", "CLARIFY", "ABSTAIN", "ERROR"})
MAX_TURNS = 6
MAX_TOOL_CALLS = 3
MAX_MESSAGE_CHARS = 1200
MAX_CONTEXT_CHARS = 8000
MAX_MODEL_CALLS = 4
TURN_TIMEOUT_SECONDS = 60


class ContractError(ValueError):
    """Stable boundary error with no untrusted payload in its message."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def record(value: Any, fields: set[str]) -> dict[str, Any]:
    require(type(value) is dict and set(value) == fields, "INVALID_FIELDS")
    return value


def text(value: Any, limit: int = MAX_MESSAGE_CHARS) -> str:
    require(type(value) is str and bool(value.strip()) and len(value) <= limit, "INVALID_TEXT")
    return value


def integer(value: Any, minimum: int = 0, maximum: int = 1_000_000) -> int:
    require(type(value) is int and minimum <= value <= maximum, "INVALID_INTEGER")
    return value


def strings(value: Any, limit: int = 20, allow_empty: bool = False) -> list[str]:
    require(type(value) is list and len(value) <= limit, "INVALID_LIST")
    require(allow_empty or bool(value), "INVALID_LIST")
    for item in value:
        text(item, 200)
    require(len(set(value)) == len(value), "DUPLICATE_VALUE")
    return value


def day(value: Any) -> date:
    text(value, 10)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("INVALID_DATE") from exc
    require(parsed.isoformat() == value, "INVALID_DATE")
    return parsed


def interval(start: Any, end: Any) -> tuple[date, date]:
    first, last = day(start), day(end)
    require(0 < (last - first).days <= 61, "INVALID_INTERVAL")
    return first, last


@dataclass(frozen=True)
class Caller:
    subject: str
    allowed_queues: tuple[str, ...]

    @classmethod
    def parse(cls, value: Any) -> "Caller":
        data = record(value, {"subject", "allowed_queues"})
        subject = text(data["subject"], 100)
        queues = strings(data["allowed_queues"], 2)
        require(set(queues) <= QUEUES, "INVALID_QUEUE")
        return cls(subject, tuple(queues))


@dataclass(frozen=True)
class Session:
    session_id: str
    owner: str
    version: int
    turn_count: int
    expires_at: datetime

    @classmethod
    def parse(cls, value: Any) -> "Session":
        data = record(value, {"session_id", "owner", "version", "turn_count", "expires_at"})
        text(data["expires_at"], 40)
        try:
            expiry = datetime.fromisoformat(data["expires_at"])
        except ValueError as exc:
            raise ContractError("INVALID_TIMESTAMP") from exc
        require(expiry.tzinfo is not None and expiry.utcoffset() is not None, "INVALID_TIMESTAMP")
        return cls(text(data["session_id"], 100), text(data["owner"], 100),
                   integer(data["version"]), integer(data["turn_count"], maximum=MAX_TURNS),
                   expiry.astimezone(timezone.utc))

    def authorize(self, caller: Caller, expected_version: int, now: datetime) -> None:
        require(self.owner == caller.subject, "SESSION_DENIED")
        integer(expected_version)
        require(self.version == expected_version, "SESSION_CONFLICT")
        require(now.tzinfo is not None and now.utcoffset() is not None, "INVALID_TIMESTAMP")
        require(now < self.expires_at, "SESSION_EXPIRED")
        require(self.turn_count < MAX_TURNS, "TURN_LIMIT")


@dataclass(frozen=True)
class TurnRequest:
    session_id: str
    expected_version: int
    message: str

    @classmethod
    def parse(cls, value: Any) -> "TurnRequest":
        data = record(value, {"session_id", "expected_version", "message"})
        return cls(text(data["session_id"], 100), integer(data["expected_version"]),
                   text(data["message"]))


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]

    @classmethod
    def parse(cls, value: Any, caller: Caller) -> "ToolCall":
        data = record(value, {"name", "arguments"})
        name = text(data["name"], 50)
        require(name in {"search_procedures", "read_service_metrics"}, "UNKNOWN_TOOL")
        fields = {"queue", "start_date", "end_date"}
        fields.add("query" if name == "search_procedures" else "metric_id")
        arguments = record(data["arguments"], fields)
        text(arguments["queue"], 30)
        require(arguments["queue"] in QUEUES, "INVALID_QUEUE")
        require(arguments["queue"] in caller.allowed_queues, "SCOPE_DENIED")
        interval(arguments["start_date"], arguments["end_date"])
        if name == "search_procedures":
            text(arguments["query"], 500)
        else:
            text(arguments["metric_id"], 60)
            require(arguments["metric_id"] in METRICS, "INVALID_METRIC")
        return cls(name, dict(arguments))


def validate_turn(value: Any, caller: Caller, available_evidence: set[str]) -> None:
    data = record(value, {"status", "message", "evidence_ids", "tool_calls", "error_code"})
    text(data["status"], 20)
    require(data["status"] in STATUSES, "INVALID_STATUS")
    text(data["message"], 4000)
    evidence = strings(data["evidence_ids"], allow_empty=True)
    require(set(evidence) <= available_evidence, "UNKNOWN_EVIDENCE")
    require(type(data["tool_calls"]) is list and len(data["tool_calls"]) <= MAX_TOOL_CALLS,
            "TOOL_LIMIT")
    for tool in data["tool_calls"]:
        ToolCall.parse(tool, caller)
    if data["status"] == "ANSWERED":
        require(bool(evidence) and data["error_code"] is None, "INVALID_ANSWER")
    elif data["status"] == "ERROR":
        text(data["error_code"], 80)
        require(not evidence, "INVALID_ANSWER")
    else:
        require(not evidence and data["error_code"] is None, "INVALID_ANSWER")


def validate_retrieval_sample(value: Any) -> None:
    """Validate saved evaluation inputs; this function does not compute Ragas scores."""
    data = record(value, {"user_input", "response", "retrieved_contexts",
                          "retrieved_context_ids", "reference", "reference_context_ids"})
    for key in ("user_input", "response", "reference"):
        text(data[key], 4000)
    ids = strings(data["retrieved_context_ids"], allow_empty=True)
    strings(data["reference_context_ids"])
    contexts = data["retrieved_contexts"]
    require(type(contexts) is list and len(contexts) == len(ids), "CONTEXT_MISMATCH")
    for context in contexts:
        text(context, MAX_CONTEXT_CHARS)
    require(sum(map(len, contexts)) <= MAX_CONTEXT_CHARS, "CONTEXT_LIMIT")
