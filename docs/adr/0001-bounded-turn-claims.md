# Bounded turn claims around model execution

Status: accepted

## Context

A conversation turn can wait on a model while another request targets the same session
version. The application must preserve one committed outcome without holding a SQLite
write transaction open during inference.

## Decision

Acquire an owner- and version-checked claim in a short SQLite transaction. Each claim
has a random token and a 60-second expiry. Run the model and read tools outside that
transaction. Commit the visible outcome, receipts, turn, and active evidence atomically
only when the token and session version still match.

An expired claim may be replaced. Its old worker cannot commit over the replacement
or release the replacement's token. A timed-out error can be recorded against its own
expired claim if no replacement has taken it. Other late results are rejected.

## Alternatives

- Holding a write transaction throughout inference would serialize unrelated session
  writes behind model latency and make failures harder to recover.
- Checking only the final session version would prevent duplicate commits but permit
  simultaneous model work for the same active turn.
- An external distributed lock would add a service to a single-host application.

## Consequences

Model calls run outside database transactions, and completed turns remain attributable
to one request and token. A crashed worker can occupy a session until claim expiry.
Inference already running on the model server may continue after a client timeout;
the claim protects the local commit, not cancellation inside the server.
