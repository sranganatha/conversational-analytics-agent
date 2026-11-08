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

The source corpus contains twelve versioned procedures and 122 daily aggregate records
for August and September 2026. Evaluation uses twelve development, twelve inspected
regression, and twelve fresh author-frozen validation dialogues, each with four turns.
Metrics cover first-response and resolution breaches for intake and review queues.
All data is synthetic.

The model proposes rule lookup, metric reads, both, or a non-answer action.
Application code validates task compatibility before any read. The model then extracts
typed claims from current evidence; code checks value, unit, role, and identity before
rendering the answer. Caller authority, calendar boundaries, parameterized SQL,
and execution budgets remain application-owned. SQLite FTS5 provides lexical procedure
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

The ten-turn [model smoke verification](artifacts/task-contracts-v2/model-verification.md) is separate
from the larger quality experiment. Stopping the service retains its named model cache.
Run `make model-down` after live commands, including failed or interrupted runs.

## Evaluate

```sh
make calibrate-judge
make evaluate-development
make evaluate-regression
make evaluate-ragas
make model-down
```

The separate evaluation image adds pinned Ragas dependencies without expanding the
chat runtime. Twenty-four hand-labeled development answers calibrate the judge. A paired
development run precedes three frozen holdout repetitions. The baseline and candidate
share model, prompts, tools, corpus, and budgets; validated conversational selection
and task state are the difference. The inspected original holdout is regression data;
fresh author-frozen validation families provide the new holdout.

Reports retain runtime errors, wrong tool choices, clarification, abstention, missing
judge outcomes, and coverage. Ragas scores retrieval IDs, dialogue tool trajectories,
and per-answer faithfulness. Independent checks validate status, scope, dates, metric,
required evidence, and expected count results.

Read the [holdout report](artifacts/task-contracts-v2/evaluation-holdout.md),
[development report](artifacts/task-contracts-v2/evaluation-development.md),
[regression report](artifacts/task-contracts-v2/evaluation-regression.md),
[method and decision policy](docs/evaluation.md), and
[findings](docs/evaluation-findings.md). The recorded verdict describes this finite
experiment; a high average score cannot override a failed acceptance rule.

The recorded comparison is **IMPROVED**: each of three holdout repetitions has 48/48
exact conversational turns versus 22/48 for the current-message baseline, with no
numeric, claim, scope, runtime, or judge failures. All 96 candidate answers received
faithfulness scores of 1.0. Development and regression each have 48/48 exact candidate
turns. The [original rejected comparison](artifacts/evaluation-holdout.md) remains
available; the findings explain the task and context errors that required correction.

## Boundaries

Citation presence alone does not establish correctness. Incompatible model actions and
unsupported typed claims fail validation; at most one visible repair per stage is
allowed within the turn budget. The supported vocabulary and source facts remain bounded.
The Ragas judge uses the same model weights, so calibration does not eliminate
correlated errors. The small synthetic corpus does not establish production quality.

This is a single-host, monthly analytics reference with two approved metric templates.
It does not provide general SQL generation, external user authentication, distributed
availability, or arbitrary business analytics. Model calls have explicit limits and
no transport retry or provider fallback. Default tests and CI make no model calls.

See [architecture](docs/architecture.md), [data contracts](docs/data-contract.md),
[security boundaries](docs/security.md), [operations](docs/runbook.md), and the
[turn-claim decision](docs/adr/0001-bounded-turn-claims.md).
