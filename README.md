# Conversational Analytics Agent

Conversation and evidence contracts for questions over service procedures and operational metrics.

The synthetic dataset connects escalation rules with daily service counts for two queues.
It supports questions such as which rule applies to a period, how many cases breached
that rule, and how a follow-up changes the queue or date range.

## Included

- Twelve versioned procedure records with queue scope and effective dates
- Daily counts for August and September 2026, with independently specified monthly totals
- A metric catalog defining first-response and resolution breaches
- Twenty-four four-turn evaluation dialogues, split into twelve development and twelve holdout cases
- Validated caller, session, read-tool, answer, and retrieval-evaluation records
- Offline checks for fixture integrity, split isolation, evidence references, and aggregate totals

The current executable validates contracts and fixtures. It does not generate answers
or score model quality.

## Validate

Requires Git, Make, and a running Podman machine. Project checks execute inside the
container and install no host packages:

```sh
git clone https://github.com/sranganatha/conversational-analytics-agent.git
cd conversational-analytics-agent
make test-container
```

The command builds the image, runs fixture validation, and executes the tests with
container networking disabled. A successful validation prints:

```text
Validated 12 procedures, 122 daily records, and 24 dialogues (12 development, 12 holdout).
```

`make check` runs fixture validation; `make test` runs the tests. Both use Podman.
Initial image builds require network access to fetch the pinned Python image.

## Data and contracts

See [the data contract](docs/data-contract.md) for tool arguments, metric definitions,
session rules, answer statuses, and the evaluation record format.
All records are synthetic. Fixture expectations validate data integrity, not real-model performance.
