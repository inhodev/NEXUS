from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "ready", "running", "blocked", "failed", "completed"]
TaskStatus = Literal["pending", "ready", "running", "blocked", "failed", "completed"]
ExecutionStatus = Literal["running", "completed", "failed", "blocked"]
RecoveryStatus = Literal["ready", "running", "attention_required", "completed"]


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


class RecoveryTaskSummary(BaseModel):
    id: str
    kind: str
    title: str
    status: TaskStatus
    last_error: str | None = None


class RecoveryDecisionSummary(BaseModel):
    created_at: str
    status: str
    action: str | None = None
    detail: str | None = None


class RecoveryArtifactPaths(BaseModel):
    intent: str
    initial_plan: str
    advance_log: str
    recovery_snapshot: str


class RecoverySnapshot(BaseModel):
    run_id: str
    run_status: RunStatus
    recovery_status: RecoveryStatus
    can_advance: bool
    summary: str
    blocking_reason: str | None = None
    restart_hints: list[str] = Field(default_factory=list)
    current_task: RecoveryTaskSummary | None = None
    next_action: NextActionRecord | None = None
    last_execution: ExecutionRecord | None = None
    latest_decision: RecoveryDecisionSummary | None = None
    artifact_paths: RecoveryArtifactPaths
    updated_at: str


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
