from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from nexus_core.app import create_app
from nexus_core.config import Settings


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
