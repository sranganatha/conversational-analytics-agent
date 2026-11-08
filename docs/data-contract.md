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
and queues outside the trusted caller's permissions. All arguments in a batch are
validated before tool dispatch.

Procedure search quotes query tokens as literal FTS5 terms and applies queue and
effective-date filters in the query. It returns at most five records on a successful
search. Overlapping applicable rules with different thresholds return `CONFLICT`.
Lexical matching is not a semantic relevance or answer-support guarantee.

Metric lookup uses one application-owned SQL template for each catalogued metric.
Queue and dates are bound parameters. The source snapshot opens read-only with
external access disabled. A complete threshold history and daily coverage are
required for a numeric result. Periods crossing a threshold change include each
applicable source rule in `threshold_evidence`; the precomputed daily counts already
use those source definitions. They cannot answer a hypothetical threshold change.

| Tool status | Meaning |
|---|---|
| `OK` | Exact procedure evidence or a complete aggregate is available |
| `NO_EVIDENCE` | No applicable procedure matched the search |
| `CONFLICT` | Applicable source rules disagree on the threshold |
| `MISSING_RULE` | Rules do not cover the requested metric interval |
| `MISSING_DATA` | Daily records do not cover the entire requested interval |

Incomplete coverage never becomes a partial or zero count. Tool statuses describe
evidence availability and are separate from answer statuses.

## Evidence snapshots and receipts

The container build prepares a SQLite procedure index and a DuckDB analytical
snapshot from source files. It never reads dialogue labels or expected monthly
totals to build these databases. The runtime checks the database digests against
build metadata, and both databases open read-only.

Each tool result has a content-derived `receipt_id`, exact arguments, tool name,
source digests, and result evidence. Identical requests over identical sources return
the same receipt digest. Numeric evidence identifies the exact metric, queue, and
half-open interval and includes its numerator, denominator, and unit. Receipt hashes
identify content; they are not digital signatures or a defense against a hostile
operator replacing both data and metadata.

## Caller and session

A trusted caller record contains `subject` and `allowed_queues`. The caller is supplied
outside conversation text. A session contains `session_id`, `owner`, `version`,
`turn_count`, and a timezone-aware `expires_at` timestamp.
Authorization checks owner, expected version, exclusive expiry, and the six-turn limit.
It rejects boolean versions and invalid timestamps. New sessions expire one hour
after creation.

SQLite stores sessions, turns, and receipts. A short `BEGIN IMMEDIATE` transaction
checks the session version, runs the read-tool batch, and atomically commits the
receipts, turn, active selection, and incremented version. A competing stale request
returns `SESSION_CONFLICT`; a lock that exceeds the bounded wait returns
`SESSION_BUSY`. A failed tool batch rolls back its session writes. SQLite serializes
these bounded batches; no model call runs inside this transaction.

Receipt and turn rows reject updates and deletes. Historical reads recheck current
queue permissions and are denied if they would expose a revoked scope. An expired
session cannot be read or advanced. A completed six-turn session remains readable
until expiry, but cannot accept another turn.

Changing the queue or interval clears active evidence. Changing the metric clears
incompatible evidence; a procedure search refreshes the active evidence. Missing or
conflicting results clear active answer evidence. Historical receipts remain intact.
History explains earlier reads and does not authorize a current answer.

A turn request contains only `session_id`, `expected_version`, and `message`.
Caller identity and queue permissions are supplied separately. Unknown request fields,
including body-supplied permission grants, are rejected.

The contract limits a turn to three tool calls and four model calls with a 60-second
deadline. User messages are limited to 1,200 characters. Retrieval evaluation samples
carry at most 8,000 context characters. The graph uses one planning call and, when
evidence is available, one answer call. Each model request has a 512-token generation
limit, a 4,096-token context configuration, a 16,000-character prompt limit, and a
65,536-byte response limit. Socket timeouts and elapsed-time checks enforce the turn
budget at model and tool boundaries. There are no automatic retries or fixture fallbacks.

## Conversational orchestration

A LangGraph workflow resolves a monthly request, conditionally executes validated
read tools, and composes an answer from the current results. The planner returns a
structured proposal and selected tool names. Application code normalizes explicit
queue names, the two metric names, and named calendar months before model planning.
An omitted slot can carry over from owned structured context. Missing or ambiguous
slots clarify before model or data access. The model cannot override an explicit
selection. Calendar boundaries and previous-month
arithmetic are calculated by application code, including year transitions. The agent
supports whole-month questions; the underlying tools also accept bounded date intervals.

Conversational mode supplies owned user/assistant history and the prior selection to
the planner. Baseline mode supplies neither. Both use the same prompts, model, tools,
and limits. The answer composer sees current evidence and the resolved request, not
prior conversation text or evaluation labels.

Missing or conflicting tool results produce an abstention without asking the model to
invent a result. Invalid model output, unknown citations, numerical tokens absent from
the supplied evidence, transport failure, and truncation remain explicit errors.
Count answers must include the recorded count and cite its aggregate receipt; rule
answers must cite an applicable threshold record. Clarification retains known partial
slots so a later response can supply the missing metric or month.
Numerical-token membership does not verify every numerical relation or answer meaning.
Visible structured proposals, answers, actual tool attempts, receipts, usage, and timings
are recorded. Hidden model reasoning is neither requested nor retained.

Model inference runs outside SQLite transactions. An owner- and version-checked claim
reserves the turn for 60 seconds. Completion atomically appends the outcome and tool
receipts and advances the session. Expired claims can be replaced, but stale workers
cannot commit over or release the replacement. See the [turn-claim decision](adr/0001-bounded-turn-claims.md).

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
