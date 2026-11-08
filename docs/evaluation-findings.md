# Evaluation findings

The experiment compares the same local Qwen model and read tools with and without
conversation state. The recorded artifacts identify exact model, source, fixture,
dependency, and policy fingerprints. See [the evaluation method](evaluation.md) for
the frozen comparison rule and coverage definitions.

## Recorded result

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

## Interpretation boundaries

Session state may improve some follow-ups without making the selected model reliable
on the entire task. Wrong tool choices, unresolved references, validated error outputs,
and missing count answers remain unsuccessful turns. Reporting those outcomes is part
of the experiment rather than an exception to its denominator.

The judge is the same model as the answer generator. Twelve hand-labeled calibration
cases test known controls but do not establish independent judge reliability on every
generated answer. This finite synthetic corpus does not establish production quality.
