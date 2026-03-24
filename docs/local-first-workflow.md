# Local-First Workflow

This repository is intended to run natively on the host machine first.

## Setup

1. Open the repo.
2. If you are doing parallel Codex work, create a worktree under `.worktrees/`.

```bash
make worktree NAME=<branch-name>
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

Expected first-slice behavior:

- the service starts without Docker
- a request can be registered
- run and task state can be queried
- each task exposes a small allowed action set
- a bounded execution action can run inside the workspace
- artifacts and logs stay local

Useful API checks:

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/api/actions
curl -s -X POST http://127.0.0.1:8000/api/runs -H 'content-type: application/json' -d '{"intent":"Build a task manager with audit logs"}'
curl -s http://127.0.0.1:8000/api/runs
curl -s http://127.0.0.1:8000/api/system/summary
curl -s http://127.0.0.1:8000/api/runs/<run-id>/executions
```

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
