# Security boundaries

All data is synthetic. The local CLI supplies its caller identity and does not expose
a public API. The controls below demonstrate application boundaries, not a production
identity or data-protection service.

| Input or boundary | Risk | Implemented control | Limit |
|---|---|---|---|
| User message | Forged queue grant or injected instruction | Caller scope supplied separately and checked on every tool call | CLI identity is fixed, not authenticated |
| Session ID | Reading another caller's history | Owner checks before session and receipt reads | Single-host SQLite, no distributed session service |
| Stored history | Old evidence reused after scope/date change | Revalidate scope and invalidate incompatible active evidence | History can still influence model tool selection |
| Procedure passage | Embedded instructions or stale rule | Treat as data, filter scope/effective date, validate evidence IDs | Semantic resistance remains model-dependent |
| Model tool proposal | Arbitrary SQL, unknown tools, or excessive reads | Enumerated tools and strict arguments; bounded graph | Wrong allowed tool choice remains possible |
| Model answer | Invented citations or numbers | Current-evidence references and numeric-token checks | Same numbers can be used in an incorrect claim |
| Concurrent request | Duplicate commits or stale worker overwrite | Version checks and expiring token-bound turn claims | Does not cancel remote inference |
| Model transport | Proxy leakage, oversized response, unbounded call | Explicit local endpoint allowlist, proxies disabled, byte/time/token limits | Local Ollama service has no application authentication |
| Evaluation | Label leakage or favorable score hiding failures | Separate references, frozen inputs, paired runs, explicit missing coverage | Small corpus and same-weight judge limit conclusions |
| Container runtime | Unnecessary process privileges or network access | Non-root execution, read-only filesystem, dropped capabilities, offline default tests | Live model service requires its private network and writable model cache |

Keep model ports unpublished. Do not mount credentials or personal datasets into
these services. The synthetic data contracts are not a design for handling sensitive
production records. Published artifacts contain visible synthetic transcripts and
evaluation labels, not credentials or hidden model reasoning.

Run `make test-container` to exercise foreign-owner denial, forbidden queues, stale
versions, source instructions, receipt tampering, malformed model output, bounded
execution, claim takeover, and missing evaluation outcomes. These tests use scripted
model replies where a specific failure must be reproducible; they do not establish
real-model quality. The separate live evaluation records actual model behavior.
