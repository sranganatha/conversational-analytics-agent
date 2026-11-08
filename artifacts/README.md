# Verification evidence

## Recorded comparisons

| Location | Interpretation |
|---|---|
| [task-contracts-v2/](task-contracts-v2/evaluation-holdout.md) | Current corrected comparison: `IMPROVED`, with 48/48 exact candidate turns versus 22/48 baseline in each repetition |
| [Root reports](evaluation-holdout.md) | Historical first comparison: `REJECTED`; these records describe the earlier workflow |

Current supporting evidence includes [development](task-contracts-v2/evaluation-development.md),
[regression](task-contracts-v2/evaluation-regression.md),
[model probes](task-contracts-v2/model-verification.md), and
[local verification](task-contracts-v2/local-verification.md).
The root-level [local verification](local-verification.md) and model probes are
historical too; their test counts and results are not the current configuration.

## Generate separate evidence

Use the output overrides in the [README](../README.md#evaluate) to write a new run
under `artifacts/local-run/`. Preserve an existing run before reusing its directory.
Without overrides, live commands write under `task-contracts-v2/` and overwrite the
checked-in evidence. `EVALUATION_OUTPUT` must be the same across all evaluation stages;
`VERIFY_OUTPUT` controls the separate model smoke transcript.

`make verify-model` writes the local-model verification transcript and summary.
Reports identify the model digest, code digest, actual tool calls, outcomes, usage,
and timings. This bounded smoke run is separate from held-out quality evaluation.

`make calibrate-judge`, `make evaluate-development`, and `make evaluate-ragas`
write calibration, paired development, freeze, and paired holdout artifacts.
`make evaluate-regression` reruns the inspected original holdout using explicit
reference errata. Fresh author-frozen families form the current holdout.
The JSON files retain exact inputs, visible tool outcomes, independent labels,
Ragas scores, judge outputs, usage, errors, and coverage. Markdown summaries do
not replace the detailed records. See [evaluation](../docs/evaluation.md) for
the frozen decision policy and limitations.
