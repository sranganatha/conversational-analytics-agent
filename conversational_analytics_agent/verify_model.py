"""Record a bounded real-model smoke run without reading holdout labels."""

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from .agent import ConversationAgent
from .contracts import Caller, ContractError
from .fixtures import load_json
from .model import OllamaModel
from .store import SessionStore
from .tools import EvidenceTools


def verify(output: Path) -> bool:
    root = Path(__file__).resolve().parent.parent
    config = load_json(root / "config" / "model.json")
    model = OllamaModel(os.environ.get("OLLAMA_URL", "http://ollama:11434"), config["name"])
    report = {"execution_mode": "ollama", "timestamp": datetime.now(timezone.utc).isoformat(),
              "model": config, "python": platform.python_version(), "langgraph": version("langgraph"),
              "cases": [], "preflight_error": None}
    sources = [*sorted((root / "conversational_analytics_agent").glob("*.py")), root / "config" / "model.json",
               root / "requirements.lock"]
    report["code_digest"] = hashlib.sha256(b"".join(
        str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() for path in sources)).hexdigest()
    try:
        model.preflight(config["digest"])
        tools = EvidenceTools()
        caller = Caller.parse({"subject": "verification-analyst", "allowed_queues": ["intake", "review"]})
        suites = [
            ("conversational", [
                ("For the intake queue in September 2026, what is the first-response rule?", "ANSWERED", None),
                ("How many cases exceeded it that month?", "ANSWERED", 120),
                ("And the previous month?", "ANSWERED", 93),
                ("What about the review queue?", "ANSWERED", 62)]),
            ("conversational", [("How many review cases were overdue in September 2026?", "CLARIFY", None)]),
            ("baseline", [
                ("For the intake queue in September 2026, what is the first-response rule?", "ANSWERED", None),
                ("How many cases exceeded it that month?", "CLARIFY", None)]),
            ("conversational", [
                ("Show both the first-response rule and count for intake in September 2026.", "ANSWERED", 120),
                ("Predict next month's count.", "ABSTAIN", None),
                ("Only the count, for the previous month.", "ANSWERED", 93)])]
        with TemporaryDirectory() as temporary:
            store = SessionStore(Path(temporary) / "sessions.sqlite")
            for suite_index, (mode, cases) in enumerate(suites):
                session = store.create(caller, datetime.now(timezone.utc))
                agent = ConversationAgent(model, tools, store, mode=mode)
                current_version = 0
                for message, expected_status, expected_value in cases:
                    case = {"suite": suite_index, "mode": mode, "message": message,
                            "expected_status": expected_status, "expected_value": expected_value}
                    try:
                        result = agent.run({"session_id": session.session_id, "expected_version": current_version,
                                            "message": message}, caller)
                        current_version = result["version"]
                        values = [item.get("value") for receipt in result["receipts"]
                                  for item in receipt["result"]["evidence"]]
                        case["passed"] = (result["answer"]["status"] == expected_status
                                          and (expected_value is None or expected_value in values))
                        case["result"] = result
                    except ContractError as exc:
                        case.update(passed=False, error_code=exc.code)
                    report["cases"].append(case)
                    print(f"{mode}: {message} -> {'PASS' if case['passed'] else 'FAIL'}", flush=True)
    except ContractError as exc:
        report["preflight_error"] = exc.code
    report["passed"] = report["preflight_error"] is None and len(report["cases"]) == 10 and all(
        case["passed"] for case in report["cases"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "model-verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Local-model verification", "", f"Execution: {report['execution_mode']}",
             f"Model: `{config['name']}`", f"Model digest: `{config['digest']}`",
             f"Code digest: `{report['code_digest']}`", "", "| Mode | Message | Result |", "|---|---|---|"]
    lines += [f"| {case['mode']} | {case['message']} | {'PASS' if case['passed'] else 'FAIL'} |" for case in report["cases"]]
    lines += ["", f"Preflight error: {report['preflight_error'] or 'none'}.",
              "", "This ten-turn smoke run is not the held-out comparison or a Ragas evaluation.",
              "Full visible outputs, tool receipts, failures, usage, and timings are in the JSON report."]
    (output / "model-verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report["passed"]


if __name__ == "__main__":
    raise SystemExit(0 if verify(Path(sys.argv[1] if len(sys.argv) == 2 else "artifacts")) else 1)
