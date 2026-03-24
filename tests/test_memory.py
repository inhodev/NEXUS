from __future__ import annotations

import json
from pathlib import Path

from nexus_core.memory import MemoryIndex, index_workspace, search_workspace


def test_index_workspace_pulls_in_text_and_json_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "run_001"
    artifacts = workspace / "artifacts"
    executions = workspace / "executions" / "exec_1"
    artifacts.mkdir(parents=True)
    executions.mkdir(parents=True)

    (workspace / "intent.md").write_text(
        "# Run Intent\n\nBuild a task system with audit logs.\n",
        encoding="utf-8",
    )
    (artifacts / "advance-decisions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "created_at": "2026-03-25T00:00:00+00:00",
                        "status": "recommended",
                        "action": "inspect-workspace",
                        "task_title": "Record request and local constraints",
                        "summary": "Planner selected the safe first step.",
                    }
                ),
                json.dumps(
                    {
                        "created_at": "2026-03-25T00:05:00+00:00",
                        "status": "blocked",
                        "detail": "No safe next action for run because there are 2 ready tasks.",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    (artifacts / "run-recovery.json").write_text(
        json.dumps(
            {
                "run_id": "run_001",
                "recovery_status": "attention_required",
                "blocking_reason": "No safe next action",
            }
        ),
        encoding="utf-8",
    )
    (executions / "stdout.txt").write_text(
        "planner selected action inspect-workspace\n",
        encoding="utf-8",
    )

    index = index_workspace(workspace)

    assert isinstance(index, MemoryIndex)
    assert len(index.entries) >= 4

    audit_hits = index.search("audit logs", limit=3)
    assert audit_hits[0].entry.kind == "intent"
    assert "audit logs" in audit_hits[0].snippet.lower()

    blocked_hits = index.search("two ready tasks", limit=3)
    assert blocked_hits[0].entry.kind == "jsonl"
    assert blocked_hits[0].entry.title.endswith("line 2")
    assert "blocked" in blocked_hits[0].snippet.lower()

    planning_hits = index.search("planner selected action", limit=3)
    assert planning_hits[0].entry.source_path.endswith("stdout.txt")
    assert "planner selected action" in planning_hits[0].snippet.lower()


def test_search_workspace_can_skip_execution_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "run_002"
    artifacts = workspace / "artifacts"
    executions = workspace / "executions" / "exec_2"
    artifacts.mkdir(parents=True)
    executions.mkdir(parents=True)

    (workspace / "intent.md").write_text(
        "# Run Intent\n\nPrepare a worker handoff.\n",
        encoding="utf-8",
    )
    (executions / "stdout.txt").write_text(
        "claimed worktree ready\n",
        encoding="utf-8",
    )

    hits = search_workspace(workspace, "claimed worktree", include_executions=False)

    assert hits == []
