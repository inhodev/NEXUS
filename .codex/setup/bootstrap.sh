#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"
uv sync --extra dev
mkdir -p .nexus/state .nexus/workspaces

echo "Bootstrap complete at $ROOT_DIR"
