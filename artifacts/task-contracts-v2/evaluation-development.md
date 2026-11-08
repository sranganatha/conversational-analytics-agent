# Paired conversational evaluation

Split: development
Execution: ollama-ragas
Complete: True
Verdict: **INSUFFICIENT_EVIDENCE**

| Repetition | Mode | Exact turns | Status matches | Faithfulness coverage | Numeric failures | Claim failures | Errors |
|---|---|---|---|---|---|---|---|
| 1 | baseline | 22/48 | 22/48 | 10/10 | 0 | 0 | 0 |
| 1 | conversational | 48/48 | 48/48 | 36/36 | 0 | 0 | 0 |

Faithfulness uses the same model weights as answer generation with separate Ragas prompts.
Calibration disagreements and missing judge results limit conclusions. Citation IDs alone do not establish support.
Exact checks cover expected state, current evidence, and numeric tokens; they do not prove prose semantics.
Typed claims are also checked against independent count and procedure references, including value, role, unit, and ID.
The original holdout is regression data with versioned reference errata; this holdout uses fresh author-frozen families.
The fixture author also implemented the corrections. This is not an independently blind benchmark.
Retrieval ID precision/recall and full-dialogue tool accuracy appear per case in the JSON report.
Search wording is excluded from argument comparison; scope, dates, metric IDs, names, and order are scored.
Errors remain in denominators. Clarifications and abstentions are excluded only from faithfulness.
This small synthetic corpus is a reference experiment, not a population-level quality claim.
