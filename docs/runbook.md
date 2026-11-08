# Local operations

## Start and reset a conversation

Run `make chat`. The command builds the runtime image, starts Ollama, checks the model
artifact, and opens a temporary session. Enter `quit` or end input to exit. Starting
`make chat` again creates a new session. The six-turn budget is per session; no chat
history is retained after the CLI exits.

The model cache is a project-specific named Podman volume. `make model-down` stops
the Compose services and network while retaining this cache. It does not remove
arbitrary host files or unrelated containers.

## Diagnose a failed turn

| Outcome | Action |
|---|---|
| `CLARIFY` | Supply the missing queue, month/year, or first-response/resolution metric |
| `ABSTAIN` | Check supported dates and source availability; do not interpret missing data as zero |
| `MODEL_IDENTITY_MISMATCH` | Check the configured name/digest and model cache; do not disable verification |
| `MODEL_UNAVAILABLE`, `MODEL_HTTP_ERROR`, or `MODEL_TIMEOUT` | Inspect the project Ollama service; restore it before starting a new explicit request |
| `MODEL_TRUNCATED` or `MODEL_SCHEMA_ERROR` | Keep the failed output visible; do not substitute a fixture answer |
| `UNSUPPORTED_NUMBER`, `MISSING_NUMERIC_RESULT`, or invalid evidence | Treat as answer-validation failure, not a supported answer |
| `SESSION_CONFLICT` or `SESSION_BUSY` | Re-read the current session/version; do not replay a stale version blindly |
| Expired session or exhausted turn budget | Start a new conversation |

An error committed by the agent advances its session version and clears active
answer evidence. Repeating the question is a new explicit turn with a new version.
A client that loses a response should inspect persisted history before retrying;
the store's version check prevents the old version from committing twice.

A crashed worker can leave a claim until its 60-second expiry. A later request may
replace an expired claim; a stale worker cannot commit over or release that replacement.
Do not delete session rows or receipt history to bypass a claim.

## Evaluation recovery

Run calibration, development, and holdout commands in the order documented in
[evaluation](evaluation.md). Reports checkpoint only completed dialogues and mark an
interrupted run incomplete. Preserve previous artifacts before a deliberate rerun.
The evaluator restarts from the beginning and does not silently fill missing cases.
A changed input fingerprint requires new matching prerequisites. A digest mismatch
does not justify changing labels or removing a failed case.

## Verification

`make test-container` exercises real graph and SQLite failure/recovery paths with
scripted model replies: failed model output remains an error, claims are released,
expired claims can be replaced, stale workers cannot interfere, foreign sessions are
denied, and exhausted budgets stop additional work. `make demo` checks deterministic
source and session behavior. Neither command measures real-model quality.

Use `make verify-model` for the separate bounded live smoke run and the evaluation
commands for conversational quality. Finish with `make model-down`, including after
a failed or interrupted live run. Preserve evidence before removing any project data.
