#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="${NEXUS_API_PORT:-8000}"
VENV_BIN="$ROOT_DIR/.venv/bin"

cd "$ROOT_DIR"
"$VENV_BIN/uvicorn" nexus_core.app:app --reload --host 127.0.0.1 --port "$PORT"
