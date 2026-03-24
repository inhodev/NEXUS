# NEXUS

NEXUS is a supervised autonomous software-civilization platform.

The current real slice is a local-first native control plane. It can:
- accept a run request,
- materialize a default task graph,
- expose an action catalog and task-scoped available actions,
- recommend the next safe action for the single ready task,
- expose a resumable recovery snapshot for the current run state,
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

## Codex Worktree Flow

Use hidden project-local worktrees so parallel threads stay isolated and bootstrapped the same way:

```bash
make worktree NAME=feature-local-slice
cd .worktrees/feature-local-slice
make setup
```

Every worktree shares the same workflow:
- `make setup` wraps `.codex/actions/setup.sh` and prepares the local environment.
- `make run` wraps `.codex/actions/run-api.sh` and starts the native FastAPI service.
- `make test` wraps `.codex/actions/test.sh` and runs lint plus tests.
- `make smoke` wraps `.codex/actions/smoke.sh` and verifies the live API.

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

- `GET /api/runs/{run_id}/recovery` exposes the resumable run snapshot, current task focus, latest decision, last execution, and restart hints.
- `GET /api/runs/{run_id}/next-action` previews the only safe next action without mutating run state.
- `POST /api/runs/{run_id}/advance` records the planner decision and executes the bounded action.
- `POST /api/runs/{run_id}/executions` remains task-scoped and now requires an explicit `task_id`.
- Planner decisions are appended to `artifacts/advance-decisions.jsonl` inside the run workspace.
- The latest resumable snapshot is stored in `artifacts/run-recovery.json`.

## When Advance Stops

If `GET /api/runs/{run_id}/next-action` or `POST /api/runs/{run_id}/advance` returns `409`:
- inspect `GET /api/runs/{run_id}/recovery` first for the blocking reason and restart hints
- inspect `GET /api/runs/{run_id}` for task statuses and recent events
- inspect `artifacts/advance-decisions.jsonl` for the latest planner decision record
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

The next highest-leverage step is to add explicit safe recovery transitions:
- let operators repair a blocked or failed run without mutating SQLite by hand,
- preserve auditable recovery decisions alongside planner/execution artifacts,
- and expand the approved action graph without opening arbitrary shell access.
