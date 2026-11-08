"""Bounded local paired experiment; labels never enter the agent call."""

import argparse
import asyncio
import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from .agent import ConversationAgent
from .contracts import Caller, ContractError, require
from .evaluation import comparison_verdict, independent_checks, summarize
from .fixtures import evaluation_cases, load_json
from .model import OllamaModel
from .ragas_metrics import LocalJudge, dialogue_tools, judge_context, resolved_judge_question, retrieval_scores, score_faithfulness
from .store import SessionStore
from .tools import EvidenceTools, canonical

ROOT = Path(__file__).resolve().parent.parent


def fingerprints():
    paths = [*sorted((ROOT / "conversational_analytics_agent").glob("*.py")),
             *sorted((ROOT / "config").glob("*.json")), ROOT / "requirements.lock",
             ROOT / "requirements-evaluation.lock", ROOT / "Containerfile", ROOT / "Containerfile.evaluation",
             *sorted((ROOT / "fixtures").glob("*"))]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def model():
    config = load_json(ROOT / "config" / "model.json")
    client = OllamaModel(os.environ.get("OLLAMA_URL", "http://ollama:11434"), config["name"])
    client.preflight(config["digest"])
    return client


def metadata():
    policy = load_json(ROOT / "config" / "evaluation.json")
    require(all(policy[key] == value for key, value in {
        "holdout_repetitions": 3, "judge_timeout_seconds": 60, "judge_max_calls": 2,
        "calibration_required_matches": 24, "faithfulness_required_score": 1.0}.items()), "INVALID_EVALUATION_POLICY")
    return {"execution_mode": "ollama-ragas", "timestamp": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "architecture": platform.machine(),
            "source_revision": os.environ.get("SOURCE_REVISION", "unknown"), "fingerprints": fingerprints(),
            "validation_manifest": load_json(ROOT / "fixtures" / "validation-v2.manifest.json"),
            "versions": {name: version(name) for name in ("ragas", "langgraph", "duckdb")},
            "policy": policy}


async def calibrate(output):
    report = {**metadata(), "cases": [], "complete": False, "passed": False}
    client = model()
    report["model"] = dict(client.identity)
    judge = LocalJudge(client)
    cases = load_json(ROOT / "config" / "judge-calibration.json")["cases"]
    require(len(cases) == 24, "INVALID_CALIBRATION")
    for case in cases:
        question = resolved_judge_question(case["resolved_request"]) if "resolved_request" in case else case["question"]
        contexts = [judge_context(item) for item in case["context_records"]] if "context_records" in case else [case["context"]]
        result = await judge.score(question, case["answer"], contexts)
        result.update(judge_user_input=question, judge_contexts=contexts, original_user_input=case["question"])
        matched = result["state"] == "SCORED" and (result["value"] == 1) == case["supported"]
        report["cases"].append({**case, "result": result, "matched": matched})
        write_report(output / "judge-calibration.json", report)
        print(f"calibration {case['id']}: {'MATCH' if matched else 'DISAGREE/ERROR'}", flush=True)
    report.update(complete=True, passed=all(case["matched"] for case in report["cases"]))
    write_report(output / "judge-calibration.json", report)
    return report


def run_dialogue(agent, store, dialogue):
    """Execute inputs only. Expected labels are attached after generation."""
    caller = Caller.parse(dialogue["caller"])
    session = store.create(caller, datetime.now(timezone.utc))
    results = []
    current_version = 0
    for turn in dialogue["turns"]:
        try:
            outcome = agent.run({"session_id": session.session_id, "expected_version": current_version,
                                 "message": turn["message"]}, caller)
            current_version = outcome["version"]
        except ContractError as exc:
            outcome = {"answer": {"status": "ERROR", "message": "Turn failed.", "evidence_ids": [],
                                   "tool_calls": [], "error_code": exc.code}, "resolved_request": None,
                       "receipts": [], "model_calls": [], "tool_attempts": [], "elapsed_ms": 0}
        results.append(outcome)
    return results


def markdown(report):
    lines = ["# Paired conversational evaluation", "", f"Split: {report['split']}",
             f"Execution: {report['execution_mode']}", f"Complete: {report['complete']}",
             f"Verdict: **{report['verdict']}**", "", "| Repetition | Mode | Exact turns | Status matches | Faithfulness coverage | Numeric failures | Claim failures | Errors |",
             "|---|---|---|---|---|---|---|---|"]
    for rep in range(report["repetitions"]):
        for mode in ("baseline", "conversational"):
            turns = [turn for row in report["dialogues"] if row["repetition"] == rep and row["mode"] == mode
                     for turn in row["turns"]]
            summary = summarize(turns)
            lines.append(f"| {rep + 1} | {mode} | {summary['exact_successes']}/{summary['turns']} | "
                         f"{summary['status_matches']}/{summary['turns']} | "
                         f"{summary['faithfulness_scored']}/{summary['faithfulness_eligible']} | "
                         f"{summary['numeric_failures']} | {summary['claim_failures']} | {summary['statuses'].get('ERROR', 0)} |")
    lines += ["", "Faithfulness uses the same model weights as answer generation with separate Ragas prompts.",
              "Calibration disagreements and missing judge results limit conclusions. Citation IDs alone do not establish support.",
              "Exact checks cover expected state, current evidence, and numeric tokens; they do not prove prose semantics.",
              "Typed claims are also checked against independent count and procedure references, including value, role, unit, and ID.",
              "The original holdout is regression data with versioned reference errata; this holdout uses fresh author-frozen families.",
              "The fixture author also implemented the corrections. This is not an independently blind benchmark.",
              "Retrieval ID precision/recall and full-dialogue tool accuracy appear per case in the JSON report.",
              "Search wording is excluded from argument comparison; scope, dates, metric IDs, names, and order are scored.",
              "Errors remain in denominators. Clarifications and abstentions are excluded only from faithfulness.",
              "This small synthetic corpus is a reference experiment, not a population-level quality claim."]
    return "\n".join(lines) + "\n"


async def evaluate(output, split):
    cases = evaluation_cases()
    calibration = load_json(output / "judge-calibration.json")
    frozen = {"fingerprints": fingerprints(), "policy": load_json(ROOT / "config" / "evaluation.json")}
    require(calibration["fingerprints"] == frozen["fingerprints"] and calibration["complete"],
            "CALIBRATION_IDENTITY_MISMATCH")
    if split == "holdout":
        development = load_json(output / "evaluation-development.json")
        require(development["complete"] and development["fingerprints"] == frozen["fingerprints"],
                "DEVELOPMENT_REQUIRED")
        regression = load_json(output / "evaluation-regression.json")
        require(regression["complete"] and regression["fingerprints"] == frozen["fingerprints"],
                "REGRESSION_REQUIRED")
        freeze_path = output / "evaluation-freeze.json"
        if freeze_path.exists():
            require(load_json(freeze_path) == frozen, "FROZEN_CONFIGURATION_CHANGED")
        else:
            write_report(freeze_path, frozen)
    client = model()
    judge = LocalJudge(client)
    report = {**metadata(), "split": split, "repetitions": 3 if split == "holdout" else 1,
              "model": dict(client.identity), "calibration_passed": calibration["passed"],
              "dialogues": [], "complete": False, "verdict": "INSUFFICIENT_EVIDENCE"}
    path = output / f"evaluation-{split}.json"
    write_report(path, report)
    selected = cases[split]
    thresholds = {item["evidence_id"]: item["threshold_hours"] for item in
                  load_json(ROOT / "fixtures" / "procedures.json")["procedures"]}
    tools = EvidenceTools()
    for repetition in range(report["repetitions"]):
        for index, dialogue in enumerate(selected):
            # Alternate execution order to reduce systematic warm-cache order effects.
            modes = ("baseline", "conversational") if (index + repetition) % 2 == 0 else ("conversational", "baseline")
            for mode in modes:
                with TemporaryDirectory() as temporary:
                    store = SessionStore(Path(temporary) / "sessions.sqlite")
                    agent = ConversationAgent(client, tools, store, mode=mode)
                    outcomes = run_dialogue(agent, store, dialogue)
                turns = []
                for source, outcome in zip(dialogue["turns"], outcomes):
                    turn = {"message": source["message"], "expected": source["expected"],
                            "expected_tools": source["expected_tools"], "outcome": outcome}
                    turn["checks"] = independent_checks(source["expected"], outcome, Caller.parse(dialogue["caller"]), thresholds)
                    turn["checks"]["tool_order_correct"] = (
                        [attempt["call"]["name"] for attempt in outcome["tool_attempts"]] == source["expected_tools"])
                    turn["checks"]["exact_success"] &= turn["checks"]["tool_order_correct"]
                    turn["retrieval"] = await retrieval_scores(source["expected"], outcome)
                    turn["faithfulness"] = await score_faithfulness(judge, source["message"], outcome)
                    turns.append(turn)
                row = {"dialogue_id": dialogue["dialogue_id"], "split": split, "mode": mode,
                       "repetition": repetition, "turns": turns,
                       "tool_call_accuracy": await dialogue_tools(turns), "summary": summarize(turns)}
                report["dialogues"].append(row)
                write_report(path, report)
                print(f"{split} {repetition + 1} {mode} {dialogue['dialogue_id']}: "
                      f"{row['summary']['exact_successes']}/4 exact", flush=True)
    report["complete"] = True
    if split == "holdout":
        report["verdict"] = comparison_verdict(report["dialogues"], calibration["passed"], report["repetitions"])
    require(report["fingerprints"] == fingerprints(), "CONFIGURATION_CHANGED_DURING_RUN")
    write_report(path, report)
    (output / f"evaluation-{split}.md").write_text(markdown(report), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "development", "regression", "holdout"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/task-contracts-v2"))
    args = parser.parse_args()
    try:
        report = asyncio.run(calibrate(args.output) if args.action == "calibrate"
                             else evaluate(args.output, args.action))
        print("Calibration passed:" if args.action == "calibrate" else "Verdict:",
              report["passed"] if args.action == "calibrate" else report["verdict"])
    except (ContractError, FileNotFoundError) as exc:
        print(exc.code if isinstance(exc, ContractError) else "EVALUATION_PREREQUISITE_MISSING")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
