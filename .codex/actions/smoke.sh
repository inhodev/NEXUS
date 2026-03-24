#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"
PORT="${NEXUS_API_PORT:-8000}"
BASE_URL="${NEXUS_API_BASE_URL:-http://127.0.0.1:$PORT}"
VENV_BIN="$ROOT_DIR/.venv/bin"

cd "$ROOT_DIR"
curl -sf "$BASE_URL/healthz" >/dev/null
run_payload="$(curl -sf -X POST "$BASE_URL/api/runs" \
  -H 'content-type: application/json' \
  -d '{"intent":"Smoke test the NEXUS local-first control plane"}')"
run_id="$(printf '%s' "$run_payload" | "$VENV_BIN/python" -c 'import json, sys; print(json.load(sys.stdin)["id"])')"

printf '%s' "$run_payload" | grep -q '"id"'

for _ in $(seq 1 10); do
  summary_payload="$(curl -sf "$BASE_URL/api/system/summary")"
  latest_run_id="$(printf '%s' "$summary_payload" | "$VENV_BIN/python" -c 'import json, sys; print(json.load(sys.stdin).get("latest_run_id") or "")')"
  if [[ "$latest_run_id" == "$run_id" ]]; then
    printf 'Smoke check passed for %s\n' "$BASE_URL"
    exit 0
  fi
  sleep 0.2
done

printf 'Smoke check failed for %s: latest_run_id did not converge to %s\n' "$BASE_URL" "$run_id" >&2
exit 1
