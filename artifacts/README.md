# Verification evidence

`make verify-model` writes the local-model verification transcript and summary here.
Current commands write under `task-contracts-v2/`; the original files at this
directory's root remain historical evidence for the rejected first experiment.
Reports identify the model digest, code digest, actual tool calls, outcomes, usage,
and timings. This bounded smoke run is separate from held-out quality evaluation.

`make calibrate-judge`, `make evaluate-development`, and `make evaluate-ragas`
write calibration, paired development, freeze, and paired holdout artifacts here.
`make evaluate-regression` reruns the inspected original holdout using explicit
reference errata. Fresh author-frozen families form the current holdout.
The JSON files retain exact inputs, visible tool outcomes, independent labels,
Ragas scores, judge outputs, usage, errors, and coverage. Markdown summaries do
not replace the detailed records. See [evaluation](../docs/evaluation.md) for
the frozen decision policy and limitations.
