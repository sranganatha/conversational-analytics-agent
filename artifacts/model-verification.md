# Local-model verification

Execution: ollama
Model: `qwen3:1.7b`
Model digest: `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`
Code digest: `2b141e7d7e893207313768cefa99b7fff1af14e3d8bcf682edb5ec184fc6011b`

| Mode | Message | Result |
|---|---|---|
| conversational | For the intake queue in September 2026, what is the first-response rule? | PASS |
| conversational | How many cases exceeded it that month? | PASS |
| conversational | And the previous month? | PASS |
| conversational | What about the review queue? | PASS |
| conversational | How many review cases were overdue in September 2026? | PASS |
| baseline | For the intake queue in September 2026, what is the first-response rule? | PASS |
| baseline | How many cases exceeded it that month? | PASS |

Preflight error: none.

This seven-turn smoke run is not the held-out comparison or a Ragas evaluation.
Full visible outputs, tool receipts, failures, usage, and timings are in the JSON report.
