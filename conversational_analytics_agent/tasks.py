"""Task requirements and typed evidence claims, independent of model transport."""

import re
from typing import Any

from .contracts import integer, record, require, text

TASK_TOOLS = {"RULE": ["search_procedures"], "COUNT": ["read_service_metrics"],
              "BOTH": ["search_procedures", "read_service_metrics"]}


def unsupported_request(message: str) -> bool:
    value = message.lower()
    return bool(re.search(
        r"\b(income|phone|phones|email|emails|predict|forecast)\b"
        r"|\b(which|list|individual)\b.{0,40}\bcustomers?\b"
        r"|\bnext month\b|\bwhat will\b"
        r"|\b(ignore|override)\b.{0,60}\b(permission|permissions|restriction|restrictions)\b"
        r"|\b(administrator|admin) grant\b|\ball queues (are )?allowed\b"
        r"|\b(drafts|conflicts?)\b.{0,80}\b(disagree|choose|lenient)\b", value))


def resolve_task(message: str, previous: str | None) -> str | None:
    value = message.lower()
    count = bool(re.search(r"\b(count|counts|total|totals|aggregate|aggregates|how many)\b", value))
    rule = bool(re.search(r"\b(rule|rules|deadline|deadlines|threshold|thresholds)\b", value))
    both = count and rule and bool(re.search(
        r"\bboth\b|\b(rule|rules|deadline|deadlines|threshold|thresholds)\b.{0,60}\band\b.{0,30}"
        r"\b(count|counts|total|totals|how many)\b|\bcount\b.{0,30}\band\b.{0,30}\b(rule|deadline)\b", value))
    if both:
        return "BOTH"
    if count:
        return "COUNT"
    if rule:
        return "RULE"
    if re.search(r"\bbreach(es)?\b", value):
        return "COUNT"
    if re.search(r"\b(it|its|them|same|that|earlier|previous|prior|instead|intake|review|response|resolution)\b"
                 r"|\b(january|february|march|april|may|june|july|august|september|october|november|december)\b"
                 r"|\b\d{4}-\d{2}\b", value):
        return previous
    return None


def required_claims(plan: dict[str, Any], context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims = []
    for item in context:
        if plan["intent"] in {"RULE", "BOTH"} and item.get("threshold_hours") is not None:
            claims.append({"kind": "deadline", "evidence_id": item["evidence_id"],
                           "value": item["threshold_hours"], "unit": "hours"})
        if plan["intent"] in {"COUNT", "BOTH"} and "value" in item:
            claims.append({"kind": "count", "evidence_id": item["evidence_id"],
                           "value": item["value"], "unit": "cases"})
    required_kinds = {"deadline", "count"} if plan["intent"] == "BOTH" else {
        "count" if plan["intent"] == "COUNT" else "deadline"}
    require({item["kind"] for item in claims} == required_kinds and len(claims) == len(required_kinds),
            "REQUIRED_EVIDENCE_MISSING")
    return claims


def grounded_answer(value: Any, plan: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    data = record(value, {"status", "claims"})
    require(type(data["status"]) is str and data["status"] in {"ANSWERED", "ABSTAIN"}, "MODEL_SCHEMA_ERROR")
    require(type(data["claims"]) is list and len(data["claims"]) <= 2, "CLAIM_MISMATCH")
    if data["status"] == "ABSTAIN":
        require(not data["claims"], "CLAIM_MISMATCH")
        return {"status": "ABSTAIN", "message": "The model could not support the requested answer.",
                "evidence_ids": [], "error_code": None}
    require(len(data["claims"]) == len(facts), "CLAIM_MISMATCH")
    by_id = {item["evidence_id"]: item for item in facts}
    seen = set()
    for claim in data["claims"]:
        record(claim, {"kind", "evidence_id", "value", "unit"})
        identity = text(claim["evidence_id"], 200)
        integer(claim["value"])
        require(identity in by_id and identity not in seen, "UNKNOWN_EVIDENCE")
        require(claim == by_id[identity], "CLAIM_MISMATCH")
        seen.add(identity)
    # Render only claims the model returned and the current tools independently support.
    metric = "first-response" if plan["metric_id"] == "first_response_breaches" else "resolution"
    pieces = []
    for claim in sorted(data["claims"], key=lambda item: item["kind"] != "deadline"):
        label = f"{metric} deadline" if claim["kind"] == "deadline" else f"{metric} breach count"
        pieces.append(f"For the {plan['queue']} queue in {plan['period']}, the {label} is "
                      f"{claim['value']} {claim['unit']}.")
    return {"status": "ANSWERED", "message": " ".join(pieces),
            "evidence_ids": [item["evidence_id"] for item in data["claims"]], "error_code": None}
