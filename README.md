# Conversational Analytics Agent

Conversational questions over service procedures and operational metrics, with cited evidence.

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
- A bounded LangGraph workflow that selects read tools, clarifies ambiguity, and composes answers from fresh evidence
- A current-message-only baseline using the same model, tools, and prompts without conversation history
- A pinned local Qwen model served by Ollama in Podman
- Validated caller, session, read-tool, answer, and retrieval-evaluation records
- Offline checks for fixture integrity, split isolation, evidence references, and aggregate totals

The local assistant resolves monthly follow-ups and generates cited answers. The
deterministic demo exercises fixed tool requests separately from model behavior.

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
hash-verified dependency wheels. The lock targets the Python 3.12 Linux amd64 container.
Snapshot preparation uses only the procedure, metric,
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

## Local conversation

With Podman Compose support available:

```sh
make chat
```

Try these questions in order:

1. For the intake queue in September 2026, what is the first-response rule?
2. How many cases exceeded it that month?
3. And the previous month?
4. What about the review queue?

The assistant checks scope on every read and retrieves fresh evidence for each turn.
The model selects a month; application code calculates its exact calendar boundaries.
Ambiguous questions can return a clarification rather than a count. A session accepts
at most six turns and ends when you enter `quit`. The local caller can read both
synthetic queues; this CLI does not authenticate external users.

The first run downloads approximately 1.4 GB of model data. Model identity is checked
against [the pinned configuration](config/model.json). A digest mismatch fails visibly.
The model service uses a private container network without publishing a host port.

Run the separately labeled smoke verification and stop the service with:

```sh
make verify-model
make model-down
```

Verification writes a JSON transcript and Markdown summary under `artifacts/`.
See the recorded [local-model verification](artifacts/model-verification.md).
The service stays running until `make model-down`, including after verification failure.
Stopping it retains the named model cache for reuse. Chat session data is temporary;
verification preserves its visible transcript in the report. No project packages are
installed on the host.

## Evaluate conversations

Ragas and independent checks compare the conversational agent with its baseline:

```sh
make calibrate-judge
make evaluate-development
make evaluate-ragas
make model-down
```

The commands record judge calibration, development results, and three paired holdout
repetitions under `artifacts/`. They use an additional evaluation image; the chat
runtime does not require Ragas. Reports retain abstentions, runtime errors, and missing
judge results. The judge uses the same model weights as answer generation, so its
scores have a self-judging limitation. See [evaluation details](docs/evaluation.md)
for metrics, input freezing, coverage, and the comparison policy.

The recorded [holdout comparison](artifacts/evaluation-holdout.md) is **REJECTED**.
The conversational configuration completes more exact turns than the baseline, but
fails count requests and tool-selection checks. See [the findings](docs/evaluation-findings.md)
for an example where full faithfulness still accompanies the wrong answer task.

## Answer boundaries

Answers cite the current tool evidence. Citation validation and numerical-token checks
reject some malformed or unsupported outputs, but do not prove semantic correctness.
The local-model smoke run is separate from held-out evaluation and does not establish
general answer quality. Default tests and CI make no model calls.

## Data and contracts

See [the data contract](docs/data-contract.md) for tool arguments, metric definitions,
session rules, answer statuses, and the evaluation record format.
All records are synthetic. Fixture expectations validate data integrity, not real-model performance.
