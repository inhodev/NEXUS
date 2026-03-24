#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"
"$ROOT_DIR/.codex/setup/bootstrap.sh"
