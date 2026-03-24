from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .db import connect
from .models import (
    CreateRunRequest,
    EventRecord,
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


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def create_run(settings: Settings, request: CreateRunRequest) -> RunDetail:
    run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
    created_at = utc_now()
    workspace = settings.workspace_root / run_id
    artifacts_dir = workspace / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

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
            INSERT INTO tasks (id, run_id, kind, title, status, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (task.id, run_id, task.kind, task.title, task.status, task.position)
                for task in tasks
            ],
        )
        connection.executemany(
            """
            INSERT INTO events (run_id, level, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (run_id, "info", "Run created from user intent", created_at),
                (run_id, "info", "Workspace prepared for local-first execution", utc_now()),
                (run_id, "info", "Initial task graph materialized", utc_now()),
            ],
        )

    _write_artifacts(workspace, request.intent, tasks, created_at)
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

        task_rows = connection.execute(
            """
            SELECT id, kind, title, status, position
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


def _write_artifacts(
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
