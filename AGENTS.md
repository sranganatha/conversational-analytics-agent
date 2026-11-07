# Repository instructions

## Scope and engineering

- Build the conversational analytics workflow over synthetic service procedures and counts.
- Keep caller authority separate from messages, procedure text, and model output.
- Validate external and persisted records with explicit fields and stable error codes.
- Keep domain decisions separate from storage, model calls, and report writing.
- Use clear domain names, guard clauses, type annotations, and small direct functions.
- Prefer Python's standard library until a current acceptance criterion needs a dependency.
- Add an ADR only for an important project decision with meaningful alternatives and consequences.
- Preserve unrelated changes. Avoid placeholder commands, speculative adapters, and unused abstractions.

## Evidence

- Keep expected labels separate from model inputs and retrieved evidence.
- Split by scenario family before tuning and preserve the holdout labels.
- Count errors, abstentions, and missing evaluation results explicitly.
- Treat citations as references, not proof that a claim is supported.
- Do not replace failed model output with fixture answers.
- Keep public documentation reader-facing and limited to implemented behavior and truthful commands.
- Keep work tracking, portfolio discussions, and provider migration plans out of the README.
- Use no em dashes in prose.

## Development and delivery

- Run all project checks through Make and Podman; install no project dependencies on the host.
- Keep default checks credential-free and disable networking during container execution.
- Every non-trivial contract or failure rule needs a focused runnable test.
- Review the diff and run `make test-container` before opening or merging a PR.
- Follow issue, focused branch, checks, PR, human approval, squash merge, and branch deletion.
- Never push implementation directly to main or merge without human approval.
