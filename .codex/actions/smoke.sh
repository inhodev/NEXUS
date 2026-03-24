#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="${NEXUS_API_PORT:-8000}"
RUNTIME_ROOT="${NEXUS_RUNTIME_DIR:-$ROOT_DIR/.nexus}"
VENV_BIN="$ROOT_DIR/.venv/bin"

cd "$ROOT_DIR"
mkdir -p "$RUNTIME_ROOT/logs"

"$VENV_BIN/uvicorn" nexus_core.app:app --host 127.0.0.1 --port "$PORT" >"$RUNTIME_ROOT/logs/smoke-api.log" 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 20); do
  if curl -s "http://127.0.0.1:$PORT/healthz" >/dev/null; then
    break
  fi
  sleep 0.5
done

"$VENV_BIN/python" scripts/smoke_api.py --base-url "http://127.0.0.1:$PORT" "$@"
