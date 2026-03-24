from __future__ import annotations

from importlib import resources

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

_HTML_TEMPLATE_NAME = "embassy.html"
_API_BASE_PLACEHOLDER = "__NEXUS_API_BASE__"


def get_embassy_html(api_base: str = "/api") -> str:
    html = resources.files(__package__).joinpath(_HTML_TEMPLATE_NAME).read_text(encoding="utf-8")
    return html.replace(_API_BASE_PLACEHOLDER, api_base.rstrip("/") or "/")


def build_embassy_router(api_base: str = "/api") -> APIRouter:
    router = APIRouter()

    @router.get("/embassy", response_class=HTMLResponse)
    def embassy_page() -> str:
        return get_embassy_html(api_base=api_base)

    @router.get("/embassy/healthz")
    def embassy_healthz() -> dict[str, str]:
        return {"status": "ok"}

    return router
