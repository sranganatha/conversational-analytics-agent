# Task-contract verification

The evaluated runtime is commit `a3177a2618d77ce60af05eb9ad1d0f4208e2693c`.
The freeze manifest binds 32 source, fixture, configuration, image, and dependency
files. Documentation and recorded outputs do not alter those evaluated inputs.
The pinned model is `qwen3:1.7b`, digest
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.

## Execution

All project dependencies and Python execution used Make and Podman. No project
packages were installed on the host. The actual model and Ragas judge ran through
the private container network; neither service published a host port. Default
checks ran with networking disabled.

- `make test-container`: 127 tests pass, comprising 111 runtime and 16 evaluator tests.
- `make verify-model`: all ten actual-model probes pass, including mixed evidence,
  unsupported prediction, clarification, and resumed conversation.
- `make calibrate-judge`: 24/24 labels match, with 12 supported and 12 unsupported controls.
- `make check demo`: fixture validation and the deterministic tool/persistence demo pass,
  including stale evidence invalidation and unauthorized read denial.

Focused tests cover rejected action proposals before dispatch, bounded semantic
repair, month/year inheritance, context preservation after denied requests, exact
claim roles/units/IDs/values, source-only model inputs, independent evaluation checks,
late judge results, preserved raw evidence, and partial-period judge context.

## Completed comparison

Development and regression each complete 96 paired turns, with 48/48 exact candidate
turns. Fresh holdout completes 288 paired turns. Each of three repetitions records
48/48 exact candidate turns versus 22/48 baseline turns, and 32/32 fully faithful
candidate answers versus 8/8 baseline answers. The verdict is `IMPROVED`.
There are no numeric, claim, scope, runtime, or judge failures. All answered turns
receive a faithfulness score. No semantic repair was needed in these recorded runs.

All 32 frozen input hashes were verified against disk after completion. The original
source fixtures and rejected reports are unchanged. `make model-down` removed the
model container and private network; the named model cache remains available.

## Interpretation

The original rejected reports at the parent directory remain unchanged. The original
holdout has been inspected and is regression data. The new holdout was committed
before the runtime correction by the same author and is not an independently blind
benchmark. The same model weights generate and judge answers. Fixed-setting
repetitions are not independent statistical samples, and this small synthetic corpus
does not establish production readiness.

See [evaluation method](../../docs/evaluation.md),
[model probes](model-verification.md), and [freeze manifest](evaluation-freeze.json).
