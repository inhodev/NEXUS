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
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check the NEXUS local-first API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    try:
        status, health = request_json(f"{args.base_url}/healthz")
        assert status == 200 and health["status"] == "ok"

        status, agents = request_json(f"{args.base_url}/api/agents")
        assert status == 200 and len(agents["items"]) >= 5

        status, run = request_json(
            f"{args.base_url}/api/requests",
            {"intent": "Smoke test the NEXUS local-first control plane"},
        )
        assert status == 201

        first_task = run["tasks"][0]["id"]
        status, execution = request_json(
            f"{args.base_url}/api/runs/{run['id']}/executions",
            {"task_id": first_task, "action": "inspect-workspace"},
        )
        assert status == 201
        assert execution["status"] == "completed"

        status, refreshed_run = request_json(f"{args.base_url}/api/runs/{run['id']}")
        assert status == 200
        assert refreshed_run["tasks"][0]["status"] == "completed"
        assert refreshed_run["tasks"][1]["status"] == "ready"

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
