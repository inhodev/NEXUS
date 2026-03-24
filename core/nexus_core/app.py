from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .config import Settings
from .db import initialize_database
from .models import (
    ActionDescriptor,
    CreateExecutionRequest,
    CreateRunRequest,
    DispatchRecord,
    DispatchResultRequest,
    ExecutionRecord,
    MemorySearchHitRecord,
    NextActionRecord,
    RecoveryActionRequest,
    RecoveryActionResult,
    RecoverySnapshot,
    RunDetail,
    RunSummary,
    SystemSummary,
)
from .service import (
    AGENT_ROLES,
    advance_run,
    block_dispatch,
    claim_dispatch,
    complete_dispatch,
    create_dispatch,
    create_execution,
    create_run,
    fail_dispatch,
    get_execution,
    get_recovery_snapshot,
    get_run,
    get_system_summary,
    heartbeat_dispatch,
    list_action_descriptors,
    list_dispatches,
    list_executions,
    list_runs,
    recommend_next_action,
    recover_run,
    search_run_memory,
)
from .ui import build_embassy_router


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
    app.include_router(build_embassy_router(api_base="/api"))

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

    @app.get("/api/runs/{run_id}/recovery", response_model=RecoverySnapshot)
    def recovery_endpoint(run_id: str) -> RecoverySnapshot:
        try:
            return get_recovery_snapshot(app_settings, run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error

    @app.get("/api/runs/{run_id}/dispatches", response_model=list[DispatchRecord])
    def dispatches_endpoint(run_id: str) -> list[DispatchRecord]:
        try:
            return list_dispatches(app_settings, run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error

    @app.post("/api/runs/{run_id}/dispatches", response_model=DispatchRecord, status_code=201)
    def create_dispatch_endpoint(run_id: str) -> DispatchRecord:
        try:
            return create_dispatch(app_settings, run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/runs/{run_id}/dispatches/{dispatch_id}/claim", response_model=DispatchRecord)
    def claim_dispatch_endpoint(run_id: str, dispatch_id: str) -> DispatchRecord:
        try:
            return claim_dispatch(app_settings, run_id, dispatch_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or dispatch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/runs/{run_id}/dispatches/{dispatch_id}/heartbeat",
        response_model=DispatchRecord,
    )
    def heartbeat_dispatch_endpoint(run_id: str, dispatch_id: str) -> DispatchRecord:
        try:
            return heartbeat_dispatch(app_settings, run_id, dispatch_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or dispatch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/runs/{run_id}/dispatches/{dispatch_id}/complete",
        response_model=DispatchRecord,
    )
    def complete_dispatch_endpoint(
        run_id: str,
        dispatch_id: str,
        request: DispatchResultRequest,
    ) -> DispatchRecord:
        try:
            return complete_dispatch(app_settings, run_id, dispatch_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or dispatch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/runs/{run_id}/dispatches/{dispatch_id}/fail",
        response_model=DispatchRecord,
    )
    def fail_dispatch_endpoint(
        run_id: str,
        dispatch_id: str,
        request: DispatchResultRequest,
    ) -> DispatchRecord:
        try:
            return fail_dispatch(app_settings, run_id, dispatch_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or dispatch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/runs/{run_id}/dispatches/{dispatch_id}/block",
        response_model=DispatchRecord,
    )
    def block_dispatch_endpoint(
        run_id: str,
        dispatch_id: str,
        request: DispatchResultRequest,
    ) -> DispatchRecord:
        try:
            return block_dispatch(app_settings, run_id, dispatch_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or dispatch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/runs/{run_id}/recover", response_model=RecoveryActionResult)
    def recover_endpoint(run_id: str, request: RecoveryActionRequest) -> RecoveryActionResult:
        try:
            return recover_run(app_settings, run_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run or task not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

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

    @app.get("/api/runs/{run_id}/memory/search", response_model=list[MemorySearchHitRecord])
    def search_run_memory_endpoint(
        run_id: str,
        q: str,
        limit: int = 10,
        include_executions: bool = True,
    ) -> list[MemorySearchHitRecord]:
        try:
            return search_run_memory(
                app_settings,
                run_id,
                q,
                limit=limit,
                include_executions=include_executions,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error

    return app


app = create_app()
