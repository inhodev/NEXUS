from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import Settings

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    intent TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    workspace_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    position INTEGER NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    command_argv_json TEXT NOT NULL,
    cwd TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    exit_code INTEGER,
    stdout_path TEXT NOT NULL,
    stderr_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dispatches (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    task_kind TEXT NOT NULL,
    task_title TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    worktree_name TEXT NOT NULL,
    worktree_path TEXT NOT NULL,
    repo_root TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    prompt_path TEXT NOT NULL,
    startup_commands_json TEXT NOT NULL,
    claim_command_argv_json TEXT,
    claim_stdout_path TEXT,
    claim_stderr_path TEXT,
    claimed_at TEXT,
    heartbeat_at TEXT,
    lease_expires_at TEXT,
    result_manifest_path TEXT,
    status TEXT NOT NULL,
    status_detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def initialize_database(settings: Settings) -> None:
    settings.ensure_directories()
    with sqlite3.connect(settings.database_path) as connection:
        connection.executescript(SCHEMA)
        _ensure_column(connection, "tasks", "started_at", "TEXT")
        _ensure_column(connection, "tasks", "finished_at", "TEXT")
        _ensure_column(connection, "tasks", "last_error", "TEXT")
        _ensure_column(connection, "dispatches", "repo_root", "TEXT")
        _ensure_column(connection, "dispatches", "base_commit", "TEXT")
        _ensure_column(connection, "dispatches", "startup_commands_json", "TEXT")
        _ensure_column(connection, "dispatches", "claim_command_argv_json", "TEXT")
        _ensure_column(connection, "dispatches", "claim_stdout_path", "TEXT")
        _ensure_column(connection, "dispatches", "claim_stderr_path", "TEXT")
        _ensure_column(connection, "dispatches", "claimed_at", "TEXT")
        _ensure_column(connection, "dispatches", "heartbeat_at", "TEXT")
        _ensure_column(connection, "dispatches", "lease_expires_at", "TEXT")
        _ensure_column(connection, "dispatches", "result_manifest_path", "TEXT")
        _ensure_column(connection, "dispatches", "status_detail", "TEXT")
        _ensure_column(connection, "dispatches", "updated_at", "TEXT")


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def connect(settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()
