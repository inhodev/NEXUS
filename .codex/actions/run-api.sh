#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"
PORT="${NEXUS_API_PORT:-8000}"
VENV_BIN="$ROOT_DIR/.venv/bin"
RELOAD_FLAG=()

if [[ "${NEXUS_API_RELOAD:-0}" == "1" ]]; then
  RELOAD_FLAG=(--reload)
fi

cd "$ROOT_DIR"
"$VENV_BIN/uvicorn" core.nexus_core.app:app "${RELOAD_FLAG[@]}" --host 127.0.0.1 --port "$PORT"
