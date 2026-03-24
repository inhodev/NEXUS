from __future__ import annotations

import json
import subprocess
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
    assert snapshot["latest_dispatch"] is None
    assert snapshot["latest_decision"] is None
    assert snapshot["available_recovery_actions"] == []
    assert "POST /api/runs/" in snapshot["restart_hints"][0]
    assert snapshot["artifact_paths"]["dispatches"].endswith("dispatches.jsonl")

    artifact_path = Path(snapshot["artifact_paths"]["recovery_snapshot"])
    assert artifact_path.exists()
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["next_action"]["action"] == "inspect-workspace"


def test_dispatch_prepares_work_order_for_ready_task(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Prepare a worktree-backed handoff for the current ready task"},
        )
        run = create_response.json()
        dispatch_response = client.post(f"/api/runs/{run['id']}/dispatches")
        dispatches_response = client.get(f"/api/runs/{run['id']}/dispatches")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")
        detail_response = client.get(f"/api/runs/{run['id']}")

    assert dispatch_response.status_code == 201
    dispatch = dispatch_response.json()
    assert dispatch["run_id"] == run["id"]
    assert dispatch["task_id"] == run["tasks"][0]["id"]
    assert dispatch["task_kind"] == "intake"
    assert dispatch["agent_role"] == "planner"
    assert dispatch["status"] == "prepared"
    assert (
        dispatch["status_detail"]
        == "Prepared for the current safe task and pinned to a git commit."
    )
    assert dispatch["branch_name"].startswith("codex/")
    assert Path(dispatch["repo_root"]).name == "NEXUS"
    assert len(dispatch["base_commit"]) == 40
    assert dispatch["worktree_path"].endswith(dispatch["worktree_name"])
    assert dispatch["startup_commands"][0] == (
        f"make worktree NAME={dispatch['worktree_name']} BASE_REF={dispatch['base_commit']}"
    )
    assert Path(dispatch["prompt_path"]).exists()
    assert Path(dispatch["prompt_path"]).name == f"{dispatch['id']}.md"
    assert "Record request and local constraints" in Path(dispatch["prompt_path"]).read_text(
        encoding="utf-8"
    )
    assert dispatch["base_commit"] in Path(dispatch["prompt_path"]).read_text(encoding="utf-8")

    dispatches = dispatches_response.json()
    assert len(dispatches) == 1
    assert dispatches[0]["id"] == dispatch["id"]
    assert dispatches[0]["startup_commands"] == dispatch["startup_commands"]

    recovery = recovery_response.json()
    assert recovery["latest_dispatch"]["id"] == dispatch["id"]
    assert recovery["latest_dispatch"]["status"] == "prepared"
    assert "already prepared" in recovery["summary"]
    assert recovery["artifact_paths"]["dispatches"].endswith("dispatches.jsonl")

    detail = detail_response.json()
    assert any("Prepared dispatch" in event["message"] for event in detail["events"])

    dispatch_log = Path(run["workspace_path"]) / "artifacts" / "dispatches.jsonl"
    assert dispatch_log.exists()
    dispatch_artifact = json.loads(dispatch_log.read_text(encoding="utf-8").splitlines()[-1])
    assert dispatch_artifact["id"] == dispatch["id"]
    assert dispatch_artifact["agent_role"] == "planner"
    assert dispatch_artifact["base_commit"] == dispatch["base_commit"]
    assert dispatch_artifact["status"] == "prepared"


def test_dispatch_reuses_existing_prepared_work_order(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Keep dispatch preparation idempotent for the same safe task"},
        )
        run = create_response.json()

        first_dispatch_response = client.post(f"/api/runs/{run['id']}/dispatches")
        second_dispatch_response = client.post(f"/api/runs/{run['id']}/dispatches")
        dispatches_response = client.get(f"/api/runs/{run['id']}/dispatches")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert first_dispatch_response.status_code == 201
    assert second_dispatch_response.status_code == 201
    first_dispatch = first_dispatch_response.json()
    second_dispatch = second_dispatch_response.json()
    assert second_dispatch["id"] == first_dispatch["id"]

    dispatches = dispatches_response.json()
    assert len(dispatches) == 1
    assert dispatches[0]["status"] == "prepared"

    recovery = recovery_response.json()
    assert recovery["latest_dispatch"]["id"] == first_dispatch["id"]
    assert recovery["latest_dispatch"]["status"] == "prepared"

    dispatch_log = Path(run["workspace_path"]) / "artifacts" / "dispatches.jsonl"
    records = [json.loads(line) for line in dispatch_log.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["id"] == first_dispatch["id"]


def test_claim_dispatch_materializes_worktree_and_logs(tmp_path: Path, monkeypatch) -> None:
    from nexus_core import service as service_module

    def fake_materialize(settings, dispatch, command_argv):
        Path(dispatch.worktree_path).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            args=command_argv,
            returncode=0,
            stdout="worktree ready\n",
            stderr="",
        )

    monkeypatch.setattr(service_module, "_materialize_dispatch_worktree", fake_materialize)

    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Claim the prepared dispatch into a real worktree lifecycle"},
        )
        run = create_response.json()

        dispatch_response = client.post(f"/api/runs/{run['id']}/dispatches")
        dispatch = dispatch_response.json()
        claim_response = client.post(
            f"/api/runs/{run['id']}/dispatches/{dispatch['id']}/claim"
        )
        second_claim_response = client.post(
            f"/api/runs/{run['id']}/dispatches/{dispatch['id']}/claim"
        )
        next_action_response = client.get(f"/api/runs/{run['id']}/next-action")
        advance_response = client.post(f"/api/runs/{run['id']}/advance")
        execution_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": dispatch["task_id"], "action": "inspect-workspace"},
        )
        dispatches_response = client.get(f"/api/runs/{run['id']}/dispatches")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert claim_response.status_code == 200
    assert second_claim_response.status_code == 200
    assert next_action_response.status_code == 409
    assert advance_response.status_code == 409
    assert execution_response.status_code == 400
    claimed = claim_response.json()
    assert second_claim_response.json()["id"] == claimed["id"]
    assert claimed["id"] == dispatch["id"]
    assert claimed["status"] == "claimed"
    assert claimed["claimed_at"] is not None
    assert claimed["claim_command_argv"][0] == "zsh"
    assert Path(claimed["worktree_path"]).exists()
    assert Path(claimed["claim_stdout_path"]).read_text(encoding="utf-8") == "worktree ready\n"
    assert Path(claimed["claim_stderr_path"]).read_text(encoding="utf-8") == ""

    dispatches = dispatches_response.json()
    assert dispatches[0]["status"] == "claimed"
    assert dispatches[0]["claim_command_argv"] == claimed["claim_command_argv"]

    recovery = recovery_response.json()
    assert recovery["latest_dispatch"]["id"] == claimed["id"]
    assert recovery["latest_dispatch"]["status"] == "claimed"
    assert recovery["recovery_status"] == "running"
    assert recovery["can_advance"] is False
    assert "owns task" in recovery["summary"]

    dispatch_log = Path(run["workspace_path"]) / "artifacts" / "dispatches.jsonl"
    records = [json.loads(line) for line in dispatch_log.read_text(encoding="utf-8").splitlines()]
    assert [record["status"] for record in records] == ["prepared", "claimed"]


def test_claim_failed_dispatch_can_retry_same_handoff(tmp_path: Path, monkeypatch) -> None:
    from nexus_core import service as service_module

    attempts = {"count": 0}

    def flaky_materialize(settings, dispatch, command_argv):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return subprocess.CompletedProcess(
                args=command_argv,
                returncode=1,
                stdout="",
                stderr="branch already exists\n",
            )
        Path(dispatch.worktree_path).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            args=command_argv,
            returncode=0,
            stdout="claimed on retry\n",
            stderr="",
        )

    monkeypatch.setattr(service_module, "_materialize_dispatch_worktree", flaky_materialize)

    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Retry the same pinned handoff after a failed claim"},
        )
        run = create_response.json()
        dispatch = client.post(f"/api/runs/{run['id']}/dispatches").json()

        first_claim_response = client.post(
            f"/api/runs/{run['id']}/dispatches/{dispatch['id']}/claim"
        )
        dispatches_after_failure = client.get(f"/api/runs/{run['id']}/dispatches")
        recovery_after_failure = client.get(f"/api/runs/{run['id']}/recovery")

        retry_claim_response = client.post(
            f"/api/runs/{run['id']}/dispatches/{dispatch['id']}/claim"
        )
        dispatches_after_retry = client.get(f"/api/runs/{run['id']}/dispatches")

    assert first_claim_response.status_code == 409
    failed_dispatch = dispatches_after_failure.json()[0]
    assert failed_dispatch["status"] == "claim_failed"
    assert "branch already exists" in failed_dispatch["status_detail"]
    assert Path(failed_dispatch["claim_stderr_path"]).exists()

    recovery = recovery_after_failure.json()
    assert recovery["can_advance"] is True
    assert recovery["latest_dispatch"]["status"] == "claim_failed"
    assert "claim failed" in recovery["summary"]
    assert any("retry the same pinned handoff" in hint for hint in recovery["restart_hints"])

    assert retry_claim_response.status_code == 200
    claimed_dispatch = retry_claim_response.json()
    assert claimed_dispatch["status"] == "claimed"
    assert Path(claimed_dispatch["worktree_path"]).exists()

    dispatches = dispatches_after_retry.json()
    assert dispatches[0]["status"] == "claimed"

    dispatch_log = Path(run["workspace_path"]) / "artifacts" / "dispatches.jsonl"
    records = [json.loads(line) for line in dispatch_log.read_text(encoding="utf-8").splitlines()]
    assert [record["status"] for record in records] == ["prepared", "claim_failed", "claimed"]


def test_execution_invalidates_prepared_dispatch(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Invalidate stale work orders when execution changes the task graph"},
        )
        run = create_response.json()

        dispatch_response = client.post(f"/api/runs/{run['id']}/dispatches")
        assert dispatch_response.status_code == 201

        advance_response = client.post(f"/api/runs/{run['id']}/advance")
        dispatches_response = client.get(f"/api/runs/{run['id']}/dispatches")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")
        detail_response = client.get(f"/api/runs/{run['id']}")

    assert advance_response.status_code == 200
    dispatches = dispatches_response.json()
    assert len(dispatches) == 1
    dispatch = dispatches[0]
    assert dispatch["status"] == "invalidated"
    assert "Execution changed the task graph" in dispatch["status_detail"]
    assert dispatch["updated_at"] != dispatch["created_at"]

    recovery = recovery_response.json()
    assert recovery["latest_dispatch"]["id"] == dispatch["id"]
    assert recovery["latest_dispatch"]["status"] == "invalidated"

    dispatch_log = Path(run["workspace_path"]) / "artifacts" / "dispatches.jsonl"
    records = [json.loads(line) for line in dispatch_log.read_text(encoding="utf-8").splitlines()]
    assert [record["status"] for record in records] == ["prepared", "invalidated"]

    detail = detail_response.json()
    assert any(
        "Invalidated 1 active dispatch record" in event["message"]
        for event in detail["events"]
    )


def test_recovery_invalidates_claimed_dispatch(tmp_path: Path, monkeypatch) -> None:
    from nexus_core import service as service_module

    def fake_materialize(settings, dispatch, command_argv):
        Path(dispatch.worktree_path).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            args=command_argv,
            returncode=0,
            stdout="claimed\n",
            stderr="",
        )

    monkeypatch.setattr(service_module, "_materialize_dispatch_worktree", fake_materialize)

    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Invalidate claimed dispatches when recovery changes the task graph"},
        )
        run = create_response.json()
        settings = client.app.state.settings
        dispatch = client.post(f"/api/runs/{run['id']}/dispatches").json()
        claim_response = client.post(f"/api/runs/{run['id']}/dispatches/{dispatch['id']}/claim")
        assert claim_response.status_code == 200

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = 'blocked',
                    last_error = 'Manual review is required before continuing'
                WHERE id = ? AND run_id = ?
                """,
                (dispatch["task_id"], run["id"]),
            )
            connection.execute(
                """
                UPDATE runs
                SET status = 'blocked'
                WHERE id = ?
                """,
                (run["id"],),
            )

        recover_response = client.post(
            f"/api/runs/{run['id']}/recover",
            json={"action": "requeue-task", "task_id": dispatch["task_id"]},
        )
        dispatches_response = client.get(f"/api/runs/{run['id']}/dispatches")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert recover_response.status_code == 200
    dispatches = dispatches_response.json()
    assert dispatches[0]["status"] == "invalidated"
    assert dispatches[0]["claim_stdout_path"] is not None
    assert dispatches[0]["claimed_at"] is not None

    recovery = recovery_response.json()
    assert recovery["latest_dispatch"]["status"] == "invalidated"

    dispatch_log = Path(run["workspace_path"]) / "artifacts" / "dispatches.jsonl"
    records = [json.loads(line) for line in dispatch_log.read_text(encoding="utf-8").splitlines()]
    assert [record["status"] for record in records] == ["prepared", "claimed", "invalidated"]


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


def test_failed_task_can_be_requeued_via_recover(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Recover a genuinely failed task back to ready"},
        )
        run = create_response.json()

        first_advance_response = client.post(f"/api/runs/{run['id']}/advance")
        assert first_advance_response.status_code == 200

        workspace = Path(run["workspace_path"])
        intent_path = workspace / "intent.md"
        intent_path.unlink()

        failed_advance_response = client.post(f"/api/runs/{run['id']}/advance")
        failed_execution = failed_advance_response.json()
        assert failed_advance_response.status_code == 200
        assert failed_execution["status"] == "failed"

        intent_path.write_text("# Run Intent\n\nRecovered intent\n", encoding="utf-8")
        recover_response = client.post(
            f"/api/runs/{run['id']}/recover",
            json={"action": "requeue-task", "task_id": run["tasks"][1]["id"]},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")
        resumed_advance_response = client.post(f"/api/runs/{run['id']}/advance")

    assert recover_response.status_code == 200
    payload = recover_response.json()
    assert payload["action"] == "requeue-task"
    assert payload["task_id"] == run["tasks"][1]["id"]

    detail = detail_response.json()
    assert detail["status"] == "ready"
    assert detail["tasks"][1]["status"] == "ready"
    assert detail["tasks"][1]["finished_at"] is None
    assert detail["tasks"][1]["last_error"] is None

    snapshot = recovery_response.json()
    assert snapshot["run_status"] == "ready"
    assert snapshot["can_advance"] is True
    assert snapshot["next_action"]["task_id"] == run["tasks"][1]["id"]
    assert snapshot["next_action"]["action"] == "read-intent"
    assert snapshot["last_execution"]["id"] == failed_execution["id"]
    assert snapshot["last_execution"]["status"] == "failed"
    assert snapshot["available_recovery_actions"] == []

    assert resumed_advance_response.status_code == 200
    assert resumed_advance_response.json()["status"] == "completed"
    assert resumed_advance_response.json()["action"] == "read-intent"


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


def test_dispatch_refuses_when_no_safe_target_exists(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Refuse to dispatch when the task graph is ambiguous"},
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

        dispatch_response = client.post(f"/api/runs/{run['id']}/dispatches")
        dispatches_response = client.get(f"/api/runs/{run['id']}/dispatches")

    assert dispatch_response.status_code == 409
    assert dispatch_response.json()["detail"] == "No safe dispatch target"
    assert dispatches_response.json() == []


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


def test_running_task_cannot_be_reexecuted(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Reject launching another execution for a running task"},
        )
        run = create_response.json()
        settings = client.app.state.settings

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = 'running'
                WHERE id = ? AND run_id = ?
                """,
                (run["tasks"][0]["id"], run["id"]),
            )
            connection.execute(
                """
                UPDATE runs
                SET status = 'running'
                WHERE id = ?
                """,
                (run["id"],),
            )

        blocked_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": run["tasks"][0]["id"], "action": "inspect-workspace"},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")

    assert blocked_response.status_code == 400
    assert blocked_response.json()["detail"] == "Task is already running"
    detail = detail_response.json()
    assert any("already running" in event["message"] for event in detail["events"])


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


def test_host_command_launch_failure_stays_recoverable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from nexus_core import service as service_module

    def raise_file_not_found(*_args, **_kwargs):
        raise FileNotFoundError("pwd missing")

    monkeypatch.setattr(service_module.subprocess, "run", raise_file_not_found)

    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Keep recovery usable when a host command cannot start"},
        )
        run = create_response.json()

        execution_response = client.post(
            f"/api/runs/{run['id']}/executions",
            json={"task_id": run["tasks"][0]["id"], "action": "inspect-workspace"},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert execution_response.status_code == 201
    execution = execution_response.json()
    assert execution["status"] == "failed"
    assert execution["exit_code"] == 127
    assert Path(execution["stdout_path"]).exists()
    assert Path(execution["stderr_path"]).exists()

    detail = detail_response.json()
    assert detail["status"] == "failed"
    assert detail["tasks"][0]["status"] == "failed"
    assert "pwd missing" in detail["tasks"][0]["last_error"]

    recovery = recovery_response.json()
    assert recovery["run_status"] == "failed"
    assert recovery["recovery_status"] == "attention_required"
    assert recovery["last_execution"]["id"] == execution["id"]
    assert recovery["last_execution"]["status"] == "failed"


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


def test_ambiguous_ready_tasks_can_be_normalized_via_recover(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Normalize multiple ready tasks safely"},
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

        recovery_before = client.get(f"/api/runs/{run['id']}/recovery")
        recover_response = client.post(
            f"/api/runs/{run['id']}/recover",
            json={"action": "select-ready-task", "task_id": run["tasks"][0]["id"]},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")
        recovery_after = client.get(f"/api/runs/{run['id']}/recovery")

    before_payload = recovery_before.json()
    assert len(before_payload["available_recovery_actions"]) == 2
    assert all(
        action["action"] == "select-ready-task"
        for action in before_payload["available_recovery_actions"]
    )

    assert recover_response.status_code == 200
    detail = detail_response.json()
    assert detail["tasks"][0]["status"] == "ready"
    assert detail["tasks"][1]["status"] == "pending"

    snapshot = recovery_after.json()
    assert snapshot["run_status"] == "ready"
    assert snapshot["can_advance"] is True
    assert snapshot["blocking_reason"] is None
    assert snapshot["next_action"]["task_id"] == run["tasks"][0]["id"]
    assert snapshot["available_recovery_actions"] == []


def test_blocked_task_can_be_requeued_via_recover(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Resume a blocked task through the recovery API"},
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

        recovery_before = client.get(f"/api/runs/{run['id']}/recovery")
        recover_response = client.post(
            f"/api/runs/{run['id']}/recover",
            json={"action": "requeue-task", "task_id": run["tasks"][0]["id"]},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")
        recovery_after = client.get(f"/api/runs/{run['id']}/recovery")

    before_payload = recovery_before.json()
    assert before_payload["current_task"]["status"] == "blocked"
    assert any(
        action["action"] == "requeue-task"
        and action["task_id"] == run["tasks"][0]["id"]
        for action in before_payload["available_recovery_actions"]
    )

    assert recover_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "ready"
    assert detail["tasks"][0]["status"] == "ready"
    assert detail["tasks"][0]["last_error"] is None

    snapshot = recovery_after.json()
    assert snapshot["recovery_status"] == "ready"
    assert snapshot["can_advance"] is True
    assert snapshot["next_action"]["action"] == "inspect-workspace"
    assert snapshot["available_recovery_actions"] == []


def test_recovery_action_fails_closed_on_invalid_target(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        create_response = client.post(
            "/api/requests",
            json={"intent": "Reject invalid recovery targets"},
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

        recover_response = client.post(
            f"/api/runs/{run['id']}/recover",
            json={"action": "select-ready-task", "task_id": run["tasks"][2]["id"]},
        )
        detail_response = client.get(f"/api/runs/{run['id']}")
        recovery_response = client.get(f"/api/runs/{run['id']}/recovery")

    assert recover_response.status_code == 400
    assert "not allowed" in recover_response.json()["detail"]
    detail = detail_response.json()
    assert detail["tasks"][0]["status"] == "ready"
    assert detail["tasks"][1]["status"] == "ready"
    assert detail["tasks"][2]["status"] == "pending"

    snapshot = recovery_response.json()
    assert snapshot["recovery_status"] == "attention_required"
    recovery_actions_log = Path(snapshot["artifact_paths"]["recovery_actions"])
    last_record = json.loads(recovery_actions_log.read_text(encoding="utf-8").splitlines()[-1])
    assert last_record["status"] == "blocked"


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
