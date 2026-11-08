# Task contracts and grounded claims

Status: accepted

## Context

The first paired experiment rejected the conversational configuration. The model
could choose procedure search for a count request and produce a faithful but irrelevant
deadline answer. Month-only corrections were ignored, and a non-answer could erase
usable selections. Checking numeric tokens against retrieved text could not distinguish
counts, deadlines, dates, or denominators.

## Decision

Keep explicit queue, date, metric, and task state outside model-generated prose.
The model proposes one action: rule lookup, count lookup, both, clarification, or
abstention. Application code validates the proposal against the current task before
executing typed tools. Unsupported requests and anticipated scope denials abstain
without changing the previous validated selection.

For supported sources, the model returns typed claims with evidence identity, role,
integer value, and unit. Validate every claim against current tool evidence and render
only those validated model claims with the resolved queue, metric, and month. Do not
use generated prose as authoritative data and do not substitute fixture answers.

A rejected tool proposal or claim gets at most one explicit repair generation per
stage. Retain the rejected output and error code. The existing four-call and 60-second
turn limits still apply. Transport failures are not retried, and no provider fallback
or deterministic replacement for failed model output is permitted.

## Alternatives

- Prompt instructions alone did not reliably preserve task/evidence roles in the
  recorded experiment.
- A larger model might improve selection but would not enforce these contracts.
- Fully deterministic dispatch and answers would remove model tool selection and
  claim extraction from the workflow being evaluated.
- Unbounded repair loops would hide failures and weaken execution budgets.

## Consequences

The supported answer vocabulary remains two service metrics and their deadlines.
Answers have a constrained presentation rather than unrestricted generated prose.
The model still selects actions and extracts claims; malformed or unsupported output
can still fail visibly. Independent evaluation checks those claims against references,
and Ragas scores the rendered answer separately. The original rejected evidence is
retained; inspected cases become regression data, with fresh author-frozen validation
families and explicit label errata.
