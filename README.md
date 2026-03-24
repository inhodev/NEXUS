# NEXUS

NEXUS is a supervised autonomous software-civilization platform.

The current real slice is a local-first native control plane. It can:
- accept a run request,
- materialize a default task graph,
- create an isolated workspace,
- write artifacts,
- persist run state/events in SQLite,
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

## Strongest Next Slice

The next highest-leverage step is to turn the bounded execution hook into a real planner/executor loop:
- map each task kind to one or more approved server-side actions,
- store richer execution summaries and restart hints,
- and let the control plane progress a run across multiple tasks without opening arbitrary shell access.
