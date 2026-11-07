# Data and conversation contracts

## Source data

The fixtures describe two synthetic service queues, `intake` and `review`.
`daily.csv` contains one row per queue per day from August 1 through September 30, 2026.
Its 122 records contain case counts, first-response breaches, and resolution breaches.
The counts are deliberately small and regular so the expected arithmetic is inspectable.

Each breach count is a subset of the row's case count. A case can belong to both breach
categories, so adding those counts does not give a count of distinct breached cases.
A breach means elapsed time strictly exceeds the applicable threshold.
No rates, individual case records, forecasts, or monetary values are represented.

`expected-totals.json` specifies four independently authored monthly totals.
Validation compares them with sums of the daily rows; it does not derive or rewrite
the expectations. `manifest.json` freezes the exact bytes of the six data files.

## Procedure evidence

Twelve records include eight queue/metric/month rules, two queue definitions, and two
conflicting October intake drafts. October is outside the aggregate data interval.
The imported review definition includes an adversarial instruction as untrusted source text.
Its presence in the corpus grants no authority.

Dates use UTC service dates and half-open intervals: `start_date` is included and
`end_date` is excluded. Procedure applicability uses the same convention.
Numeric expectations identify the exact queue, metric, period, and aggregate receipt.
Procedure expectations reference the exact effective source record.

## Read-tool arguments

Both tools require `queue`, `start_date`, and `end_date` for an interval of at most 61 days.

| Tool | Additional argument | Meaning |
|---|---|---|
| `search_procedures` | `query`, 1 to 500 characters | Retrieve applicable procedure evidence |
| `read_service_metrics` | `metric_id` | Read one defined breach count |

Metric IDs are `first_response_breaches` and `resolution_breaches`.
The metric catalog fixes each measure's numerator, denominator, unit, threshold kind,
and permitted filters. Tool records reject unknown fields, arbitrary SQL, unknown metrics,
and queues outside the trusted caller's permissions. These are argument contracts;
tool execution is not included in the current executable.

## Caller and session

A trusted caller record contains `subject` and `allowed_queues`. The caller is supplied
outside conversation text. A session contains `session_id`, `owner`, `version`,
`turn_count`, and a timezone-aware `expires_at` timestamp.
Authorization checks owner, expected version, exclusive expiry, and the six-turn limit.
It rejects boolean versions and invalid timestamps. These checks do not implement a
persistent session store or concurrent request locking.

A turn request contains only `session_id`, `expected_version`, and `message`.
Caller identity and queue permissions are supplied separately. Unknown request fields,
including body-supplied permission grants, are rejected.

The contract limits a turn to three tool calls and four model calls with a 60-second
deadline. User messages are limited to 1,200 characters. Retrieval evaluation samples
carry at most 8,000 context characters. Model-call counts and deadlines are declared
limits; enforcement requires an execution loop.

## Answer and evaluation records

Turn results contain `status`, `message`, `evidence_ids`, `tool_calls`, and `error_code`.

| Status | Required behavior |
|---|---|
| `ANSWERED` | Nonempty answer and evidence IDs present in the supplied evidence set; no error code |
| `CLARIFY` | A clarification message without evidence or an error code |
| `ABSTAIN` | A visible explanation without evidence or an error code |
| `ERROR` | A visible failure with a stable error code and no answer evidence |

Shape validation does not establish semantic support. A valid citation can still support
the wrong claim. Likewise, tool-call shape validation is not proof that a tool executed.

The saved retrieval sample separates `user_input`, `response`, `retrieved_contexts`,
`retrieved_context_ids`, `reference`, and `reference_context_ids`. Reference labels belong
to evaluation and must not enter model prompts. Context IDs and passages have matching
positions. This validates evaluation inputs without invoking Ragas or a judge.

## Dialogue corpus

Twenty-four four-turn dialogues contain 96 labeled turns across six categories:
temporal follow-ups, queue changes, clarification, missing data, version conflicts,
and injection. Each category contributes two development and two holdout dialogues.
Twelve scenario families are disjoint between the splits, with two queue variants per
family. Family identity is an authored boundary; validation cannot establish semantic
novelty between differently worded scenarios.

Every expected turn separates status, resolved queue/date/metric, evidence IDs, exact
numeric value where applicable, and expected tool names from the user's message.
Unknown evidence, stale procedure labels, incorrect totals, and family split overlap
fail validation. The corpus validates a finite contract rather than general assistant quality.
