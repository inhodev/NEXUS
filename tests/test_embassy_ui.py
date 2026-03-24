from __future__ import annotations

from pathlib import Path

from nexus_core.ui import build_embassy_router, get_embassy_html


def test_embassy_html_includes_required_panels() -> None:
    html = get_embassy_html()

    assert "<title>NEXUS Embassy</title>" in html
    assert 'data-api-base="/api"' in html
    assert 'id="runList"' in html
    assert 'id="recovery"' in html
    assert 'id="dispatches"' in html
    assert 'id="runSelect"' in html
    assert "fetchJson(`/runs/${state.runId}`)" in html


def test_embassy_router_exports_page_and_health_endpoint() -> None:
    router = build_embassy_router(api_base="/api")
    paths = {route.path for route in router.routes}

    assert "/embassy" in paths
    assert "/embassy/healthz" in paths


def test_embassy_html_file_is_checked_in() -> None:
    html_path = Path(__file__).resolve().parents[1] / "core" / "nexus_core" / "ui" / "embassy.html"

    assert html_path.exists()
    assert html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
