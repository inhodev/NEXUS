from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "ready", "running", "blocked", "failed", "completed"]
TaskStatus = Literal["pending", "ready", "running", "blocked", "failed", "completed"]
ExecutionStatus = Literal["running", "completed", "failed", "blocked"]
RecoveryStatus = Literal["ready", "running", "attention_required", "completed"]
DispatchStatus = Literal[
    "prepared",
    "claimed",
    "claim_failed",
    "completed",
    "worker_failed",
    "worker_blocked",
    "superseded",
    "invalidated",
]


class CreateRunRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=10_000)


class CreateExecutionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=128)
    task_id: str | None = None


class DispatchResultRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=2_000)
    changed_files: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


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


class RecoveryActionOption(BaseModel):
    action: str
    task_id: str | None = None
    task_title: str | None = None
    task_status: TaskStatus | None = None
    description: str


class RecoveryActionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    task_id: str | None = Field(default=None, min_length=1, max_length=256)


class RecoveryActionResult(BaseModel):
    run_id: str
    action: str
    task_id: str | None = None
    summary: str
    updated_at: str
    recovery: "RecoverySnapshot"


class RecoveryArtifactPaths(BaseModel):
    intent: str
    initial_plan: str
    advance_log: str
    dispatches: str
    recovery_actions: str
    recovery_snapshot: str


class DispatchReportUrls(BaseModel):
    heartbeat: str
    complete: str
    fail: str
    block: str


class DispatchRecord(BaseModel):
    id: str
    run_id: str
    task_id: str
    task_kind: str
    task_title: str
    agent_role: str
    branch_name: str
    worktree_name: str
    worktree_path: str
    repo_root: str
    base_commit: str
    prompt_path: str
    handoff_path: str
    startup_commands: list[str] = Field(default_factory=list)
    heartbeat_interval_seconds: int
    report_urls: DispatchReportUrls
    claim_command_argv: list[str] = Field(default_factory=list)
    claim_stdout_path: str | None = None
    claim_stderr_path: str | None = None
    claimed_at: str | None = None
    heartbeat_at: str | None = None
    lease_expires_at: str | None = None
    result_manifest_path: str | None = None
    status: DispatchStatus
    status_detail: str | None = None
    created_at: str
    updated_at: str


class MemoryEntryRecord(BaseModel):
    id: str
    source_path: str
    kind: str
    title: str
    metadata: dict[str, str] = Field(default_factory=dict)


class MemorySearchHitRecord(BaseModel):
    entry: MemoryEntryRecord
    score: int
    snippet: str
    matched_terms: list[str] = Field(default_factory=list)


class DispatchResultTemplate(BaseModel):
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class DispatchHandoffRecord(BaseModel):
    dispatch: DispatchRecord
    result_template: DispatchResultTemplate
    operator_hints: list[str] = Field(default_factory=list)


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
    latest_dispatch: DispatchRecord | None = None
    latest_decision: RecoveryDecisionSummary | None = None
    available_recovery_actions: list[RecoveryActionOption] = Field(default_factory=list)
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
