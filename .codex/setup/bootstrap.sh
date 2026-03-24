#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"
mkdir -p .nexus/logs .nexus/state .nexus/workspaces

if ! uv sync --extra dev >".nexus/logs/uv-sync.log" 2>&1; then
  echo "warning: uv sync did not complete; see .nexus/logs/uv-sync.log" >&2
fi

mkdir -p .nexus/state .nexus/workspaces

echo "Bootstrap complete at $ROOT_DIR"
