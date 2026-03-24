# ADR 0001: Local-First Native Development Before Docker

## Status

Accepted on 2026-03-25.

## Context

The current repository starts from documents only, while the PRD originally assumes Docker and Docker Compose in the initial stack. The immediate goal is not broad infrastructure completeness. The immediate goal is the strongest real NEXUS core slice with low operational overhead and strong Codex compatibility.

Docker currently hurts speed more than it helps:
- the developer machine cannot install Docker right now,
- the repo needs a real runnable slice more than container parity,
- Codex worktrees and local bootstrap scripts already provide reproducible isolation for early development.

## Decision

NEXUS will use a native local-first workflow until a concrete blocker justifies reintroducing Docker.

Current replacements:
- PostgreSQL -> SQLite for the first control-plane state store
- Redis/event queue -> in-process flow plus SQLite-backed event history
- Dockerized local orchestration -> `.codex` bootstrap scripts plus filesystem workspaces
- Container-first developer boot -> `uv sync`, native FastAPI, repo action scripts

## Consequences

Positive:
- lower startup cost,
- faster Codex worktree bootstrapping,
- simpler smoke testing,
- fewer hidden infra assumptions in the first slice.

Tradeoffs:
- local parity is weaker than container parity,
- future multi-service setups will need explicit migration work,
- queue and database abstractions must stay honest so Docker can return later if needed.

## Reintroduction Rule

Docker should return only if one of these becomes true:
- a required dependency cannot be run natively in a maintainable way,
- reproducibility problems become a real drag on development,
- or the local service graph grows enough that native startup becomes fragile.

Until then, local-first native execution is the default.
