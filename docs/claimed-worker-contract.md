# Claimed Worker Contract

This document defines what a claimed worker must report back to NEXUS after it owns a dispatch and finishes local work in the pinned worktree.

The current API transport is path-scoped:

- `GET /api/runs/{run_id}/dispatches/{dispatch_id}/handoff`
- `POST /api/runs/{run_id}/dispatches/{dispatch_id}/heartbeat`
- `POST /api/runs/{run_id}/dispatches/{dispatch_id}/complete`
- `POST /api/runs/{run_id}/dispatches/{dispatch_id}/fail`
- `POST /api/runs/{run_id}/dispatches/{dispatch_id}/block`

That means `run_id` and `dispatch_id` come from the URL path. The body carries the worker
result payload, and the handoff endpoint returns the latest machine-readable contract.

## Required Report Fields

- `run_id`
- `dispatch_id`
- `task_id`
- `summary`
- `changed_files`
- `commands_run`
- `tests_run`
- `artifacts`
- `risk_notes`

## Status Rules

- `complete`: the worktree produced the intended change and the important checks passed.
- `fail`: the worker could not finish safely and must include a concrete failure reason.
- `block`: the worker stopped because it needs human guidance or a missing prerequisite.

## Report Expectations

- Keep the report short, factual, and specific.
- Include file paths, not vague descriptions, for every changed file.
- Include the exact commands and tests that were run.
- Include artifact paths for any proof the operator should inspect next.
- If the worker could not finish, include the best recovery hint the operator should try next.
- Preserve the dispatch identity from the claim step so the control plane can correlate the result with the owned worktree.

## Suggested Result Shape

```json
{
  "summary": "Implemented the change and verified it locally.",
  "changed_files": ["/Users/kiminho/Desktop/NEXUS/core/nexus_core/service.py"],
  "commands_run": ["make test", "make smoke"],
  "tests_run": ["tests/test_api.py"],
  "artifacts": ["/Users/kiminho/Desktop/NEXUS/.nexus/workspaces/run_.../artifacts/dispatch-claims/dispatch_.../stdout.txt"],
  "risk_notes": ["No additional risk beyond local worktree creation."]
}
```

The control plane persists the submitted worker report as
`artifacts/dispatch-results/<dispatch-id>.json` and reflects it back through the recovery
snapshot and dispatch listing APIs.
