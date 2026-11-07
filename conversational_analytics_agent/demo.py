"""Run fixed tool requests to demonstrate evidence and session behavior."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from .contracts import Caller, ContractError, require
from .store import SessionStore
from .tools import EvidenceTools


def main() -> None:
    caller = Caller.parse({"subject": "demo-analyst", "allowed_queues": ["intake", "review"]})
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    tools = EvidenceTools()
    with TemporaryDirectory() as temporary:
        store = SessionStore(Path(temporary) / "sessions.sqlite")
        session = store.create(caller, now)
        arguments = {"queue": "intake", "start_date": "2026-09-01", "end_date": "2026-10-01"}
        search = {"name": "search_procedures", "arguments": {**arguments, "query": "first response"}}
        metric = {"name": "read_service_metrics", "arguments": {
            **arguments, "metric_id": "first_response_breaches"}}
        version = 0

        def execute(message, calls):
            nonlocal version
            result = store.execute({"session_id": session.session_id, "expected_version": version,
                                    "message": message}, caller, calls, now, tools)
            version = result["version"]
            return result

        result = execute("Read the September intake rule and first-response breach count.", [search, metric])
        aggregate = result["receipts"][-1]["result"]["evidence"][0]
        require(aggregate["value"] == 120, "DEMO_MISMATCH")
        require("intake-response-09" in result["state"]["active_evidence"], "DEMO_MISMATCH")
        first_id = aggregate["evidence_id"]
        print("September intake: first-response rule = 2 hours; breaches = 120.")

        metric["arguments"].update(start_date="2026-08-01", end_date="2026-09-01")
        result = execute("Read the August intake count.", [metric])
        require(result["receipts"][0]["result"]["evidence"][0]["value"] == 93
                and first_id not in result["state"]["active_evidence"], "DEMO_MISMATCH")
        print("August intake: breaches = 93; September evidence is no longer active.")

        metric["arguments"]["queue"] = "review"
        result = execute("Read the August review count.", [metric])
        require(result["receipts"][0]["result"]["evidence"][0]["value"] == 62, "DEMO_MISMATCH")
        print("August review: first-response breaches = 62; intake evidence is no longer active.")

        metric["arguments"]["metric_id"] = "resolution_breaches"
        result = execute("Read review resolution breaches for August.", [metric])
        receipt = result["receipts"][0]
        require(receipt["result"]["evidence"][0]["value"] == 31, "DEMO_MISMATCH")
        require(tools.execute(metric, caller)["receipt_id"] == receipt["receipt_id"], "DEMO_MISMATCH")
        print("August review: resolution breaches = 31; identical reads have the same receipt digest.")

        restricted = Caller.parse({"subject": "demo-analyst", "allowed_queues": ["intake"]})
        try:
            tools.execute(metric, restricted)
        except ContractError as exc:
            require(exc.code == "SCOPE_DENIED", "DEMO_MISMATCH")
        else:
            raise ContractError("DEMO_MISMATCH")
        restored = SessionStore(Path(temporary) / "sessions.sqlite").get(session.session_id, caller, now)
        require(restored["session"]["version"] == 4 and len(restored["turns"]) == 4, "DEMO_MISMATCH")
        print("Unauthorized read denied; four turns and their receipts survive store reopen.")
        print("PASS: fixed tool requests; no model calls or conversational inference.")


if __name__ == "__main__":
    main()
