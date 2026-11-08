# Conversational evaluation

The evaluator compares a current-message-only baseline and conversational agent using
identical model, prompts, tools, source data, and budgets. Only validated conversation
selection and task intent differ. Each dialogue/configuration/repetition has a fresh
temporary session database. Reference labels are attached after execution and never
enter agent requests.

## Run

```sh
make test-container
make calibrate-judge EVALUATION_OUTPUT=artifacts/local-run
make evaluate-development EVALUATION_OUTPUT=artifacts/local-run
make evaluate-regression EVALUATION_OUTPUT=artifacts/local-run
make evaluate-ragas EVALUATION_OUTPUT=artifacts/local-run
make model-down
```

Commands use Make and Podman, with no host packages or cloud credentials. The separate
evaluation image pins Ragas 0.4.3 and compatible dependencies. Container tests disable
networking; live evaluation uses the private Ollama network. LangChain Community 0.4.1
is pinned because 0.4.2 removed a module imported by Ragas.

The commands above write `artifacts/local-run/`, preserving the checked-in evidence.
Use the same output directory for every stage. Without an override, evaluation commands
write `artifacts/task-contracts-v2/`, which contains the corrected recorded comparison.
Original rejected reports remain at the artifact root. Archive previous attempts before
reusing an output directory. A rerun starts from the beginning, not from a favorable
subset. For a separate smoke transcript, use
`make verify-model VERIFY_OUTPUT=artifacts/local-run`.

## Data and prerequisites

- Twelve original development dialogues remain development data.
- The twelve inspected original holdout dialogues are now regression data.
- Two versioned reference errata correct missing-period abstentions that legitimately
  require availability reads. They change expected tool metadata and resolved arguments,
  not source facts or the original files. The model never receives errata.
- Twelve fresh four-turn dialogues in six author-frozen families form the new holdout.
  Their IDs and exact inputs are disjoint from the original corpus. The fixture author
  also implemented the correction; this is not an independently blind benchmark, and
  disjoint IDs do not prove semantic novelty.

The fresh inputs and labels were committed before the runtime correction. Their manifest
binds fixture identity. A serialization correction represented single-queue permissions
as arrays without changing questions or expected facts. See the
[data contract](data-contract.md) for supported scenarios.

Calibration uses twenty-four hand-labeled development answers: twelve original citation
and number controls plus twelve representative follow-up and structured-record controls.
There are twelve supported and twelve unsupported answers. All must match to pass. Record
invalid outputs and disagreements without choosing another judge silently. This finite
calibration does not eliminate same-weight judge bias.

Development and regression each run twelve paired dialogues once. Holdout requires both
completed reports and calibration from the exact current runtime/configuration. It
writes a freeze manifest before running twelve paired dialogues three times. Fingerprints
include runtime source, model/policy/calibration configuration, locks, and all fixtures.
Changing those inputs requires matching new prerequisites. Only completed fresh holdout
receives the final comparison verdict.

Reports checkpoint after completed dialogues. An interrupted run remains incomplete and
cannot establish a verdict. No automatic run resume, transport retry, prompt tuning, or
fixture-answer replacement occurs. Runtime semantic repair is separate: one rejected
action or claim per stage can receive a visible correction generation inside the same
four-call/60-second turn budget. Judge calls are not repaired or retried.

## Measurements

| Measurement | Inputs and interpretation |
|---|---|
| Independent status/state checks | Required outcome, queue, dates, metric, citations, and per-turn tool order |
| Independent claim checks | Model claims versus reference count/procedure facts: exact ID, role, value, and unit |
| Scope/version checks | Executed arguments, caller queues, evidence scope, and effective dates |
| Ragas ID precision/recall | All returned procedure IDs versus independent passage references |
| Ragas tool-call accuracy | Ordered actual dialogue calls with scope/date/metric arguments |
| Ragas faithfulness | Rendered answer versus exact current evidence records |
| Operational metadata | Actual usage, timings, rejected proposals, repairs, and explicit missing values |

Ragas ID metrics use its sample API; tool and faithfulness metrics use collections.
No legacy LLM wrapper is used. Search wording has no single required phrasing, so it
is excluded from argument comparison. Actual queries remain in the transcript. Ragas
compares ordered calls across the dialogue; independent per-turn checks also catch a
correct call made on the wrong turn.

Typed claims are checked twice for different purposes. Runtime validation compares the
model output with current tool evidence before rendering. Independent evaluation uses
separate reference IDs, monthly totals, and procedure thresholds, not the runtime's
claimed verdict. Count and deadline roles cannot be exchanged merely because a number
appears somewhere in context. This protects the bounded structured answer vocabulary;
it does not establish unrestricted natural-language correctness.

For faithfulness, the judge receives a standalone question derived from the actual
resolved request, not the reference label. The original user message remains in the
report. This prevents follow-up instructions such as "switch queues" from being
misread as claims made by the answer. Task and state correctness still use the original
independent references and can reject an answer even when faithfulness is perfect.

Structured evidence has a readable factual projection with exact source records
retained alongside it. Procedure text is preserved verbatim, and date ranges are not
expanded. These inputs and the judge's generated claims/verdicts are recorded. No
generated judge claim is dropped to improve a score. The
[input diagnostics](../artifacts/task-contracts-v2/judge-input-diagnostics.json)
retain all nine non-perfect preflight candidate scores that exposed the adapter issue.

Faithfulness decomposes answers into statements and judges entailment. Missing, changed,
late, or non-finite judge results are errors. Empty retrieval has undefined precision
and zero recall when references exist. Clarifications and abstentions are excluded only
from faithfulness; all statuses, errors, and missing results remain in full denominators.
Per-dialogue and per-repetition records preserve pairing and coverage.

A numeric-task failure includes missing count evidence, omitted counts, wrong state,
incorrect citations, or unsupported numerical content, not just arithmetic mistakes.
A true deadline can be faithful to a procedure while failing a requested count task.

## Decision and limits

The frozen policy is in [evaluation.json](../config/evaluation.json). Any candidate
scope, numeric-task, or independent typed-claim failure produces `REJECTED`. Missing
runs, runtime/judge errors, or failed calibration produce `INSUFFICIENT_EVIDENCE`.
With complete evidence, an unsupported candidate answer rejects the candidate.
`IMPROVED` requires more exact successes and no decrease in status agreement or fully
faithful answer count in every repetition. Otherwise the result is `NO_CLEAR_GAIN`.
The claim gate strengthens the original policy; it does not lower a passing threshold.

The judge uses the same pinned Qwen weights as answer generation with separate Ragas
prompts. Calibration cannot eliminate correlated errors. Source facts, task vocabulary,
and validation families are small and synthetic. Repetitions use fixed generation
settings and are not independent statistical samples. Scores grant no runtime authority
and cannot override deterministic access or claim checks.
