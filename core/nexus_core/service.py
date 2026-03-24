from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .db import connect
from .models import (
    ActionDescriptor,
    CreateExecutionRequest,
    CreateRunRequest,
    DispatchRecord,
    EventRecord,
    ExecutionRecord,
    NextActionRecord,
    RecoveryActionOption,
    RecoveryActionRequest,
    RecoveryActionResult,
    RecoveryArtifactPaths,
    RecoveryDecisionSummary,
    RecoverySnapshot,
    RecoveryTaskSummary,
    RunDetail,
    RunSummary,
    SystemSummary,
    TaskRecord,
)

DEFAULT_TASKS: tuple[tuple[str, str], ...] = (
    ("intake", "Record request and local constraints"),
    ("planning", "Create the initial execution graph"),
    ("architecture", "Define boundaries, data flow, and safety limits"),
    ("implementation", "Prepare the next runnable execution slice"),
    ("verification", "Validate artifacts, logs, and remaining risks"),
)

AGENT_ROLES = [
    {"role": "planner", "focus": "turn natural language intent into an execution path"},
    {"role": "architect", "focus": "shape boundaries, interfaces, and constraints"},
    {"role": "implementer", "focus": "build the next narrow runnable slice"},
    {"role": "reviewer", "focus": "check quality, safety, and recoverability"},
]

ACTION_CATALOG: dict[str, dict[str, object]] = {
    "inspect-workspace": {
        "argv": ["pwd"],
        "description": "Confirm the active run workspace path.",
        "task_kinds": {"intake"},
    },
    "list-root": {
        "argv": ["ls", "-la"],
        "description": "Inspect the root of the run workspace.",
        "task_kinds": {"intake", "implementation", "verification"},
    },
    "list-artifacts": {
        "argv": ["ls", "-la", "artifacts"],
        "description": "Inspect generated artifacts for the run.",
        "task_kinds": {"planning", "architecture", "verification"},
    },
    "read-intent": {
        "argv": ["cat", "intent.md"],
        "description": "Read the run intent captured at registration time.",
        "task_kinds": {"intake", "planning", "architecture"},
    },
}

DEFAULT_ACTION_BY_TASK_KIND: dict[str, str] = {
    "intake": "inspect-workspace",
    "planning": "read-intent",
    "architecture": "list-artifacts",
    "implementation": "list-root",
    "verification": "list-artifacts",
}

RECOVERY_ARTIFACT_NAME = "run-recovery.json"
RECOVERY_ACTIONS_ARTIFACT_NAME = "recovery-actions.jsonl"
DISPATCHES_ARTIFACT_NAME = "dispatches.jsonl"

DEFAULT_AGENT_ROLE_BY_TASK_KIND: dict[str, str] = {
    "intake": "planner",
    "planning": "planner",
    "architecture": "architect",
    "implementation": "implementer",
    "verification": "reviewer",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def list_action_descriptors() -> list[ActionDescriptor]:
    descriptors: list[ActionDescriptor] = []
    for action, spec in ACTION_CATALOG.items():
        descriptors.append(
            ActionDescriptor(
                action=action,
                description=str(spec["description"]),
                command_argv=list(spec["argv"]),
                task_kinds=sorted(spec["task_kinds"]),
            )
        )
    return descriptors


def create_run(settings: Settings, request: CreateRunRequest) -> RunDetail:
    run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
    created_at = utc_now()
    workspace = settings.workspace_root / run_id
    artifacts_dir = workspace / "artifacts"
    executions_dir = workspace / "executions"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    executions_dir.mkdir(parents=True, exist_ok=True)

    tasks: list[TaskRecord] = []
    for index, (kind, title) in enumerate(DEFAULT_TASKS):
        tasks.append(
            TaskRecord(
                id=f"{run_id}_{kind}",
                kind=kind,
                title=title,
                status="ready" if index == 0 else "pending",
                position=index,
            )
        )

    with connect(settings) as connection:
        connection.execute(
            """
            INSERT INTO runs (id, intent, status, created_at, workspace_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, request.intent, "ready", created_at, str(workspace)),
        )
        connection.executemany(
            """
            INSERT INTO tasks (
                id, run_id, kind, title, status, position, started_at, finished_at, last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    task.id,
                    run_id,
                    task.kind,
                    task.title,
                    task.status,
                    task.position,
                    task.started_at,
                    task.finished_at,
                    task.last_error,
                )
                for task in tasks
            ],
        )
        _log_event(connection, run_id, "info", "Run created from user intent", created_at)
        _log_event(
            connection,
            run_id,
            "info",
            "Workspace prepared for local-first execution",
            utc_now(),
        )
        _log_event(connection, run_id, "info", "Initial task graph materialized", utc_now())

    _write_initial_artifacts(workspace, request.intent, tasks, created_at)
    _persist_recovery_snapshot(settings, run_id)
    return get_run(settings, run_id)


def list_runs(settings: Settings) -> list[RunSummary]:
    with connect(settings) as connection:
        rows = connection.execute(
            """
            SELECT id, intent, status, created_at, workspace_path
            FROM runs
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [RunSummary(**dict(row)) for row in rows]


def get_run(settings: Settings, run_id: str) -> RunDetail:
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        task_rows = connection.execute(
            """
            SELECT id, kind, title, status, position, started_at, finished_at, last_error
            FROM tasks
            WHERE run_id = ?
            ORDER BY position ASC
            """,
            (run_id,),
        ).fetchall()
        event_rows = connection.execute(
            """
            SELECT id, level, message, created_at
            FROM events
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()

    return RunDetail(
        **dict(run_row),
        tasks=[_task_from_row(row) for row in task_rows],
        events=[EventRecord(**dict(row)) for row in event_rows],
    )


def get_system_summary(settings: Settings) -> SystemSummary:
    runs = list_runs(settings)
    latest = runs[0].id if runs else None
    return SystemSummary(
        run_count=len(runs),
        latest_run_id=latest,
        workspace_root=str(settings.workspace_root),
    )


def recommend_next_action(settings: Settings, run_id: str) -> NextActionRecord:
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        recommendation, _ = _resolve_next_action(connection, run_row)
    if recommendation is None:
        raise ValueError("No safe next action")
    return recommendation


def get_recovery_snapshot(settings: Settings, run_id: str) -> RecoverySnapshot:
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        return _build_recovery_snapshot(connection, run_row)


def create_dispatch(settings: Settings, run_id: str) -> DispatchRecord:
    created_at = utc_now()
    base_commit = _resolve_repo_head(settings)
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        recommendation, _ = _resolve_next_action(connection, run_row)
        if recommendation is None:
            raise ValueError("No safe dispatch target")

        workspace = Path(run_row["workspace_path"])
        existing_dispatch, superseded_count = _reconcile_prepared_dispatches(
            connection,
            workspace,
            run_id,
            task_id=recommendation.task_id,
            base_commit=base_commit,
            updated_at=created_at,
        )
        if existing_dispatch is not None:
            if superseded_count:
                _log_event(
                    connection,
                    run_id,
                    "decision",
                    (
                        f"Superseded {superseded_count} stale prepared dispatch record(s) "
                        f"before reusing dispatch '{existing_dispatch.id}'."
                    ),
                    created_at,
                )
                _write_recovery_snapshot(
                    workspace,
                    _build_recovery_snapshot(connection, _fetch_run_row(connection, run_id)),
                )
            return existing_dispatch

        dispatch = _build_dispatch_record(
            settings,
            run_row,
            recommendation,
            base_commit=base_commit,
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO dispatches (
                id, run_id, task_id, task_kind, task_title, agent_role, branch_name,
                worktree_name, worktree_path, repo_root, base_commit, prompt_path,
                startup_commands_json, status, status_detail, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dispatch.id,
                dispatch.run_id,
                dispatch.task_id,
                dispatch.task_kind,
                dispatch.task_title,
                dispatch.agent_role,
                dispatch.branch_name,
                dispatch.worktree_name,
                dispatch.worktree_path,
                dispatch.repo_root,
                dispatch.base_commit,
                dispatch.prompt_path,
                json.dumps(dispatch.startup_commands),
                dispatch.status,
                dispatch.status_detail,
                dispatch.created_at,
                dispatch.updated_at,
            ),
        )
        _write_dispatch_prompt(
            workspace,
            dispatch,
            intent=str(run_row["intent"]),
            recommendation=recommendation,
        )
        _append_dispatch_record(workspace, dispatch)
        if superseded_count:
            _log_event(
                connection,
                run_id,
                "decision",
                (
                    f"Superseded {superseded_count} stale prepared dispatch record(s) "
                    "before preparing a new pinned dispatch."
                ),
                created_at,
            )
        _log_event(
            connection,
            run_id,
            "decision",
            (
                f"Prepared dispatch '{dispatch.id}' for task '{dispatch.task_title}' "
                f"with agent role '{dispatch.agent_role}'."
            ),
            created_at,
        )
        _write_recovery_snapshot(
            workspace,
            _build_recovery_snapshot(connection, _fetch_run_row(connection, run_id)),
        )

    return dispatch


def list_dispatches(settings: Settings, run_id: str) -> list[DispatchRecord]:
    with connect(settings) as connection:
        _fetch_run_row(connection, run_id)
        rows = connection.execute(
            """
            SELECT id, run_id, task_id, task_kind, task_title, agent_role, branch_name,
                   worktree_name, worktree_path, repo_root, base_commit, prompt_path,
                   startup_commands_json, status, status_detail, created_at, updated_at
            FROM dispatches
            WHERE run_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (run_id,),
        ).fetchall()
    return [_dispatch_from_row(row) for row in rows]


def recover_run(
    settings: Settings,
    run_id: str,
    request: RecoveryActionRequest,
) -> RecoveryActionResult:
    created_at = utc_now()
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        workspace = Path(run_row["workspace_path"])
        task_rows = _fetch_task_rows(connection, run_id)
        available_actions = _available_recovery_actions(
            task_rows,
            run_status=str(run_row["status"]),
        )
        summary = _apply_recovery_action(
            connection,
            run_row,
            task_rows,
            available_actions,
            request,
            created_at,
        )
        invalidated_dispatches = _invalidate_prepared_dispatches(
            connection,
            workspace,
            run_id,
            detail="Recovery changed the task graph after the dispatch was prepared.",
            updated_at=created_at,
        )
        if invalidated_dispatches:
            _log_event(
                connection,
                run_id,
                "decision",
                (
                    f"Invalidated {len(invalidated_dispatches)} prepared dispatch record(s) "
                    "after recovery changed task state."
                ),
                created_at,
            )
        _update_run_status(connection, run_id)
        updated_run_row = _fetch_run_row(connection, run_id)
        snapshot = _build_recovery_snapshot(connection, updated_run_row)
        _append_recovery_action_record(
            workspace,
            {
                "created_at": created_at,
                "run_id": run_id,
                "action": request.action,
                "task_id": request.task_id,
                "status": "applied",
                "summary": summary,
                "run_status": snapshot.run_status,
                "can_advance": snapshot.can_advance,
            },
        )
        _write_recovery_snapshot(workspace, snapshot)

    return RecoveryActionResult(
        run_id=run_id,
        action=request.action,
        task_id=request.task_id,
        summary=summary,
        updated_at=created_at,
        recovery=snapshot,
    )


def advance_run(settings: Settings, run_id: str) -> ExecutionRecord:
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        recommendation, problem = _resolve_next_action(connection, run_row)
        created_at = utc_now()
        workspace = Path(run_row["workspace_path"])

        if recommendation is None:
            warning = problem or "No safe next action"
            _log_event(connection, run_id, "warning", warning, created_at)
            _append_advance_record(
                workspace,
                {
                    "created_at": created_at,
                    "run_id": run_id,
                    "status": "blocked",
                    "detail": warning,
                },
            )
            _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
            connection.commit()
            raise ValueError("No safe next action")

        _append_advance_record(
            workspace,
            {
                "created_at": created_at,
                "status": "recommended",
                **recommendation.model_dump(),
            },
        )

    return create_execution(
        settings,
        run_id,
        CreateExecutionRequest(
            task_id=recommendation.task_id,
            action=recommendation.action,
        ),
        planned=True,
    )


def create_execution(
    settings: Settings,
    run_id: str,
    request: CreateExecutionRequest,
    *,
    planned: bool = False,
) -> ExecutionRecord:
    start_time = utc_now()
    action_spec = ACTION_CATALOG.get(request.action)
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        workspace = Path(run_row["workspace_path"])
        if not request.task_id:
            _block_execution_action(
                connection,
                run_id,
                f"Blocked execution action '{request.action}' without task scope.",
                start_time,
            )
            _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
            connection.commit()
            raise ValueError("task_id is required")
        task_row = _fetch_task_row(connection, run_id, request.task_id)

        if action_spec is None:
            _block_execution_action(
                connection,
                run_id,
                f"Blocked execution action '{request.action}'.",
                start_time,
            )
            _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
            connection.commit()
            raise ValueError(f"Action '{request.action}' is not allowed")

        if task_row["status"] == "running":
            _block_execution_action(
                connection,
                run_id,
                (
                    f"Blocked execution action '{request.action}' because task "
                    f"'{task_row['title']}' is already running."
                ),
                start_time,
            )
            _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
            connection.commit()
            raise ValueError("Task is already running")
        if task_row["status"] != "ready":
            _block_execution_action(
                connection,
                run_id,
                (
                    f"Blocked execution action '{request.action}' because task "
                    f"'{task_row['title']}' is in status '{task_row['status']}'."
                ),
                start_time,
            )
            _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
            connection.commit()
            raise ValueError("Task must be ready or running before execution")
        allowed_actions = _available_actions_for_kind(str(task_row["kind"]))
        if request.action not in allowed_actions:
            _block_execution_action(
                connection,
                run_id,
                (
                    f"Blocked execution action '{request.action}' for task "
                    f"'{task_row['title']}'."
                ),
                start_time,
            )
            _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
            connection.commit()
            raise ValueError(
                f"Action '{request.action}' is not allowed for task kind '{task_row['kind']}'"
            )

        execution_id = f"exec_{uuid4().hex[:12]}"
        cwd = str(workspace)
        stdout_path = workspace / "executions" / execution_id / "stdout.txt"
        stderr_path = workspace / "executions" / execution_id / "stderr.txt"
        stdout_path.parent.mkdir(parents=True, exist_ok=True)

        claimed_task = connection.execute(
            """
            UPDATE tasks
            SET status = 'running',
                started_at = COALESCE(started_at, ?),
                last_error = NULL
            WHERE id = ? AND run_id = ? AND status = 'ready'
            """,
            (start_time, task_row["id"], run_id),
        )
        if claimed_task.rowcount != 1:
            _block_execution_action(
                connection,
                run_id,
                (
                    f"Blocked execution action '{request.action}' because task "
                    f"'{task_row['title']}' could not be claimed safely."
                ),
                start_time,
            )
            _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
            connection.commit()
            raise ValueError("Task could not be claimed for execution")
        if planned:
            _log_event(
                connection,
                run_id,
                "decision",
                (
                    f"Planner selected action '{request.action}' for task "
                    f"'{task_row['id']}' after it was claimed safely."
                ),
                start_time,
            )
        _log_event(
            connection,
            run_id,
            "info",
            f"Task '{task_row['title']}' entered running state.",
            start_time,
        )
        connection.execute(
            """
            UPDATE runs
            SET status = 'running'
            WHERE id = ?
            """,
            (run_id,),
        )

    completed = _run_mapped_action(workspace, list(action_spec["argv"]))
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    finish_time = utc_now()
    execution_status = "completed" if completed.returncode == 0 else "failed"

    with connect(settings) as connection:
        connection.execute(
            """
            INSERT INTO executions (
                id, run_id, task_id, action, status, command_argv_json, cwd,
                started_at, finished_at, exit_code, stdout_path, stderr_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                run_id,
                request.task_id,
                request.action,
                execution_status,
                json.dumps(action_spec["argv"]),
                cwd,
                start_time,
                finish_time,
                completed.returncode,
                str(stdout_path),
                str(stderr_path),
            ),
        )
        _log_event(
            connection,
            run_id,
            "info" if completed.returncode == 0 else "warning",
            f"Execution '{request.action}' finished with exit code {completed.returncode}.",
            finish_time,
        )

        if completed.returncode == 0:
            connection.execute(
                """
                UPDATE tasks
                SET status = 'completed',
                    finished_at = ?,
                    last_error = NULL
                WHERE id = ? AND run_id = ?
                """,
                (finish_time, request.task_id, run_id),
            )
            task_position = int(
                _fetch_task_row(connection, run_id, request.task_id)["position"]
            )
            _log_event(
                connection,
                run_id,
                "info",
                f"Task execution succeeded for '{request.action}'.",
                finish_time,
            )
            _advance_next_task(connection, run_id, task_position + 1, finish_time)
        else:
            connection.execute(
                """
                UPDATE tasks
                SET status = 'failed',
                    finished_at = ?,
                    last_error = ?
                WHERE id = ? AND run_id = ?
                """,
                (finish_time, _last_error_message(completed.stderr), request.task_id, run_id),
            )
            _log_event(
                connection,
                run_id,
                "warning",
                f"Task execution failed for '{request.action}'.",
                finish_time,
            )
        invalidated_dispatches = _invalidate_prepared_dispatches(
            connection,
            workspace,
            run_id,
            detail="Execution changed the task graph after the dispatch was prepared.",
            updated_at=finish_time,
        )
        if invalidated_dispatches:
            _log_event(
                connection,
                run_id,
                "decision",
                (
                    f"Invalidated {len(invalidated_dispatches)} prepared dispatch record(s) "
                    "after execution changed task state."
                ),
                finish_time,
            )
        _update_run_status(connection, run_id)
        _write_recovery_snapshot(
            workspace,
            _build_recovery_snapshot(connection, _fetch_run_row(connection, run_id)),
        )

    return get_execution(settings, run_id, execution_id)


def list_executions(settings: Settings, run_id: str) -> list[ExecutionRecord]:
    with connect(settings) as connection:
        _fetch_run_row(connection, run_id)
        rows = connection.execute(
            """
            SELECT id, run_id, task_id, action, status, command_argv_json, cwd,
                   started_at, finished_at, exit_code, stdout_path, stderr_path
            FROM executions
            WHERE run_id = ?
            ORDER BY started_at ASC, id ASC
            """,
            (run_id,),
        ).fetchall()
    return [_execution_from_row(row) for row in rows]


def get_execution(settings: Settings, run_id: str, execution_id: str) -> ExecutionRecord:
    with connect(settings) as connection:
        _fetch_run_row(connection, run_id)
        row = connection.execute(
            """
            SELECT id, run_id, task_id, action, status, command_argv_json, cwd,
                   started_at, finished_at, exit_code, stdout_path, stderr_path
            FROM executions
            WHERE run_id = ? AND id = ?
            """,
            (run_id, execution_id),
        ).fetchone()
    if row is None:
        raise KeyError(execution_id)
    return _execution_from_row(row)


def _run_mapped_action(workspace: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": "C.UTF-8",
    }
    try:
        return subprocess.run(
            command,
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = (error.stderr or "") + "\nExecution timed out after 15 seconds."
        return subprocess.CompletedProcess(
            args=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr.strip(),
        )
    except OSError as error:
        return subprocess.CompletedProcess(
            args=command,
            returncode=127,
            stdout="",
            stderr=f"{error.__class__.__name__}: {error}",
        )


def _write_initial_artifacts(
    workspace: Path,
    intent: str,
    tasks: list[TaskRecord],
    created_at: str,
) -> None:
    (workspace / "intent.md").write_text(f"# Run Intent\n\n{intent}\n", encoding="utf-8")
    payload = {
        "created_at": created_at,
        "workflow": "local-first-native",
        "tasks": [task.model_dump() for task in tasks],
    }
    (workspace / "artifacts" / "initial-plan.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _append_advance_record(workspace: Path, payload: dict[str, object]) -> None:
    artifact_path = workspace / "artifacts" / "advance-decisions.jsonl"
    with artifact_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload))
        handle.write("\n")


def _append_recovery_action_record(workspace: Path, payload: dict[str, object]) -> None:
    artifact_path = workspace / "artifacts" / RECOVERY_ACTIONS_ARTIFACT_NAME
    with artifact_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload))
        handle.write("\n")


def _append_dispatch_record(workspace: Path, dispatch: DispatchRecord) -> None:
    artifact_path = workspace / "artifacts" / DISPATCHES_ARTIFACT_NAME
    with artifact_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dispatch.model_dump(mode="json")))
        handle.write("\n")


def _persist_recovery_snapshot(settings: Settings, run_id: str) -> None:
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        workspace = Path(run_row["workspace_path"])
        _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))


def _write_recovery_snapshot(workspace: Path, snapshot: RecoverySnapshot) -> None:
    artifact_path = workspace / "artifacts" / RECOVERY_ARTIFACT_NAME
    artifact_path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )


def _resolve_repo_head(settings: Settings) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=settings.repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    commit = completed.stdout.strip()
    if completed.returncode != 0 or not commit:
        raise ValueError("Cannot prepare dispatch without a pinned git commit")
    return commit


def _recovery_artifact_paths(workspace: Path) -> RecoveryArtifactPaths:
    return RecoveryArtifactPaths(
        intent=str(workspace / "intent.md"),
        initial_plan=str(workspace / "artifacts" / "initial-plan.json"),
        advance_log=str(workspace / "artifacts" / "advance-decisions.jsonl"),
        dispatches=str(workspace / "artifacts" / DISPATCHES_ARTIFACT_NAME),
        recovery_actions=str(workspace / "artifacts" / RECOVERY_ACTIONS_ARTIFACT_NAME),
        recovery_snapshot=str(workspace / "artifacts" / RECOVERY_ARTIFACT_NAME),
    )


def _build_dispatch_record(
    settings: Settings,
    run_row: sqlite3.Row,
    recommendation: NextActionRecord,
    *,
    base_commit: str,
    created_at: str,
) -> DispatchRecord:
    dispatch_id = f"dispatch_{uuid4().hex[:12]}"
    worktree_name = _dispatch_worktree_name(run_row["id"], recommendation.task_kind)
    worktree_path = settings.worktree_root / worktree_name
    prompt_path = Path(run_row["workspace_path"]) / "artifacts" / "dispatches" / (
        f"{dispatch_id}.md"
    )
    return DispatchRecord(
        id=dispatch_id,
        run_id=str(run_row["id"]),
        task_id=recommendation.task_id,
        task_kind=recommendation.task_kind,
        task_title=recommendation.task_title,
        agent_role=DEFAULT_AGENT_ROLE_BY_TASK_KIND.get(
            recommendation.task_kind,
            "implementer",
        ),
        branch_name=f"codex/{worktree_name}",
        worktree_name=worktree_name,
        worktree_path=str(worktree_path),
        repo_root=str(settings.repo_root),
        base_commit=base_commit,
        prompt_path=str(prompt_path),
        startup_commands=[
            f"make worktree NAME={worktree_name} BASE_REF={base_commit}",
            f"cd .worktrees/{worktree_name}",
        ],
        status="prepared",
        status_detail="Prepared for the current safe task and pinned to a git commit.",
        created_at=created_at,
        updated_at=created_at,
    )


def _dispatch_worktree_name(run_id: object, task_kind: str) -> str:
    run_slug = str(run_id).replace("_", "-")
    if len(run_slug) > 24:
        run_slug = run_slug[-24:]
    return f"{run_slug}-{task_kind}"


def _write_dispatch_prompt(
    workspace: Path,
    dispatch: DispatchRecord,
    *,
    intent: str,
    recommendation: NextActionRecord,
) -> None:
    prompt_path = Path(dispatch.prompt_path)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(
        "\n".join(
            [
                f"# Dispatch Work Order: {dispatch.id}",
                "",
                f"- Run: {dispatch.run_id}",
                f"- Task: {dispatch.task_title} ({dispatch.task_kind})",
                f"- Agent Role: {dispatch.agent_role}",
                f"- Suggested Action: {recommendation.action}",
                f"- Suggested Command: {' '.join(recommendation.command_argv)}",
                f"- Base Commit: {dispatch.base_commit}",
                "",
                "## Intent",
                intent,
                "",
                "## Startup",
                *[f"- {command}" for command in dispatch.startup_commands],
                "",
                "## Context",
                f"- Workspace: {workspace}",
                f"- Repo Root: {dispatch.repo_root}",
                f"- Prompt Path: {dispatch.prompt_path}",
                f"- Worktree Path: {dispatch.worktree_path}",
                "- Note: the worktree bootstraps from the pinned base commit above.",
                "- Note: commit any required local changes before materializing the worktree.",
            ]
        ),
        encoding="utf-8",
    )


def _reconcile_prepared_dispatches(
    connection: sqlite3.Connection,
    workspace: Path,
    run_id: str,
    *,
    task_id: str,
    base_commit: str,
    updated_at: str,
) -> tuple[DispatchRecord | None, int]:
    rows = connection.execute(
        """
        SELECT id, run_id, task_id, task_kind, task_title, agent_role, branch_name,
               worktree_name, worktree_path, repo_root, base_commit, prompt_path,
               startup_commands_json, status, status_detail, created_at, updated_at
        FROM dispatches
        WHERE run_id = ? AND status = 'prepared'
        ORDER BY created_at DESC, id DESC
        """,
        (run_id,),
    ).fetchall()

    active_dispatch: DispatchRecord | None = None
    superseded_count = 0
    for row in rows:
        dispatch = _dispatch_from_row(row)
        if (
            active_dispatch is None
            and dispatch.task_id == task_id
            and dispatch.base_commit == base_commit
        ):
            active_dispatch = dispatch
            continue

        superseded = _update_dispatch_status(
            connection,
            dispatch,
            status="superseded",
            detail="Superseded by a newer or different safe dispatch target.",
            updated_at=updated_at,
        )
        _append_dispatch_record(workspace, superseded)
        superseded_count += 1

    return active_dispatch, superseded_count


def _invalidate_prepared_dispatches(
    connection: sqlite3.Connection,
    workspace: Path,
    run_id: str,
    *,
    detail: str,
    updated_at: str,
) -> list[DispatchRecord]:
    rows = connection.execute(
        """
        SELECT id, run_id, task_id, task_kind, task_title, agent_role, branch_name,
               worktree_name, worktree_path, repo_root, base_commit, prompt_path,
               startup_commands_json, status, status_detail, created_at, updated_at
        FROM dispatches
        WHERE run_id = ? AND status = 'prepared'
        ORDER BY created_at ASC, id ASC
        """,
        (run_id,),
    ).fetchall()

    invalidated: list[DispatchRecord] = []
    for row in rows:
        dispatch = _dispatch_from_row(row)
        updated = _update_dispatch_status(
            connection,
            dispatch,
            status="invalidated",
            detail=detail,
            updated_at=updated_at,
        )
        _append_dispatch_record(workspace, updated)
        invalidated.append(updated)
    return invalidated


def _update_dispatch_status(
    connection: sqlite3.Connection,
    dispatch: DispatchRecord,
    *,
    status: str,
    detail: str,
    updated_at: str,
) -> DispatchRecord:
    updated_dispatch = dispatch.model_copy(
        update={
            "status": status,
            "status_detail": detail,
            "updated_at": updated_at,
        }
    )
    connection.execute(
        """
        UPDATE dispatches
        SET status = ?, status_detail = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, detail, updated_at, dispatch.id),
    )
    return updated_dispatch


def _fetch_run_row(connection: sqlite3.Connection, run_id: str) -> sqlite3.Row:
    run_row = connection.execute(
        """
        SELECT id, intent, status, created_at, workspace_path
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if run_row is None:
        raise KeyError(run_id)
    return run_row


def _fetch_task_row(
    connection: sqlite3.Connection,
    run_id: str,
    task_id: str,
) -> sqlite3.Row:
    task_row = connection.execute(
        """
        SELECT id, run_id, kind, title, status, position, started_at, finished_at, last_error
        FROM tasks
        WHERE run_id = ? AND id = ?
        """,
        (run_id, task_id),
    ).fetchone()
    if task_row is None:
        raise KeyError(task_id)
    return task_row


def _fetch_task_rows(connection: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT id, kind, title, status, position, started_at, finished_at, last_error
        FROM tasks
        WHERE run_id = ?
        ORDER BY position ASC
        """,
        (run_id,),
    ).fetchall()


def _task_from_row(row: sqlite3.Row) -> TaskRecord:
    payload = dict(row)
    payload["available_actions"] = _available_actions_for_kind(str(row["kind"]))
    return TaskRecord(**payload)


def _resolve_next_action(
    connection: sqlite3.Connection,
    run_row: sqlite3.Row,
) -> tuple[NextActionRecord | None, str | None]:
    run_id = str(run_row["id"])
    task_rows = connection.execute(
        """
        SELECT id, kind, title, status, position, started_at, finished_at, last_error
        FROM tasks
        WHERE run_id = ?
        ORDER BY position ASC
        """,
        (run_id,),
    ).fetchall()
    statuses = [str(row["status"]) for row in task_rows]
    ready_rows = [row for row in task_rows if row["status"] == "ready"]

    if str(run_row["status"]) in {"failed", "completed"}:
        return None, (
            f"No safe next action for run '{run_id}' because the run status is "
            f"'{run_row['status']}'."
        )
    if "failed" in statuses:
        return None, f"No safe next action for run '{run_id}' because a task has failed."
    if "running" in statuses:
        return None, f"No safe next action for run '{run_id}' because a task is running."
    if "blocked" in statuses:
        return None, f"No safe next action for run '{run_id}' because a task is blocked."
    if len(ready_rows) != 1:
        return None, (
            f"No safe next action for run '{run_id}' because there are {len(ready_rows)} "
            "ready tasks."
        )

    task_row = ready_rows[0]
    task_kind = str(task_row["kind"])
    action = DEFAULT_ACTION_BY_TASK_KIND.get(task_kind)
    if action is None:
        return None, (
            f"No safe next action for run '{run_id}' because task kind '{task_kind}' "
            "has no default safe action."
        )

    available_actions = _available_actions_for_kind(task_kind)
    if action not in available_actions:
        return None, (
            f"No safe next action for run '{run_id}' because action '{action}' is not "
            f"available for task kind '{task_kind}'."
        )

    return (
        NextActionRecord(
            run_id=run_id,
            task_id=str(task_row["id"]),
            task_kind=task_kind,
            task_title=str(task_row["title"]),
            action=action,
            command_argv=list(ACTION_CATALOG[action]["argv"]),
            available_actions=available_actions,
            reason=(
                f"it is the default safe action for the only ready task kind "
                f"'{task_kind}'."
            ),
        ),
        None,
    )


def _available_recovery_actions(
    task_rows: list[sqlite3.Row],
    *,
    run_status: str,
) -> list[RecoveryActionOption]:
    statuses = [str(row["status"]) for row in task_rows]
    ready_rows = [row for row in task_rows if row["status"] == "ready"]
    actions: list[RecoveryActionOption] = []

    if run_status not in {"running", "completed"} and "running" not in statuses:
        for row in task_rows:
            if row["status"] in {"failed", "blocked"}:
                actions.append(
                    RecoveryActionOption(
                        action="requeue-task",
                        task_id=str(row["id"]),
                        task_title=str(row["title"]),
                        task_status=str(row["status"]),
                        description=(
                            "Reset this failed or blocked task back to ready after repairing "
                            "its inputs or artifacts."
                        ),
                    )
                )

        if len(ready_rows) > 1 and not any(
            row["status"] in {"failed", "blocked"} for row in task_rows
        ):
            for row in ready_rows:
                actions.append(
                    RecoveryActionOption(
                        action="select-ready-task",
                        task_id=str(row["id"]),
                        task_title=str(row["title"]),
                        task_status=str(row["status"]),
                        description=(
                            "Keep this task ready and move all other ready tasks back to "
                            "pending."
                        ),
                    )
                )

    return actions


def _apply_recovery_action(
    connection: sqlite3.Connection,
    run_row: sqlite3.Row,
    task_rows: list[sqlite3.Row],
    available_actions: list[RecoveryActionOption],
    request: RecoveryActionRequest,
    created_at: str,
) -> str:
    run_id = str(run_row["id"])
    workspace = Path(run_row["workspace_path"])
    allowed_pairs = {(item.action, item.task_id) for item in available_actions}
    pair = (request.action, request.task_id)
    if pair not in allowed_pairs:
        _log_event(
            connection,
            run_id,
            "warning",
            (
                f"Blocked recovery action '{request.action}'"
                + (f" for task '{request.task_id}'." if request.task_id else ".")
            ),
            created_at,
        )
        _append_recovery_action_record(
            workspace,
            {
                "created_at": created_at,
                "run_id": run_id,
                "action": request.action,
                "task_id": request.task_id,
                "status": "blocked",
                "detail": "Recovery action is not allowed for the current run state.",
            },
        )
        _write_recovery_snapshot(workspace, _build_recovery_snapshot(connection, run_row))
        connection.commit()
        raise ValueError("Recovery action is not allowed for the current run state")

    if request.task_id is None:
        raise ValueError("task_id is required for recovery actions")

    target_row = _fetch_task_row(connection, run_id, request.task_id)
    if request.action == "requeue-task":
        connection.execute(
            """
            UPDATE tasks
            SET status = 'ready',
                started_at = NULL,
                finished_at = NULL,
                last_error = NULL
            WHERE id = ? AND run_id = ?
            """,
            (request.task_id, run_id),
        )
        summary = (
            f"Recovery requeued task '{target_row['title']}' and restored it to ready state."
        )
    elif request.action == "select-ready-task":
        connection.execute(
            """
            UPDATE tasks
            SET status = CASE WHEN id = ? THEN 'ready' ELSE 'pending' END
            WHERE run_id = ? AND status = 'ready'
            """,
            (request.task_id, run_id),
        )
        summary = (
            f"Recovery kept task '{target_row['title']}' ready and normalized other "
            "ready tasks back to pending."
        )
    else:
        raise ValueError(f"Unknown recovery action '{request.action}'")

    _log_event(connection, run_id, "decision", summary, created_at)
    return summary


def _build_recovery_snapshot(
    connection: sqlite3.Connection,
    run_row: sqlite3.Row,
) -> RecoverySnapshot:
    run_id = str(run_row["id"])
    run_status = str(run_row["status"])
    workspace = Path(run_row["workspace_path"])
    task_rows = _fetch_task_rows(connection, run_id)
    next_action, problem = _resolve_next_action(connection, run_row)
    current_task = _recovery_current_task(task_rows, next_action)
    last_execution = _fetch_latest_execution(connection, run_id)
    latest_dispatch = _fetch_latest_dispatch(connection, run_id)
    latest_decision = _read_latest_decision_summary(workspace)
    available_recovery_actions = _available_recovery_actions(
        task_rows,
        run_status=run_status,
    )
    recovery_status, summary, blocking_reason, restart_hints = _recovery_guidance(
        run_id=run_id,
        run_status=run_status,
        current_task=current_task,
        next_action=next_action,
        last_execution=last_execution,
        latest_dispatch=latest_dispatch,
        problem=problem,
        ready_count=sum(1 for row in task_rows if row["status"] == "ready"),
    )

    return RecoverySnapshot(
        run_id=run_id,
        run_status=run_status,
        recovery_status=recovery_status,
        can_advance=next_action is not None,
        summary=summary,
        blocking_reason=blocking_reason,
        restart_hints=restart_hints,
        current_task=current_task,
        next_action=next_action,
        last_execution=last_execution,
        latest_dispatch=latest_dispatch,
        latest_decision=latest_decision,
        available_recovery_actions=available_recovery_actions,
        artifact_paths=_recovery_artifact_paths(workspace),
        updated_at=utc_now(),
    )


def _recovery_current_task(
    task_rows: list[sqlite3.Row],
    next_action: NextActionRecord | None,
) -> RecoveryTaskSummary | None:
    if next_action is not None:
        for row in task_rows:
            if row["id"] == next_action.task_id:
                return RecoveryTaskSummary(
                    id=str(row["id"]),
                    kind=str(row["kind"]),
                    title=str(row["title"]),
                    status=str(row["status"]),
                    last_error=row["last_error"],
                )

    for status in ("running", "failed", "blocked", "ready", "pending"):
        for row in task_rows:
            if row["status"] == status:
                return RecoveryTaskSummary(
                    id=str(row["id"]),
                    kind=str(row["kind"]),
                    title=str(row["title"]),
                    status=str(row["status"]),
                    last_error=row["last_error"],
                )
    return None


def _fetch_latest_execution(
    connection: sqlite3.Connection,
    run_id: str,
) -> ExecutionRecord | None:
    row = connection.execute(
        """
        SELECT id, run_id, task_id, action, status, command_argv_json, cwd,
               started_at, finished_at, exit_code, stdout_path, stderr_path
        FROM executions
        WHERE run_id = ?
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return _execution_from_row(row)


def _fetch_latest_dispatch(
    connection: sqlite3.Connection,
    run_id: str,
) -> DispatchRecord | None:
    row = connection.execute(
        """
        SELECT id, run_id, task_id, task_kind, task_title, agent_role, branch_name,
               worktree_name, worktree_path, repo_root, base_commit, prompt_path,
               startup_commands_json, status, status_detail, created_at, updated_at
        FROM dispatches
        WHERE run_id = ?
        ORDER BY updated_at DESC, created_at DESC, id DESC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return _dispatch_from_row(row)


def _read_latest_decision_summary(workspace: Path) -> RecoveryDecisionSummary | None:
    artifact_path = workspace / "artifacts" / "advance-decisions.jsonl"
    if not artifact_path.exists():
        return None

    lines = artifact_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None

    payload = json.loads(lines[-1])
    return RecoveryDecisionSummary(
        created_at=str(payload.get("created_at", "")),
        status=str(payload.get("status", "recommended")),
        action=payload.get("action"),
        detail=payload.get("detail"),
    )


def _recovery_guidance(
    *,
    run_id: str,
    run_status: str,
    current_task: RecoveryTaskSummary | None,
    next_action: NextActionRecord | None,
    last_execution: ExecutionRecord | None,
    latest_dispatch: DispatchRecord | None,
    problem: str | None,
    ready_count: int,
) -> tuple[str, str, str | None, list[str]]:
    if run_status == "completed":
        return (
            "completed",
            "Run completed successfully. No restart is required.",
            None,
            ["No restart required."],
        )

    if run_status == "running":
        return (
            "running",
            "A bounded execution is currently in progress for this run.",
            None,
            [
                "Wait for the current execution to finish before advancing again.",
                f"Inspect GET /api/runs/{run_id}/executions for the latest execution logs.",
            ],
        )

    if next_action is not None and current_task is not None:
        summary = (
            f"Run can advance with '{next_action.action}' on task "
            f"'{current_task.title}'."
        )
        restart_hints = [
            f"Call POST /api/runs/{run_id}/advance to continue.",
            f"Use GET /api/runs/{run_id}/next-action to preview the safe next step.",
        ]
        if (
            latest_dispatch is not None
            and latest_dispatch.status == "prepared"
            and latest_dispatch.task_id == current_task.id
        ):
            summary += " A pinned dispatch is already prepared for this task."
            restart_hints.append(
                f"Inspect {latest_dispatch.prompt_path} or GET /api/runs/{run_id}/dispatches "
                "before preparing another handoff."
            )
        else:
            restart_hints.append(
                f"Call POST /api/runs/{run_id}/dispatches to prepare a pinned worktree handoff."
            )
        return (
            "ready",
            summary,
            None,
            restart_hints,
        )

    blocking_reason = problem
    if current_task is not None and current_task.status == "failed" and current_task.last_error:
        blocking_reason = (
            f"Task '{current_task.title}' failed with last error: {current_task.last_error}"
        )
    elif current_task is not None and current_task.status == "blocked" and current_task.last_error:
        blocking_reason = (
            f"Task '{current_task.title}' is blocked with last error: {current_task.last_error}"
        )

    restart_hints: list[str] = [
        f"Inspect GET /api/runs/{run_id} for task statuses and recent events.",
        f"Review {workspace_hint(last_execution)} before taking a manual recovery action.",
    ]
    if current_task is not None and current_task.status == "failed":
        restart_hints = [
            "Inspect stderr_path and stdout_path from the last execution before retrying.",
            "Repair the workspace inputs or artifacts that caused the failed task.",
            f"Inspect GET /api/runs/{run_id} for the failed task and recent events.",
        ]
    elif current_task is not None and current_task.status == "blocked":
        restart_hints = [
            "Inspect last_error and recent events before changing task state.",
            "Review workspace artifacts and decide on a manual recovery action.",
            f"Check GET /api/runs/{run_id} for the blocked task context.",
        ]
    elif ready_count > 1:
        restart_hints = [
            "Resolve task graph ambiguity so exactly one task is ready.",
            f"Inspect GET /api/runs/{run_id} before retrying advance.",
            "Review the latest recovery snapshot artifact for the current blocker.",
        ]
    elif run_status == "failed":
        restart_hints = [
            "Inspect stderr_path and stdout_path from the last execution before retrying.",
            "Repair the workspace state before attempting manual recovery.",
            f"Inspect GET /api/runs/{run_id} for the failure context.",
        ]

    return (
        "attention_required",
        "Run cannot advance safely until the blocking state is resolved.",
        blocking_reason or "No safe next action is available for the current run state.",
        restart_hints,
    )


def workspace_hint(last_execution: ExecutionRecord | None) -> str:
    if last_execution is None:
        return "the run workspace artifacts"
    return (
        f"{last_execution.stderr_path} and {last_execution.stdout_path}"
    )


def _advance_next_task(
    connection: sqlite3.Connection,
    run_id: str,
    next_position: int,
    created_at: str,
) -> None:
    next_row = connection.execute(
        """
        SELECT id, title
        FROM tasks
        WHERE run_id = ? AND position = ? AND status = 'pending'
        """,
        (run_id, next_position),
    ).fetchone()
    if next_row is None:
        return
    connection.execute(
        """
        UPDATE tasks
        SET status = 'ready'
        WHERE id = ? AND run_id = ?
        """,
        (next_row["id"], run_id),
    )
    _log_event(
        connection,
        run_id,
        "info",
        f"Task '{next_row['title']}' is now ready.",
        created_at,
    )


def _update_run_status(connection: sqlite3.Connection, run_id: str) -> None:
    rows = connection.execute(
        """
        SELECT status
        FROM tasks
        WHERE run_id = ?
        ORDER BY position ASC
        """,
        (run_id,),
    ).fetchall()
    statuses = [row["status"] for row in rows]
    if statuses and all(status == "completed" for status in statuses):
        run_status = "completed"
    elif "failed" in statuses:
        run_status = "failed"
    elif "blocked" in statuses:
        run_status = "blocked"
    elif "running" in statuses:
        run_status = "running"
    else:
        run_status = "ready"
    connection.execute(
        """
        UPDATE runs
        SET status = ?
        WHERE id = ?
        """,
        (run_status, run_id),
    )


def _log_event(
    connection: sqlite3.Connection,
    run_id: str,
    level: str,
    message: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO events (run_id, level, message, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (run_id, level, message, created_at),
    )


def _block_execution_action(
    connection: sqlite3.Connection,
    run_id: str,
    message: str,
    created_at: str,
) -> None:
    _log_event(connection, run_id, "warning", message, created_at)


def _execution_from_row(row: sqlite3.Row) -> ExecutionRecord:
    payload = dict(row)
    payload["command_argv"] = json.loads(payload.pop("command_argv_json"))
    return ExecutionRecord(**payload)


def _dispatch_from_row(row: sqlite3.Row) -> DispatchRecord:
    payload = dict(row)
    base_commit = payload.get("base_commit") or "HEAD"
    startup_commands_json = payload.pop("startup_commands_json", None)
    if startup_commands_json:
        payload["startup_commands"] = json.loads(startup_commands_json)
    else:
        payload["startup_commands"] = [
            f"make worktree NAME={payload['worktree_name']} BASE_REF={base_commit}",
            f"cd .worktrees/{payload['worktree_name']}",
        ]
    payload["repo_root"] = payload.get("repo_root") or ""
    payload["base_commit"] = base_commit
    payload["updated_at"] = payload.get("updated_at") or payload["created_at"]
    return DispatchRecord(**payload)


def _last_error_message(stderr: str) -> str | None:
    stripped = stderr.strip()
    if not stripped:
        return None
    return stripped.splitlines()[-1][:500]


def _available_actions_for_kind(task_kind: str) -> list[str]:
    actions = [
        action
        for action, spec in ACTION_CATALOG.items()
        if task_kind in spec["task_kinds"]
    ]
    return sorted(actions)
