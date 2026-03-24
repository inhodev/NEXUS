from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .config import Settings
from .db import initialize_database
from .models import (
    ActionDescriptor,
    CreateExecutionRequest,
    CreateRunRequest,
    ExecutionRecord,
    NextActionRecord,
    RunDetail,
    RunSummary,
    SystemSummary,
)
from .service import (
    AGENT_ROLES,
    advance_run,
    create_execution,
    create_run,
    get_execution,
    get_run,
    get_system_summary,
    list_action_descriptors,
    list_executions,
    list_runs,
    recommend_next_action,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialize_database(app_settings)
        yield

    app = FastAPI(
        title="NEXUS Control Plane",
        version="0.1.0",
        description="Local-first native control plane for the first real NEXUS vertical slice.",
        lifespan=lifespan,
    )
    app.state.settings = app_settings

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "NEXUS",
            "mode": "local-first",
            "slice": "bounded-planner-and-execution-loop",
        }

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/agents")
    def agents() -> dict[str, list[dict[str, str]]]:
        return {"items": AGENT_ROLES}

    @app.get("/api/actions")
    def actions() -> dict[str, list[ActionDescriptor]]:
        return {"items": list_action_descriptors()}

    @app.get("/api/system/summary", response_model=SystemSummary)
    def system_summary() -> SystemSummary:
        return get_system_summary(app_settings)

    @app.get("/api/runs", response_model=list[RunSummary])
    def runs() -> list[RunSummary]:
        return list_runs(app_settings)

    @app.post("/api/runs", response_model=RunDetail, status_code=201)
    def create_run_endpoint(request: CreateRunRequest) -> RunDetail:
        return create_run(app_settings, request)

    @app.post("/api/requests", response_model=RunDetail, status_code=201)
    def create_request_endpoint(request: CreateRunRequest) -> RunDetail:
        return create_run(app_settings, request)

    @app.get("/api/runs/{run_id}", response_model=RunDetail)
    def run_detail(run_id: str) -> RunDetail:
        try:
            return get_run(app_settings, run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error

    @app.get("/api/runs/{run_id}/next-action", response_model=NextActionRecord)
    def next_action_endpoint(run_id: str) -> NextActionRecord:
        try:
            return recommend_next_action(app_settings, run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/runs/{run_id}/advance", response_model=ExecutionRecord)
    def advance_run_endpoint(run_id: str) -> ExecutionRecord:
        try:
            return advance_run(app_settings, run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/runs/{run_id}/executions", response_model=ExecutionRecord, status_code=201)
    def create_execution_endpoint(
        run_id: str,
        request: CreateExecutionRequest,
    ) -> ExecutionRecord:
        try:
            return create_execution(app_settings, run_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or task not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/runs/{run_id}/executions")
    def list_executions_endpoint(run_id: str) -> dict[str, list[ExecutionRecord]]:
        try:
            return {"items": list_executions(app_settings, run_id)}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error

    @app.get("/api/runs/{run_id}/executions/{execution_id}", response_model=ExecutionRecord)
    def get_execution_endpoint(run_id: str, execution_id: str) -> ExecutionRecord:
        try:
            return get_execution(app_settings, run_id, execution_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or execution not found") from error

    return app


app = create_app()
