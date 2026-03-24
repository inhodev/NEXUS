#!/usr/bin/env zsh
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/nexus.sh <setup|run|test|smoke|doctor|worktree|help> [args]
EOF
}

ROOT_DIR="$(cd "$(dirname "${0:A}")/.." && pwd)"
ACTION="${1:-help}"
shift || true

case "$ACTION" in
  setup)
    exec zsh "$ROOT_DIR/.codex/actions/setup.sh" "$@"
    ;;
  run)
    exec zsh "$ROOT_DIR/.codex/actions/run-api.sh" "$@"
    ;;
  test)
    exec zsh "$ROOT_DIR/.codex/actions/test.sh" "$@"
    ;;
  smoke)
    exec zsh "$ROOT_DIR/.codex/actions/smoke.sh" "$@"
    ;;
  doctor)
    exec zsh "$ROOT_DIR/.codex/actions/doctor.sh" "$@"
    ;;
  worktree)
    exec zsh "$ROOT_DIR/.codex/setup/create-worktree.sh" "$@"
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
