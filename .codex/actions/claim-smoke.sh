#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"
PORT="${NEXUS_API_PORT:-8000}"
BASE_URL="${NEXUS_API_BASE_URL:-http://127.0.0.1:$PORT}"
VENV_BIN="$ROOT_DIR/.venv/bin"
STARTED_SERVER=0

cd "$ROOT_DIR"

if ! curl -sf "$BASE_URL/healthz" >/dev/null; then
  mkdir -p "$ROOT_DIR/.nexus/logs"
  "$VENV_BIN/uvicorn" core.nexus_core.app:app --host 127.0.0.1 --port "$PORT" >"$ROOT_DIR/.nexus/logs/claim-smoke-api.log" 2>&1 &
  SERVER_PID=$!
  STARTED_SERVER=1
  trap '[[ $STARTED_SERVER -eq 1 ]] && kill "$SERVER_PID" >/dev/null 2>&1 || true' EXIT

  for _ in $(seq 1 20); do
    if curl -sf "$BASE_URL/healthz" >/dev/null; then
      break
    fi
    sleep 0.5
  done
fi

"$VENV_BIN/python" scripts/claim_smoke.py --base-url "$BASE_URL" --real-claim "$@"
