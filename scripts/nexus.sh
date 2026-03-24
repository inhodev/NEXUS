#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/nexus.sh <setup|run|test|smoke|doctor|worktree|help> [args]
EOF
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-help}"
shift || true

case "$ACTION" in
  setup)
    exec bash "$ROOT_DIR/.codex/actions/setup.sh" "$@"
    ;;
  run)
    exec bash "$ROOT_DIR/.codex/actions/run-api.sh" "$@"
    ;;
  test)
    exec bash "$ROOT_DIR/.codex/actions/test.sh" "$@"
    ;;
  smoke)
    exec bash "$ROOT_DIR/.codex/actions/smoke.sh" "$@"
    ;;
  doctor)
    exec bash "$ROOT_DIR/.codex/actions/doctor.sh" "$@"
    ;;
  worktree)
    exec bash "$ROOT_DIR/.codex/setup/create-worktree.sh" "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    printf 'error: unknown command: %s\n' "$ACTION" >&2
    exit 1
    ;;
esac
