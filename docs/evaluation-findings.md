# Evaluation findings

The experiment compares the same local Qwen model and read tools with and without
conversation state. The recorded artifacts identify exact model, source, fixture,
dependency, and policy fingerprints. See [the evaluation method](evaluation.md) for
the frozen comparison rule and coverage definitions.

## Current recorded result

The corrected comparison is **IMPROVED** at runtime revision
`a3177a2618d77ce60af05eb9ad1d0f4208e2693c`. Calibration matches 24/24 labels.
Development and inspected regression each complete 96 paired turns, with 48/48 exact
candidate turns. Fresh holdout completes all 288 paired turns across three repetitions.

Each fresh repetition produces the following result:

| Configuration | Exact turns | Status matches | Faithful answers | Numeric/claim/scope failures | Runtime/judge errors |
|---|---:|---:|---:|---:|---:|
| Current-message baseline | 22/48 | 22/48 | 8/8 | 0 | 0 |
| Conversational state | 48/48 | 48/48 | 32/32 | 0 | 0 |

All answered turns receive a score. Clarifications and abstentions remain in exact
task denominators. No semantic repair was needed in the recorded development,
regression, or holdout runs; focused tests exercise rejected proposals and repairs.
All 32 frozen input fingerprints match after completion. The model and dependencies
are unchanged; the workflow and evaluation adapter were corrected together.

See the [current holdout](../artifacts/task-contracts-v2/evaluation-holdout.md),
[development](../artifacts/task-contracts-v2/evaluation-development.md),
[regression](../artifacts/task-contracts-v2/evaluation-regression.md), and
[verification](../artifacts/task-contracts-v2/local-verification.md).
The fresh set is author-frozen rather than independently blind. Fixed-setting
repetitions and a same-weight judge do not establish population-level reliability.

## Why the original configuration failed

The workflow checked whether an answer matched the selected tool, but did not enforce
whether that tool answered the requested task. A procedure deadline could therefore
pass grounding while a count request remained unanswered. Month-only corrections
could retain the wrong period, and denied or unsupported requests could replace useful
conversation context. Checking for a number in an answer did not establish its role,
unit, or source.

The correction separates task resolution from model proposals. Model actions must
match the resolved task; model-extracted claims must match current tool evidence by
role, ID, value, and unit. Only validated claims become rendered answers. A bounded
semantic repair remains visible and cannot dispatch an invalid proposal. Validated
selection survives denied requests, and a month can inherit an already established
year. Access checks still run on every read.

Two original missing-period references incorrectly prohibited availability reads.
Versioned errata correct those expectations without changing the original records.
The inspected original holdout is now regression data; a new author-frozen set
provides the current holdout. It is not an independently blind benchmark.

Preflight also exposed a judge adapter problem: the small judge sometimes treated
follow-up instructions as factual claims or misread terse structured context. The
adapter now supplies the actual resolved question and readable evidence alongside
exact source records. Original messages, full judge inputs, and generated verdicts
remain recorded. All nine non-perfect preflight candidate scores are preserved in
[input diagnostics](../artifacts/task-contracts-v2/judge-input-diagnostics.json).
Calibration now has 24 controls, including supported and unsupported structured
answers. Independent task checks still use the original conversation references;
no judge claim is filtered and no acceptance threshold is lowered.

## Original recorded result

The verdict is **REJECTED**. Calibration matched all twelve hand labels. Development
completed 96 turns; holdout completed 288 turns across three paired repetitions.
Every eligible answered turn received a Ragas faithfulness result, with no judge errors.
No out-of-scope or stale receipt exposure was detected by the independent checks.

Each holdout repetition produced the same results under the fixed generation settings:

| Configuration | Exact turns | Status matches | Numeric-task failures | Runtime errors |
|---|---:|---:|---:|---:|
| Current-message baseline | 4/48 | 12/48 | 2 | 2 |
| Conversational state | 17/48 | 38/48 | 13 | 6 |

Numeric-task failures include missing counts and incorrect task/evidence selection,
not only incorrect arithmetic. Runtime errors remain in the denominators. Repetition
under deterministic settings does not provide three independent statistical samples.
The stronger completion count cannot override the failed acceptance rule.

See the [holdout report](../artifacts/evaluation-holdout.md),
[development report](../artifacts/evaluation-development.md), and
[full holdout transcript](../artifacts/evaluation-holdout.json).

## A faithful answer can answer the wrong question

In the first holdout repetition of `switch-after-date-change-intake`, the user asks:

> Report intake first-response breaches for August 2026.

The independent reference is 93 cases, supported by the August aggregate receipt.
The agent instead selects `search_procedures` and answers with the applicable
four-hour deadline. Ragas faithfulness scores that answer 1.0 because the retrieved
procedure supports the deadline. The answer still fails the requested task: it gives
no aggregate and no count.

The independent numeric/evidence check and per-turn tool check catch this mismatch.
This is why faithfulness cannot stand in for task success, tool accuracy, or numerical
correctness. It also explains why a high average support score cannot override the
comparison's failure gate.

## Original interpretation boundaries

Session state may improve some follow-ups without making the selected model reliable
on the entire task. Wrong tool choices, unresolved references, validated error outputs,
and missing count answers remain unsuccessful turns. Reporting those outcomes is part
of the experiment rather than an exception to its denominator.

The judge is the same model as the answer generator. Twelve hand-labeled calibration
cases test known controls but do not establish independent judge reliability on every
generated answer. This finite synthetic corpus does not establish production quality.
