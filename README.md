# NEXUS

NEXUS is a supervised autonomous software-civilization platform.

The current real slice is a local-first native control plane. It can:
- accept a run request,
- materialize a default task graph,
- expose an action catalog and task-scoped available actions,
- recommend the next safe action for the single ready task,
- expose a resumable recovery snapshot for the current run state,
- expose a local Embassy dashboard and searchable run memory,
- prepare an idempotent worktree-backed dispatch handoff for the current ready task,
- claim a prepared dispatch into a real pinned worktree lifecycle,
- accept claimed-worker completion, failure, blocked, and heartbeat reports,
- create an isolated workspace,
- write artifacts,
- persist run state/events in SQLite,
- append planner decisions to local artifacts,
- and execute a small mapped action set inside the run workspace to advance tasks with evidence.

Docker is intentionally not part of the current developer workflow.

## Quick Start

1. Bootstrap the local environment:

```bash
make setup
```

2. Start the API:

```bash
make run
```

3. Smoke-check the slice:

```bash
make smoke
```

4. Run validation:

```bash
make test
```

5. Optionally exercise the real worktree claim path:

```bash
make claim-smoke
```

## Codex Worktree Flow

Use hidden project-local worktrees so parallel threads stay isolated and bootstrapped the same way:

```bash
make worktree NAME=feature-local-slice BASE_REF=<commit>
cd .worktrees/feature-local-slice
make setup
```

Every worktree shares the same workflow:
- `make setup` wraps `.codex/actions/setup.sh` and prepares the local environment.
- `make run` wraps `.codex/actions/run-api.sh` and starts the native FastAPI service.
- `make test` wraps `.codex/actions/test.sh` and runs lint plus tests.
- `make smoke` wraps `.codex/actions/smoke.sh` and verifies the live API.
- `make claim-smoke` wraps `.codex/actions/claim-smoke.sh` and opt-ins to the real dispatch claim path.

## Repo Shape

- `core/nexus_core/`: local-first control plane code
- `tests/`: API validation tests
- `scripts/`: smoke checks and small operational helpers
- `.codex/setup/`: worktree/bootstrap helpers
- `.codex/actions/`: common run/test/smoke commands
- `docs/`: architecture notes and local-first workflow guidance

## Current Local-First Assumptions

- SQLite replaces PostgreSQL for the first runnable slice.
- In-process workflow state and SQLite-backed events replace Redis queues for now.
- Filesystem artifacts under `.nexus/workspaces/` replace containerized local orchestration.
- Docker remains a future compatibility target, not a current requirement.

## Current API Slice

- `GET /api/runs/{run_id}/recovery` exposes the resumable run snapshot, current task focus, latest dispatch, latest decision, last execution, and restart hints.
- `GET /embassy` serves the local Embassy dashboard and `GET /embassy/healthz` exposes its health check.
- `GET /api/runs/{run_id}/memory/search?q=...` searches intent, artifacts, dispatch logs, and optional execution outputs inside the run workspace.
- `GET /api/runs/{run_id}/dispatches`, `POST /api/runs/{run_id}/dispatches`, and `POST /api/runs/{run_id}/dispatches/{dispatch_id}/claim` expose, prepare, and claim pinned worktree handoff records for the current ready task.
- `POST /api/runs/{run_id}/dispatches/{dispatch_id}/heartbeat` refreshes a claimed worker lease.
- `POST /api/runs/{run_id}/dispatches/{dispatch_id}/complete`, `/fail`, and `/block` let a claimed worker hand results back into the run graph.
- `POST /api/runs/{run_id}/recover` applies a small set of operator-driven recovery transitions without manual SQLite edits.
- `GET /api/runs/{run_id}/next-action` previews the only safe next action without mutating run state.
- `POST /api/runs/{run_id}/advance` records the planner decision and executes the bounded action.
- `POST /api/runs/{run_id}/executions` remains task-scoped and now requires an explicit `task_id`.
- Planner decisions are appended to `artifacts/advance-decisions.jsonl` inside the run workspace.
- Dispatch handoffs are appended to `artifacts/dispatches.jsonl`, write task prompts under `artifacts/dispatches/`, and pin `repo_root` plus `base_commit`.
- Claim attempts write stdout and stderr logs under `artifacts/dispatch-claims/<dispatch-id>/`.
- Worker result manifests live under `artifacts/dispatch-results/<dispatch-id>.json`.
- Repeated `POST /api/runs/{run_id}/dispatches` calls reuse the current prepared handoff for the same safe task instead of duplicating it.
- Repeated `POST /api/runs/{run_id}/dispatches/{dispatch_id}/claim` calls reuse the current claimed handoff for the same dispatch instead of duplicating it.
- Execution or recovery changes invalidate stale prepared dispatches before the run moves forward.
- Once a dispatch is claimed, `next-action`, `advance`, and direct execution fail closed for that task until the dispatch is invalidated.
- Recovery transitions are appended to `artifacts/recovery-actions.jsonl`.
- The latest resumable snapshot is stored in `artifacts/run-recovery.json`.

## When Advance Stops

If `GET /api/runs/{run_id}/next-action` or `POST /api/runs/{run_id}/advance` returns `409`:
- inspect `GET /api/runs/{run_id}/recovery` first for the blocking reason and restart hints
- inspect `available_recovery_actions` in that snapshot for safe operator actions
- call `POST /api/runs/{run_id}/recover` only with one of those advertised recovery actions
- if the run is ready again, call `POST /api/runs/{run_id}/dispatches` to prepare a worktree-backed handoff
- inspect `GET /api/runs/{run_id}` for task statuses and recent events
- inspect `artifacts/advance-decisions.jsonl` for the latest planner decision record
- inspect `artifacts/dispatches.jsonl` and `artifacts/dispatches/*.md` for the latest handoff prompt and any invalidated/superseded dispatch history
- inspect `artifacts/dispatch-claims/<dispatch-id>/stdout.txt` and `stderr.txt` when a claim fails or when a claimed worktree needs verification
- inspect `artifacts/dispatch-results/<dispatch-id>.json` when a claimed worker reports completion, failure, or a blocked state
- inspect `artifacts/recovery-actions.jsonl` for the applied or blocked recovery history
- inspect `executions/<id>/stdout.txt` and `executions/<id>/stderr.txt` when the latest execution failed

Example `advance-decisions.jsonl` line:

```json
{"created_at":"2026-03-25T00:00:00+00:00","run_id":"run_...","status":"blocked","detail":"No safe next action for run 'run_...' because there are 2 ready tasks."}
```

Stable diagnostic keys:
- `created_at`, `run_id`, and `status` identify the planner outcome
- `action`, `task_id`, `task_kind`, and `task_title` describe the selected safe step when one exists
- `detail` explains why the planner blocked instead of advancing

## Strongest Next Slice

The next highest-leverage step is to connect claimed worktrees to richer agent execution loops:
- preserve durable memory across runs instead of per-run search only,
- attach heartbeats and result manifests to real Codex worker lifecycles automatically,
- and expand the approved action graph without opening arbitrary shell access.
