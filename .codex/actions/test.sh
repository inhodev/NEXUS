#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"
VENV_BIN="$ROOT_DIR/.venv/bin"

cd "$ROOT_DIR"
"$VENV_BIN/ruff" check .
"$VENV_BIN/pytest"
