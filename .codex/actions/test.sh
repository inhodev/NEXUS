#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_BIN="$ROOT_DIR/.venv/bin"

cd "$ROOT_DIR"
"$VENV_BIN/ruff" check .
"$VENV_BIN/pytest"
