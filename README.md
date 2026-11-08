# Conversational Analytics Agent

[![CI](https://github.com/sranganatha/conversational-analytics-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/sranganatha/conversational-analytics-agent/actions/workflows/ci.yml)

A bounded conversational assistant over synthetic service procedures and operational
counts, evaluated for retrieval, tool use, evidence support, and conversation handling.

> A faithful statement can still answer the wrong question. Evaluate the selected
> tools, dates, and results as well as the answer's citations.

## Workflow

```text
Caller scope + owner-bound session + message
    -> resolve queue, metric, and month
    -> model selects validated read tools
    -> applicable procedures and exact aggregates
    -> cited answer, clarification, abstention, or visible error
    -> saved outcome and immutable receipts

Paired baseline/conversation runs -> independent checks + Ragas -> comparison report
```

The corpus contains twelve versioned procedure records, 122 daily aggregate records
for August and September 2026, and twenty-four four-turn dialogues split evenly between
development and holdout with disjoint scenario families. Metrics cover first-response
and resolution breaches for intake and review queues. All data is synthetic.

The model chooses procedure search, metric reads, both tools, or a non-answer outcome.
Application code owns caller authority, calendar boundaries, parameterized SQL,
execution budgets, and evidence validation. SQLite FTS5 provides lexical procedure
search; read-only DuckDB templates provide analytical results. LangGraph coordinates
the small workflow. No SQL supplied by the model executes.

## Validate

Requires Git, Make, a running Podman machine, and Podman Compose for live model commands.
Project packages install only inside images:

```sh
git clone https://github.com/sranganatha/conversational-analytics-agent.git
cd conversational-analytics-agent
make test-container
make demo
```

Checks validate contracts, fixture integrity, split isolation, tools, sessions, graph
failures, and evaluator behavior with networking disabled during container execution.
`make demo` exercises fixed tool requests and SQLite persistence without model calls.
It verifies intake first-response counts of 120 in September and 93 in August, and
review counts of 62 first-response and 31 resolution breaches in August.

`make check` validates fixtures; `make test` runs the runtime tests. Initial image
builds require network access for pinned images and hash-verified wheels. Dependency
locks target Linux amd64 and Python 3.12. Snapshot preparation reads source procedures,
metric definitions, and daily counts without loading evaluation labels.

## Ask questions

```sh
make chat
```

Try:

1. For the intake queue in September 2026, what is the first-response rule?
2. How many cases exceeded it that month?
3. And the previous month?
4. What about the review queue?

The pinned Qwen3 1.7B model runs through Ollama on the container network without a
published host port. The first run downloads approximately 1.4 GB. Its artifact digest
must match [model.json](config/model.json); mismatches fail visibly.

A session accepts six turns. Enter `quit` to exit; chat session data is temporary.
The CLI supplies a fixed caller allowed to read both synthetic queues and does not
authenticate external users. Every read rechecks scope and retrieves current evidence.

```sh
make verify-model
make model-down
```

The seven-turn [model smoke verification](artifacts/model-verification.md) is separate
from the larger quality experiment. Stopping the service retains its named model cache.
Run `make model-down` after live commands, including failed or interrupted runs.

## Evaluate

```sh
make calibrate-judge
make evaluate-development
make evaluate-ragas
make model-down
```

The separate evaluation image adds pinned Ragas dependencies without expanding the
chat runtime. Twelve hand-labeled development answers calibrate the judge. A paired
development run precedes three frozen holdout repetitions. The baseline and candidate
share model, prompts, tools, corpus, and budgets; conversation history and saved
selection are the difference.

Reports retain runtime errors, wrong tool choices, clarification, abstention, missing
judge outcomes, and coverage. Ragas scores retrieval IDs, dialogue tool trajectories,
and per-answer faithfulness. Independent checks validate status, scope, dates, metric,
required evidence, and expected count results.

Read the [holdout report](artifacts/evaluation-holdout.md),
[development report](artifacts/evaluation-development.md),
[method and decision policy](docs/evaluation.md), and
[findings](docs/evaluation-findings.md). The recorded verdict describes this finite
experiment; a high average score cannot override a failed acceptance rule.

The recorded verdict is **REJECTED**. Conversation state increased exact successful
turns, but the selected model failed count requests and tool-selection checks. The
findings explain a fully faithful procedure answer that still fails a count question.

## Boundaries

Citation presence and numeric-token checks do not prove semantic correctness. The
selected model can choose an allowed but incorrect tool or answer the wrong task.
The Ragas judge uses the same model weights, so calibration does not eliminate
correlated errors. The small synthetic corpus does not establish production quality.

This is a single-host, monthly analytics reference with two approved metric templates.
It does not provide general SQL generation, external user authentication, distributed
availability, or arbitrary business analytics. Model calls have explicit limits and
no automatic retry or fallback. Default tests and CI make no model calls.

See [architecture](docs/architecture.md), [data contracts](docs/data-contract.md),
[security boundaries](docs/security.md), [operations](docs/runbook.md), and the
[turn-claim decision](docs/adr/0001-bounded-turn-claims.md).
