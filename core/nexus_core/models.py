from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "ready", "running", "blocked", "failed", "completed"]
TaskStatus = Literal["pending", "ready", "running", "blocked", "failed", "completed"]
ExecutionStatus = Literal["running", "completed", "failed", "blocked"]


class CreateRunRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=10_000)


class CreateExecutionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=128)
    task_id: str | None = None


class TaskRecord(BaseModel):
    id: str
    kind: str
    title: str
    status: TaskStatus
    position: int
    available_actions: list[str] = Field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    last_error: str | None = None


class EventRecord(BaseModel):
    id: int
    level: str
    message: str
    created_at: str


class ExecutionRecord(BaseModel):
    id: str
    run_id: str
    task_id: str | None
    action: str
    status: ExecutionStatus
    command_argv: list[str]
    cwd: str
    started_at: str
    finished_at: str
    exit_code: int | None
    stdout_path: str
    stderr_path: str


class NextActionRecord(BaseModel):
    run_id: str
    task_id: str
    task_kind: str
    task_title: str
    action: str
    command_argv: list[str]
    available_actions: list[str] = Field(default_factory=list)
    reason: str


class ActionDescriptor(BaseModel):
    action: str
    description: str
    command_argv: list[str]
    task_kinds: list[str]


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
