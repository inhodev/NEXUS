#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/.." && pwd)"
exec zsh "$ROOT_DIR/.codex/actions/setup.sh" "$@"
