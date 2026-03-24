from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def request_json(url: str, payload: dict[str, str] | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check the NEXUS local-first API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    try:
        status, health = request_json(f"{args.base_url}/healthz")
        assert status == 200 and health["status"] == "ok"

        status, embassy_health = request_json(f"{args.base_url}/embassy/healthz")
        assert status == 200 and embassy_health["status"] == "ok"

        status, agents = request_json(f"{args.base_url}/api/agents")
        assert status == 200 and len(agents["items"]) >= 4

        status, run = request_json(
            f"{args.base_url}/api/requests",
            {"intent": "Smoke test the NEXUS local-first control plane"},
        )
        assert status == 201

        status, dispatch = request_json(f"{args.base_url}/api/runs/{run['id']}/dispatches", {})
        assert status == 201
        assert dispatch["task_kind"] == "intake"
        assert dispatch["agent_role"] == "planner"
        assert len(dispatch["base_commit"]) == 40

        status, recovery = request_json(f"{args.base_url}/api/runs/{run['id']}/recovery")
        assert status == 200
        assert recovery["run_status"] == "ready"
        assert recovery["can_advance"] is True
        assert recovery["latest_dispatch"]["id"] == dispatch["id"]
        assert recovery["latest_dispatch"]["status"] == "prepared"

        status, memory_hits = request_json(
            f"{args.base_url}/api/runs/{run['id']}/memory/search?q=smoke&limit=3"
        )
        assert status == 200
        assert len(memory_hits) >= 1

        status, next_action = request_json(f"{args.base_url}/api/runs/{run['id']}/next-action")
        assert status == 200
        assert next_action["task_id"] == run["tasks"][0]["id"]
        assert next_action["action"] == "inspect-workspace"

        status, execution = request_json(f"{args.base_url}/api/runs/{run['id']}/advance", {})
        assert status == 200
        assert execution["status"] == "completed"
        assert execution["action"] == "inspect-workspace"

        status, refreshed_run = request_json(f"{args.base_url}/api/runs/{run['id']}")
        assert status == 200
        assert refreshed_run["tasks"][0]["status"] == "completed"
        assert refreshed_run["tasks"][1]["status"] == "ready"

        status, refreshed_recovery = request_json(f"{args.base_url}/api/runs/{run['id']}/recovery")
        assert status == 200
        assert refreshed_recovery["recovery_status"] == "ready"
        assert refreshed_recovery["next_action"]["action"] == "read-intent"
        assert refreshed_recovery["latest_dispatch"]["status"] == "invalidated"

        for _ in range(4):
            status, execution = request_json(f"{args.base_url}/api/runs/{run['id']}/advance", {})
            assert status == 200
            assert execution["status"] == "completed"

        status, blocked_advance = request_json(f"{args.base_url}/api/runs/{run['id']}/advance", {})
        assert status == 409
        assert blocked_advance["detail"] == "No safe next action"

        status, summary = request_json(f"{args.base_url}/api/system/summary")
        assert status == 200
        assert summary["latest_run_id"] == run["id"]
    except (AssertionError, KeyError, urllib.error.URLError) as error:
        print(f"Smoke check failed: {error}", file=sys.stderr)
        return 1

    print(f"Smoke check passed for run {run['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
