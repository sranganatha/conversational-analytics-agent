# Conversational Analytics Agent

Scoped evidence tools for questions over service procedures and operational metrics.

The synthetic dataset connects escalation rules with daily service counts for two queues.
It supports questions such as which rule applies to a period, how many cases breached
that rule, and how a follow-up changes the queue or date range.

## Included

- Twelve versioned procedure records with queue scope and effective dates
- Daily counts for August and September 2026, with independently specified monthly totals
- A metric catalog defining first-response and resolution breaches
- Twenty-four four-turn evaluation dialogues, split into twelve development and twelve holdout cases
- SQLite FTS5 procedure search filtered by queue scope and effective dates
- Read-only DuckDB metric queries with exact totals and applicable threshold evidence
- Owner-bound SQLite sessions with version checks, expiry, and a six-turn limit
- Append-only tool receipts tied to the request and source digests
- Active evidence invalidation when the selected queue, dates, or metric changes
- Validated caller, session, read-tool, answer, and retrieval-evaluation records
- Offline checks for fixture integrity, split isolation, evidence references, and aggregate totals

The executable runs fixed tool requests and verifies session behavior. It does not
interpret natural-language follow-ups, generate model answers, or score model quality.

## Validate

Requires Git, Make, and a running Podman machine. Project checks execute inside the
container and install no host packages:

```sh
git clone https://github.com/sranganatha/conversational-analytics-agent.git
cd conversational-analytics-agent
make test-container
make demo
```

The command builds the image, runs fixture validation, and executes the tests with
container networking disabled. A successful validation prints:

```text
Validated 12 procedures, 122 daily records, and 24 dialogues (12 development, 12 holdout).
```

`make check` runs fixture validation; `make test` runs the tests. Both use Podman.
Initial image builds require network access to fetch the pinned Python image and
hash-verified DuckDB wheel. Snapshot preparation uses only the procedure, metric,
and daily-count source files, without loading evaluation labels.

## Tool demonstration

`make demo` runs procedure search and metric queries inside an isolated temporary
session. It verifies these results:

| Selection | First-response breaches | Resolution breaches |
|---|---:|---:|
| Intake, September 2026 | 120 | Not requested |
| Intake, August 2026 | 93 | Not requested |
| Review, August 2026 | 62 | 31 |

The demonstration also checks that old selections lose active evidence, identical
reads have identical receipt digests, unauthorized reads fail, and persisted turns
survive a store reopen. Temporary session data is removed when the demo exits.
No model calls, credentials, or host data files are required.

## Data and contracts

See [the data contract](docs/data-contract.md) for tool arguments, metric definitions,
session rules, answer statuses, and the evaluation record format.
All records are synthetic. Fixture expectations validate data integrity, not real-model performance.
