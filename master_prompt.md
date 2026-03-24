# AGENTS.md

## Project

This repository is for **NEXUS**.

NEXUS is a supervised autonomous software-civilization platform:
a system intended to take human intent, decompose it into executable engineering work, coordinate specialized agents, generate and modify software, validate it, retain knowledge, and improve its workflows over time under safety constraints.

The main vision lives in `prd.md`.
Read it first.
Treat it as the main product source of truth.

---

## Codex-Specific Working Rules

This repository is operated primarily through the **Codex app**.
That means you should assume:
- multiple threads may run in parallel,
- Git worktrees may be used for isolated execution,
- and subagents may be explicitly spawned for bounded parallel work.

### Lead Thread Rule
Assume one thread is the lead orchestrator.
The lead thread owns:
- overall architecture direction
- deciding what to parallelize
- subagent coordination
- convergence and integration
- final validation
- next-step prioritization

Do not let every thread behave like the overall project owner.

### Parallel Work Rule
Use parallel work only when the problem can be split cleanly.

Good candidates:
- backend/frontend separation
- architecture alternatives
- codebase exploration
- test generation
- security review
- documentation grounded in code
- isolated module work
- targeted bug investigations

Bad candidates:
- trivial changes
- heavily overlapping edits
- ambiguous tasks with no done condition
- broad “go build everything” delegation

### Worktree Rule
For Git repos, prefer worktree-backed threads for independent tasks.
Use worktrees to avoid interfering with ongoing local or parallel work.
Integrate later once a thread has coherent, reviewable results.

### Ownership Boundary Rule
Every parallel thread or subagent should have:
- a single primary goal,
- clear file/module scope,
- explicit constraints,
- and a concrete done condition.

Avoid multiple threads editing the same central files unless there is a very good reason.

### Convergence Rule
Parallel progress is not finished work.
The lead thread must:
- collect results,
- resolve conflicts,
- merge or choose the best path,
- run checks,
- and restore coherence.

---

## How to Work

### First
- read `prd.md`
- inspect the repository deeply
- determine the current maturity level
- identify the highest-leverage next implementation step
- decide whether the task should stay local to the lead thread or be split across subagents/worktrees
- begin execution immediately

### During work
- keep moving
- minimize unnecessary questions
- if blocked on one path, switch to the next highest-value unblocked path
- create extra planning/status documents only if they materially improve long-horizon execution
- keep changes understandable and traceable

---

## Prompt Shape for Parallel Threads

When launching a subagent or thread, include:
- Goal
- Context
- Constraints
- Ownership boundary
- Done when
- Expected output summary

Do not launch vague subagents.

---

## Engineering Style

Prefer:
- working software over speculative plans
- narrow runnable vertical slices over broad fake completeness
- explicit state and artifacts
- maintainable structure
- clean interfaces
- observable behavior
- recoverable workflows
- strong integration discipline

Avoid:
- giant empty scaffolds
- fake complexity
- unused abstractions
- thread sprawl without convergence
- document bureaucracy
- claiming success without validation

---

## Validation

For meaningful changes, run what is relevant and supported:
- lint
- type checks
- tests
- smoke runs
- boot verification
- security sanity checks
- diff review before accepting integration

If something cannot be validated:
- say so clearly
- leave evidence
- state what remains uncertain

Never fake validation.

---

## Safety

Do not:
- hardcode real secrets
- weaken governance casually
- remove auditability
- auto-apply dangerous migrations
- perform risky real-world deployment without explicit approval
- silently widen permissions
- create hidden unsafe shortcuts

Use:
- local-first setups
- mocks
- dry-runs
- safe defaults
- worktree isolation
- reversible changes

---

## Self-Improvement

NEXUS may improve itself only in controlled, reviewable ways.

Good early self-improvements:
- orchestration quality
- logging
- observability
- memory/retrieval quality
- test coverage
- task decomposition
- developer ergonomics
- recovery after interruption
- integration discipline between parallel threads

Protected zones:
- policy boundaries
- secret handling
- approval boundaries
- audit integrity
- emergency stop or control mechanisms

Do not casually modify protected zones.

---

## What Success Looks Like

A good outcome is not a flashy repo.
A good outcome is a repo where:
- the next major step is obvious,
- core flows are increasingly real,
- parallel work converges cleanly,
- progress survives interruption,
- the system becomes more autonomous without becoming reckless,
- and NEXUS is measurably closer to being a real software-civilization engine.

Your standard is reality, not theater.