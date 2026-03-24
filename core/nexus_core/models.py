from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "ready", "running", "failed", "completed"]
TaskStatus = Literal["pending", "ready", "running", "blocked", "failed", "completed"]


class CreateRunRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=10_000)


class TaskRecord(BaseModel):
    id: str
    kind: str
    title: str
    status: TaskStatus
    position: int


class EventRecord(BaseModel):
    id: int
    level: str
    message: str
    created_at: str


class RunSummary(BaseModel):
    id: str
    intent: str
    status: RunStatus
    created_at: str
    workspace_path: str


class RunDetail(RunSummary):
    tasks: list[TaskRecord]
    events: list[EventRecord]


class SystemSummary(BaseModel):
    run_count: int
    latest_run_id: str | None
    workspace_root: str
