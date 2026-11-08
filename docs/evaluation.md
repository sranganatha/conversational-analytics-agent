# Conversational evaluation

The evaluator compares the current-message-only baseline and conversational agent
using the same pinned model, source data, tools, and prompts. Only history and saved
selection differ. Each dialogue/configuration/repetition has a new temporary session
database. Expected labels are attached after execution and never enter model requests.

## Run

```sh
make test-container
make calibrate-judge
make evaluate-development
make evaluate-ragas
make model-down
```

These commands use Make and Podman. The evaluation image adds hash-pinned Ragas
0.4.3 and its dependencies separately from the chat image. Image builds download
wheels; offline tests run without container networking. Live evaluation communicates
with Ollama on the Compose network. No host packages or cloud credentials are needed.
LangChain Community 0.4.1 is pinned because 0.4.2 removed a module Ragas imports.

Calibration runs twelve hand-labeled development answers, including six unsupported
controls. Several controls retain valid citation IDs while changing a number or rule.
All twelve must agree with the hand labels for calibration to pass. Disagreements and
invalid outputs remain in the report. A failed calibration does not silently select
another judge or prevent recording the experiment; it limits the final verdict.

Development runs twelve paired four-turn dialogues once. The holdout command requires
completed calibration and development artifacts from the exact current source/configuration.
It writes a freeze manifest before the first holdout run, then runs the twelve paired
holdout dialogues three times. Configuration fingerprints include source files,
dependency locks, model/policy/calibration configuration, and every fixture file.
Changing these inputs invalidates previous prerequisites. Use a separate output
directory for a deliberately new experiment rather than deleting its history.

The JSON report checkpoints after each completed dialogue. An interrupted run remains
`complete: false`; it cannot establish a comparison verdict. A rerun starts from the
beginning and replaces that output file. Archive the output directory first if the
previous attempt must be retained. There is no automatic retry, resume, prompt tuning,
or answer replacement.

## Measurements

| Measurement | Inputs and interpretation |
|---|---|
| Independent checks | Expected status, resolved queue/date/metric, required current citations, exact aggregate value and numeric-token presence |
| Scope/version checks | Actual receipt arguments, caller queues, evidence scope and effective dates; no model judgment |
| Ragas ID precision/recall | Retrieved procedure IDs versus independent reference IDs; includes all returned passages, not only cited passages |
| Ragas tool-call accuracy | Whole dialogue with observed tool attempts, names, argument values, and order |
| Ragas faithfulness | Each answered turn against the current evidence records available to the composer |
| Operational metadata | Actual model/judge usage and timings; missing usage and monetary cost remain unknown |

Ragas 0.4.3 exposes ID-based retrieval metrics through its sample API. Tool-call and
faithfulness metrics use the collections API. No legacy LLM wrapper is used. Search
wording has no single expected phrasing, so it is excluded from tool-argument matching;
queue/date arguments and metric IDs are retained. Raw requests remain in the transcript.
The dialogue metric compares the ordered call sequence; independent per-turn checks
also retain turn boundaries so a correct call made on the wrong turn cannot count as
an exact successful turn.
Faithfulness uses statement extraction followed by entailment checking. Missing,
changed, or non-finite judge claims become explicit errors, with no repair retry.

Empty retrieval has undefined precision and zero recall when references exist.
It is recorded rather than dropped. Clarifications and abstentions are excluded from
faithfulness only; their status agreement, incorrect abstentions, and errors remain in
the full turn counts. Per-dialogue records preserve paired results rather than hiding
them behind a single mean.

A numeric failure means an answered turn did not fulfill its independently labeled
count request. This includes a missing aggregate, wrong scope/period/metric, missing
required citation, omitted count, or unsupported numeric token. It does not mean every
failure was an arithmetic mistake. A procedure-only answer to a count question can
be faithful to its retrieved text while failing both the task and numeric checks.

## Decision and limits

The frozen policy is in [evaluation.json](../config/evaluation.json). Candidate scope
or numeric failures produce `REJECTED`. Missing runs, runtime/judge errors, or failed
calibration produce `INSUFFICIENT_EVIDENCE`. With complete evidence, an unsupported
candidate answer rejects the candidate. `IMPROVED` requires more exact successful
turns and no decrease in status matches or fully faithful answer count in every
repetition. Otherwise the result is `NO_CLEAR_GAIN`. A negative result is a valid
experimental outcome.

The judge uses the same Qwen model weights as the answer generator, with separate
Ragas prompts. Calibration does not eliminate correlated errors. Numeric-token checks
cannot prove that a number plays the right semantic role. Valid citations cannot prove
that prose is supported. The corpus is small and synthetic, and model calls are
deterministic by configuration; repeated runs probe execution variation without
establishing population-level significance. None of these scores grants runtime
authority or overrides deterministic scope checks.
