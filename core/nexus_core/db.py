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
"""


def initialize_database(settings: Settings) -> None:
    settings.ensure_directories()
    with sqlite3.connect(settings.database_path) as connection:
        connection.executescript(SCHEMA)
        _ensure_column(connection, "tasks", "started_at", "TEXT")
        _ensure_column(connection, "tasks", "finished_at", "TEXT")
        _ensure_column(connection, "tasks", "last_error", "TEXT")


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
        connection.commit()
    finally:
        connection.close()
