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


def test_create_request_materializes_workspace_tasks_and_agents(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        agents_response = client.get("/api/agents")
        response = client.post("/api/requests", json={"intent": "Build a safe autonomous planner"})

    assert agents_response.status_code == 200
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
