# Paired conversational evaluation

Split: holdout
Execution: ollama-ragas
Complete: True
Verdict: **REJECTED**

| Repetition | Mode | Exact turns | Status matches | Faithfulness coverage | Numeric failures | Errors |
|---|---|---|---|---|---|---|
| 1 | baseline | 4/48 | 12/48 | 8/8 | 2 | 2 |
| 1 | conversational | 17/48 | 38/48 | 38/38 | 13 | 6 |
| 2 | baseline | 4/48 | 12/48 | 8/8 | 2 | 2 |
| 2 | conversational | 17/48 | 38/48 | 38/38 | 13 | 6 |
| 3 | baseline | 4/48 | 12/48 | 8/8 | 2 | 2 |
| 3 | conversational | 17/48 | 38/48 | 38/38 | 13 | 6 |

Faithfulness uses the same model weights as answer generation with separate Ragas prompts.
Calibration disagreements and missing judge results limit conclusions. Citation IDs alone do not establish support.
Exact checks cover expected state, current evidence, and numeric tokens; they do not prove prose semantics.
Retrieval ID precision/recall and full-dialogue tool accuracy appear per case in the JSON report.
Search wording is excluded from argument comparison; scope, dates, metric IDs, names, and order are scored.
Errors remain in denominators. Clarifications and abstentions are excluded only from faithfulness.
This small synthetic corpus is a reference experiment, not a population-level quality claim.
