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
    CreateExecutionRequest,
    CreateRunRequest,
    EventRecord,
    ExecutionRecord,
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
    {"role": "tester", "focus": "validate behavior and surface uncertainty"},
    {"role": "reviewer", "focus": "check quality, safety, and recoverability"},
]

ACTION_MAP: dict[str, list[str]] = {
    "inspect-workspace": ["pwd"],
    "list-root": ["ls", "-la"],
    "list-artifacts": ["ls", "-la", "artifacts"],
    "read-intent": ["cat", "intent.md"],
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
        tasks=[TaskRecord(**dict(row)) for row in task_rows],
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


def create_execution(
    settings: Settings,
    run_id: str,
    request: CreateExecutionRequest,
) -> ExecutionRecord:
    start_time = utc_now()
    command = ACTION_MAP.get(request.action)
    with connect(settings) as connection:
        run_row = _fetch_run_row(connection, run_id)
        workspace = Path(run_row["workspace_path"])
        task_row = _fetch_task_row(connection, run_id, request.task_id) if request.task_id else None

        if command is None:
            _log_event(
                connection,
                run_id,
                "warning",
                f"Blocked execution action '{request.action}'.",
                start_time,
            )
            connection.commit()
            raise ValueError(f"Action '{request.action}' is not allowed")

        if task_row is not None and task_row["status"] not in {"ready", "running"}:
            raise ValueError("Task must be ready or running before execution")

        execution_id = f"exec_{uuid4().hex[:12]}"
        cwd = str(workspace)
        stdout_path = workspace / "executions" / execution_id / "stdout.txt"
        stderr_path = workspace / "executions" / execution_id / "stderr.txt"
        stdout_path.parent.mkdir(parents=True, exist_ok=True)

        if task_row is not None:
            connection.execute(
                """
                UPDATE tasks
                SET status = 'running',
                    started_at = COALESCE(started_at, ?),
                    last_error = NULL
                WHERE id = ? AND run_id = ?
                """,
                (start_time, task_row["id"], run_id),
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

    completed = _run_mapped_action(workspace, command)
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
                json.dumps(command),
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

        if request.task_id is not None:
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
        _update_run_status(connection, run_id)

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
    task_id: str | None,
) -> sqlite3.Row:
    if task_id is None:
        raise KeyError("task_id")
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


def _execution_from_row(row: sqlite3.Row) -> ExecutionRecord:
    payload = dict(row)
    payload["command_argv"] = json.loads(payload.pop("command_argv_json"))
    return ExecutionRecord(**payload)


def _last_error_message(stderr: str) -> str | None:
    stripped = stderr.strip()
    if not stripped:
        return None
    return stripped.splitlines()[-1][:500]
