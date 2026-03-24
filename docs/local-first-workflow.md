# Local-First Workflow

This repository is intended to run natively on the host machine first.

## Setup

1. Open the repo.
2. If you are doing parallel Codex work, create a worktree under `.worktrees/`.

```bash
make worktree NAME=<branch-name> BASE_REF=<commit>
```

3. Refresh the Python environment.

```bash
make setup
```

## Run

Start the control plane directly on the host.

```bash
make run
```

## Test

```bash
make test
```

## Smoke

```bash
make smoke
```

Opt in to the real worktree claim path only when you want to exercise live `git worktree` creation:

```bash
make claim-smoke
```

Expected first-slice behavior:

- the service starts without Docker
- a request can be registered
- run and task state can be queried
- each task exposes a small allowed action set
- the next safe action can be previewed without mutating the run
- the run exposes a recovery snapshot with blocking reasons and restart hints
- the run exposes a searchable local memory surface for intent and artifacts
- the local Embassy dashboard is reachable at `/embassy`
- the run can materialize an idempotent pinned worktree-backed dispatch handoff for the current ready task
- the run can claim that dispatch into a real pinned local worktree
- the run can accept worker completion, failure, blocked, and heartbeat reports for a claimed dispatch
- the planner can advance the run with a bounded workspace action
- artifacts and logs stay local

Useful API checks:

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/api/actions
curl -s -X POST http://127.0.0.1:8000/api/runs -H 'content-type: application/json' -d '{"intent":"Build a task manager with audit logs"}'
curl -s http://127.0.0.1:8000/api/runs
curl -s http://127.0.0.1:8000/api/system/summary
curl -s http://127.0.0.1:8000/api/runs/<run-id>/recovery
curl -s "http://127.0.0.1:8000/api/runs/<run-id>/memory/search?q=dispatch"
curl -s -X POST http://127.0.0.1:8000/api/runs/<run-id>/dispatches
curl -s http://127.0.0.1:8000/api/runs/<run-id>/dispatches/<dispatch-id>/handoff
curl -s -X POST http://127.0.0.1:8000/api/runs/<run-id>/dispatches/<dispatch-id>/claim
curl -s -X POST http://127.0.0.1:8000/api/runs/<run-id>/dispatches/<dispatch-id>/heartbeat
curl -s -X POST http://127.0.0.1:8000/api/runs/<run-id>/dispatches/<dispatch-id>/complete -H 'content-type: application/json' -d '{"summary":"Completed safely"}'
curl -s http://127.0.0.1:8000/api/runs/<run-id>/next-action
curl -s -X POST http://127.0.0.1:8000/api/runs/<run-id>/advance
curl -s http://127.0.0.1:8000/api/runs/<run-id>/executions
```

If `next-action` or `advance` returns `409`, inspect these in order:

- `GET /api/runs/<run-id>/recovery` for the latest blocking reason and restart hints
- `available_recovery_actions` in that snapshot for the safe recovery transitions currently allowed
- `POST /api/runs/<run-id>/recover` to apply one advertised recovery action
- `POST /api/runs/<run-id>/dispatches` to materialize a pinned worktree-backed handoff once the run is ready again
- `POST /api/runs/<run-id>/dispatches/<dispatch-id>/claim` to turn a prepared handoff into a real local worktree
- `GET /api/runs/<run-id>` for task statuses and recent events
- `artifacts/advance-decisions.jsonl` for append-only planner history
- `artifacts/dispatches.jsonl`, `artifacts/dispatches/*.md`, and `artifacts/dispatches/*.json` for dispatch handoff history, pinned commit metadata, and machine-readable worker report contracts
- `artifacts/dispatch-claims/<dispatch-id>/stdout.txt` and `stderr.txt` for claim lifecycle logs
- `artifacts/dispatch-results/<dispatch-id>.json` for claimed worker completion, failure, or blocked reports
- `artifacts/recovery-actions.jsonl` for append-only recovery history
- `artifacts/run-recovery.json` for the latest resumable snapshot
- `executions/<id>/stdout.txt` and `executions/<id>/stderr.txt` if the latest execution failed

## Dependency Strategy

Prefer the simplest local dependency that solves the problem first.

- Prefer SQLite or file-backed persistence first.
- Prefer in-process work queues or background tasks before Redis.
- Prefer local metadata stores before Qdrant.
- Introduce Postgres, Redis, or containers only when a concrete blocker justifies them.

## Worktree Convention

Use Git worktrees for isolated Codex threads.

- Lead thread: integration and convergence.
- Worker thread: one narrow implementation or audit.
- Reviewer thread: spec and quality verification.

Keep each worktree easy to clean up and easy to resume.

## Claimed Worker Contract

The current claimed worker transport is path-scoped:

- identify the run and dispatch in the URL path, not the JSON body
- fetch `GET /dispatches/{dispatch_id}/handoff` when you need the latest machine-readable contract
- refresh ownership with `POST /dispatches/{dispatch_id}/heartbeat`
- report success with `POST /dispatches/{dispatch_id}/complete`
- report failure with `POST /dispatches/{dispatch_id}/fail`
- report a blocked worker state with `POST /dispatches/{dispatch_id}/block`

See `docs/claimed-worker-contract.md` for the body schema and operator expectations.
