from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from nexus_core.app import create_app
from nexus_core.config import Settings
from nexus_core.db import connect


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(data_dir=tmp_path / ".nexus-test")
    return TestClient(create_app(settings))


def test_health_endpoint(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_request_materializes_workspace_and_tasks(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        agents_response = client.get("/api/agents")
        actions_response = client.get("/api/actions")
        response = client.post("/api/requests", json={"intent": "Build a safe autonomous planner"})

    assert agents_response.status_code == 200
    assert actions_response.status_code == 200
    assert any(item["action"] == "inspect-workspace" for item in actions_response.json()["items"])
    assert [agent["role"] for agent in agents_response.json()["items"]] == [
        "planner",
        "architect",
        "implementer",
        "tester",
        "reviewer",
    ]
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "ready"
    assert len(payload["tasks"]) == 5
    assert "inspect-workspace" in payload["tasks"][0]["available_actions"]
    assert payload["tasks"][0]["status"] == "ready"
    assert payload["tasks"][1]["status"] == "pending"
    workspace_path = Path(payload["workspace_path"])
    assert workspace_path.exists()
    assert (workspace_path / "intent.md").exists()
    assert (workspace_path / "artifacts" / "initial-plan.json").exists()


def test_system_summary_tracks_runs(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/runs",
            json={"intent": "Build a local-first control plane"},
        )
        assert create_response.status_code == 201

        summary_response = client.get("/api/system/summary")

    assert summary_response.status_code == 200
    payload = summary_response.json()
    assert payload["run_count"] == 1
    assert payload["latest_run_id"] == create_response.json()["id"]


def test_execution_advances_task_and_records_outputs(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Inspect the workspace before planning"},
        )
        run = create_response.json()
        first_task = run["tasks"][0]

        execution_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": first_task["id"], "action": "inspect-workspace"},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")
        executions_response = client.get(f"/api/runs/{run['id']}/executions")

    assert execution_response.status_code == 201
    execution = execution_response.json()
    assert execution["status"] == "completed"
    assert execution["exit_code"] == 0
    assert (
        run["workspace_path"] in execution["stdout_path"]
        or execution["stdout_path"].endswith("stdout.txt")
    )
    assert Path(execution["stdout_path"]).exists()
    assert Path(execution["stderr_path"]).exists()

    detail = detail_response.json()
    assert detail["status"] == "ready"
    assert detail["tasks"][0]["status"] == "completed"
    assert detail["tasks"][0]["started_at"] is not None
    assert detail["tasks"][0]["finished_at"] is not None
    assert detail["tasks"][1]["status"] == "ready"

    executions = executions_response.json()["items"]
    assert len(executions) == 1
    assert executions[0]["action"] == "inspect-workspace"


def test_execution_requires_task_scope(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Reject unscoped execution requests"},
        )
        run = create_response.json()

        execution_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"action": "inspect-workspace"},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")
        executions_response = client.get(f"/api/runs/{run['id']}/executions")

    assert execution_response.status_code == 400
    assert execution_response.json()["detail"] == "task_id is required"
    detail = detail_response.json()
    assert detail["tasks"][0]["status"] == "ready"
    assert any(
        "Blocked execution action 'inspect-workspace' without task scope."
        in event["message"]
        for event in detail["events"]
    )
    assert executions_response.json()["items"] == []


def test_recovery_snapshot_for_ready_run(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Expose a resumable snapshot for the ready run state"},
        )
        run = create_response.json()
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert recovery_response.status_code == 200
    snapshot = recovery_response.json()
    assert snapshot["run_status"] == "ready"
    assert snapshot["recovery_status"] == "ready"
    assert snapshot["can_advance"] is True
    assert snapshot["current_task"]["id"] == run["tasks"][0]["id"]
    assert snapshot["next_action"]["action"] == "inspect-workspace"
    assert snapshot["latest_decision"] is None
    assert "POST /api/runs/" in snapshot["restart_hints"][0]

    artifact_path = Path(snapshot["artifact_paths"]["recovery_snapshot"])
    assert artifact_path.exists()
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["next_action"]["action"] == "inspect-workspace"


def test_next_action_endpoint_is_read_only(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Find the next safe action without mutating the run"},
        )
        run = create_response.json()

        next_action_response = client.get(f"/api/runs/{run['id']}/next-action")
        detail_response = client.get(f"/api/runs/{run['id']}")

    assert next_action_response.status_code == 200
    payload = next_action_response.json()
    assert payload["task_id"] == run["tasks"][0]["id"]
    assert payload["task_kind"] == "intake"
    assert payload["action"] == "inspect-workspace"
    assert payload["command_argv"] == ["pwd"]
    assert "default safe action" in payload["reason"]

    detail = detail_response.json()
    assert detail["tasks"][0]["status"] == "ready"
    assert not any("Planner selected action" in event["message"] for event in detail["events"])
    assert not (Path(run["workspace_path"]) / "artifacts" / "advance-decisions.jsonl").exists()


def test_failed_execution_surfaces_recovery_snapshot(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Surface failed execution recovery hints"},
        )
        run = create_response.json()

        first_advance_response = client.post(f"/api/runs/{run['id']}/advance")
        assert first_advance_response.status_code == 200

        workspace = Path(run["workspace_path"])
        (workspace / "intent.md").unlink()

        failed_advance_response = client.post(f"/api/runs/{run['id']}/advance")
        detail_response = client.get(f"/api/runs/{run['id']}")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert failed_advance_response.status_code == 200
    failed_execution = failed_advance_response.json()
    assert failed_execution["status"] == "failed"
    assert failed_execution["action"] == "read-intent"
    assert Path(failed_execution["stderr_path"]).exists()

    detail = detail_response.json()
    assert detail["status"] == "failed"
    assert detail["tasks"][1]["status"] == "failed"
    assert detail["tasks"][1]["last_error"] is not None

    snapshot = recovery_response.json()
    assert snapshot["run_status"] == "failed"
    assert snapshot["recovery_status"] == "attention_required"
    assert snapshot["can_advance"] is False
    assert snapshot["current_task"]["status"] == "failed"
    assert "failed with last error" in snapshot["blocking_reason"]
    assert snapshot["last_execution"]["id"] == failed_execution["id"]
    assert snapshot["last_execution"]["status"] == "failed"
    assert any("stderr_path and stdout_path" in hint for hint in snapshot["restart_hints"])

    artifact_payload = json.loads(
        Path(snapshot["artifact_paths"]["recovery_snapshot"]).read_text(encoding="utf-8")
    )
    assert artifact_payload["run_status"] == "failed"
    assert artifact_payload["last_execution"]["id"] == failed_execution["id"]


def test_advance_can_complete_default_task_graph(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Advance the whole default graph with safe server-side actions"},
        )
        run = create_response.json()

        observed_actions: list[str] = []
        for _ in range(5):
            next_action_response = client.get(f"/api/runs/{run['id']}/next-action")
            assert next_action_response.status_code == 200
            observed_actions.append(next_action_response.json()["action"])

            advance_response = client.post(f"/api/runs/{run['id']}/advance")
            assert advance_response.status_code == 200
            assert advance_response.json()["status"] == "completed"

        detail_response = client.get(f"/api/runs/{run['id']}")
        executions_response = client.get(f"/api/runs/{run['id']}/executions")
        no_next_action_response = client.get(f"/api/runs/{run['id']}/next-action")
        no_advance_response = client.post(f"/api/runs/{run['id']}/advance")

    assert observed_actions == [
        "inspect-workspace",
        "read-intent",
        "list-artifacts",
        "list-root",
        "list-artifacts",
    ]

    detail = detail_response.json()
    assert detail["status"] == "completed"
    assert all(task["status"] == "completed" for task in detail["tasks"])
    assert any(
        "Planner selected action 'inspect-workspace'" in event["message"]
        for event in detail["events"]
    )

    artifact_path = Path(run["workspace_path"]) / "artifacts" / "advance-decisions.jsonl"
    records = [json.loads(line) for line in artifact_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 6
    assert records[0]["action"] == "inspect-workspace"
    assert records[-1]["status"] == "blocked"

    executions = executions_response.json()["items"]
    assert len(executions) == 5
    assert no_next_action_response.status_code == 409
    assert no_advance_response.status_code == 409


def test_blocked_execution_records_event_without_advancing_task(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Attempt a blocked action"},
        )
        run = create_response.json()
        first_task = run["tasks"][0]

        blocked_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": first_task["id"], "action": "curl-the-internet"},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")

    assert blocked_response.status_code == 400
    assert "not allowed" in blocked_response.json()["detail"]

    detail = detail_response.json()
    assert detail["tasks"][0]["status"] == "ready"
    assert detail["tasks"][1]["status"] == "pending"
    assert any("Blocked execution action" in event["message"] for event in detail["events"])


def test_completed_task_reexecution_is_rejected_and_logged(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Reject re-running completed task executions"},
        )
        run = create_response.json()
        first_task = run["tasks"][0]

        first_execution_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": first_task["id"], "action": "inspect-workspace"},
        )
        blocked_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": first_task["id"], "action": "inspect-workspace"},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")

    assert first_execution_response.status_code == 201
    assert blocked_response.status_code == 400
    assert blocked_response.json()["detail"] == "Task must be ready or running before execution"
    detail = detail_response.json()
    assert any(
        "Blocked execution action 'inspect-workspace' because task" in event["message"]
        for event in detail["events"]
    )
    assert detail["tasks"][0]["status"] == "completed"
    assert detail["tasks"][1]["status"] == "ready"


def test_task_scoped_action_rules_are_enforced(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Keep actions aligned to the task graph"},
        )
        run = create_response.json()
        first_task = run["tasks"][0]

        blocked_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": first_task["id"], "action": "list-artifacts"},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")

    assert blocked_response.status_code == 400
    assert "not allowed for task kind" in blocked_response.json()["detail"]
    detail = detail_response.json()
    assert detail["tasks"][0]["status"] == "ready"
    assert any(
        "Blocked execution action 'list-artifacts'" in event["message"]
        for event in detail["events"]
    )


def test_ambiguous_next_action_state_fails_closed(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Refuse to advance when the run state is ambiguous"},
        )
        run = create_response.json()
        settings = client.app.state.settings

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = 'ready'
                WHERE id = ? AND run_id = ?
                """,
                (run["tasks"][1]["id"], run["id"]),
            )

        next_action_response = client.get(f"/api/runs/{run['id']}/next-action")
        advance_response = client.post(f"/api/runs/{run['id']}/advance")
        detail_response = client.get(f"/api/runs/{run['id']}")
        executions_response = client.get(f"/api/runs/{run['id']}/executions")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert next_action_response.status_code == 409
    assert advance_response.status_code == 409
    assert next_action_response.json()["detail"] == "No safe next action"
    assert advance_response.json()["detail"] == "No safe next action"

    detail = detail_response.json()
    assert detail["tasks"][0]["status"] == "ready"
    assert detail["tasks"][1]["status"] == "ready"
    assert any(
        event["level"] == "warning" and "No safe next action for run" in event["message"]
        for event in detail["events"]
    )
    assert executions_response.json()["items"] == []

    snapshot = recovery_response.json()
    assert snapshot["recovery_status"] == "attention_required"
    assert snapshot["can_advance"] is False
    assert snapshot["latest_decision"]["status"] == "blocked"
    assert snapshot["latest_decision"]["detail"] == snapshot["blocking_reason"]

    advance_log = Path(snapshot["artifact_paths"]["advance_log"])
    last_decision = json.loads(advance_log.read_text(encoding="utf-8").splitlines()[-1])
    assert last_decision["status"] == "blocked"
    assert last_decision["detail"] == snapshot["latest_decision"]["detail"]


def test_blocked_task_state_surfaces_recovery_hints(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Show recovery guidance for blocked tasks"},
        )
        run = create_response.json()
        settings = client.app.state.settings

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = 'blocked',
                    last_error = 'Operator review is required before continuing'
                WHERE id = ? AND run_id = ?
                """,
                (run["tasks"][0]["id"], run["id"]),
            )
            connection.execute(
                """
                UPDATE runs
                SET status = 'blocked'
                WHERE id = ?
                """,
                (run["id"],),
            )

        next_action_response = client.get(f"/api/runs/{run['id']}/next-action")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert next_action_response.status_code == 409
    snapshot = recovery_response.json()
    assert snapshot["run_status"] == "blocked"
    assert snapshot["recovery_status"] == "attention_required"
    assert snapshot["current_task"]["status"] == "blocked"
    assert "blocked with last error" in snapshot["blocking_reason"]
    assert any("Inspect last_error" in hint for hint in snapshot["restart_hints"])
