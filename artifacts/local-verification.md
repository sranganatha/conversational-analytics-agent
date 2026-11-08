# Local verification

## Execution modes

`make test-container` passes 100 runtime tests and 11 evaluation tests. Container
execution has networking disabled. Tests requiring a specific model failure use
scripted replies; graph, tools, SQLite, DuckDB, and Ragas metric code actually execute.
This mode validates implementation boundaries and evaluator behavior, not model quality.

`make demo` passes the fixed-request tool and session demonstration. It verifies exact
aggregates, evidence invalidation, immutable receipts, forbidden reads, and persistence.

The [clean-checkout CI run](https://github.com/sranganatha/conversational-analytics-agent/actions/runs/42434981924)
executes these same Make commands for source commit
`0758b622334c626069df7ea85a1beaabef454047`.

## Exercised failure and recovery paths

| Boundary | Runnable test |
|---|---|
| Foreign-owner or unknown session | `SessionStoreTests.test_foreign_or_unknown_session_is_denied` |
| Six-turn budget | `SessionStoreTests.test_seventh_turn_fails_but_history_remains_readable` |
| Failed model output remains a saved error | `AgentTests.test_model_failures_are_saved_not_replaced_by_fixtures` |
| Unexpected model error releases its claim | `AgentTests.test_unexpected_model_exception_is_visible_and_claim_is_released` |
| Expired claim replacement and stale-worker isolation | `AgentTests.test_expired_claim_can_be_replaced_but_old_worker_cannot_release_it` |
| Deadline clears answer evidence | `AgentTests.test_deadline_stops_composition_and_clears_evidence` |
| Concurrent version has one committed turn | `SessionStoreTests.test_concurrent_same_version_has_one_commit` |
| Scope rejection precedes database access | `EvidenceToolTests.test_scope_and_metric_rejection_precede_database_access` |
| Invalid judge result remains missing coverage | `EvaluationTests.test_judge_invalid_json_is_not_retried_or_converted_to_success` |

These are deterministic local failure exercises. They do not simulate cloud failover
or establish availability of a deployed service.

## Actual model experiment

The pinned Ollama/Qwen run records twelve calibration cases, 96 development turns,
and 288 holdout turns. All 184 answered development/holdout turns received Ragas judge
results. Runtime and input fingerprints match the frozen manifest. The verdict is
**REJECTED**, with task failures retained. Read the [findings](../docs/evaluation-findings.md)
and [holdout report](evaluation-holdout.md) before interpreting individual scores.

The experiment records source revision `70169776aaeb368bd233ee31d232bb068f74fd41`.
Later documentation, test, and artifact commits do not change those frozen runtime
inputs. The same model weights generate and judge answers, a stated limitation.

## Cleanup

After the experiment, `make model-down` removed the project model container and
Compose network. `podman ps` reported no running containers. The project named model
cache remains for reuse; chat and evaluation session databases are temporary. No
AWS resources, AWS credentials, or host project-package installations were used.
