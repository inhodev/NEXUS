#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"

cd "$ROOT_DIR"
mkdir -p .nexus/logs .nexus/state .nexus/workspaces

uv sync --extra dev --no-cache

mkdir -p .nexus/state .nexus/workspaces

echo "Bootstrap complete at $ROOT_DIR"
