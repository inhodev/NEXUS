#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def request_json(url: str, payload: dict[str, str] | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except json.JSONDecodeError:
            body = {"detail": error.reason}
        return error.code, body


def truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Opt-in smoke check for the real NEXUS dispatch claim path."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--real-claim",
        action="store_true",
        help="Actually exercise the live dispatch claim endpoint.",
    )
    parser.add_argument(
        "--intent",
        default="Claim smoke test the NEXUS dispatch lifecycle",
        help="Intent to use when creating the disposable smoke run.",
    )
    args = parser.parse_args()

    enabled = args.real_claim or truthy(os.environ.get("NEXUS_REAL_CLAIM_SMOKE"))
    if not enabled:
        print(
            "Claim smoke skipped. Re-run with --real-claim or NEXUS_REAL_CLAIM_SMOKE=1."
        )
        return 0

    try:
        status, run = request_json(f"{args.base_url}/api/requests", {"intent": args.intent})
        assert status == 201

        status, dispatch = request_json(f"{args.base_url}/api/runs/{run['id']}/dispatches", {})
        assert status == 201
        assert dispatch["status"] == "prepared"
        assert len(dispatch["base_commit"]) == 40

        status, claimed = request_json(
            f"{args.base_url}/api/runs/{run['id']}/dispatches/{dispatch['id']}/claim"
        )
        assert status == 200
        assert claimed["status"] == "claimed"
        assert claimed["claimed_at"] is not None
        assert Path(claimed["worktree_path"]).exists()
        assert Path(claimed["claim_stdout_path"]).exists()
        assert Path(claimed["claim_stderr_path"]).exists()

        status, replay = request_json(
            f"{args.base_url}/api/runs/{run['id']}/dispatches/{dispatch['id']}/claim"
        )
        assert status == 200
        assert replay["id"] == claimed["id"]

        status, next_action = request_json(f"{args.base_url}/api/runs/{run['id']}/next-action")
        assert status == 409
        assert "claimed" in next_action["detail"] or "claim" in next_action["detail"]

        status, recovery = request_json(f"{args.base_url}/api/runs/{run['id']}/recovery")
        assert status == 200
        assert recovery["latest_dispatch"]["status"] == "claimed"
        assert recovery["recovery_status"] == "running"
        assert recovery["can_advance"] is False
        assert recovery["latest_dispatch"]["claim_stdout_path"] == claimed["claim_stdout_path"]
    except (AssertionError, KeyError, urllib.error.URLError) as error:
        print(f"Claim smoke failed: {error}", file=sys.stderr)
        return 1

    print(f"Claim smoke passed for run {run['id']} and dispatch {claimed['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
