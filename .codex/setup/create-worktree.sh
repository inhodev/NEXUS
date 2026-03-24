#!/usr/bin/env zsh
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <branch-name> [base-ref]" >&2
  exit 1
fi

BRANCH_NAME="$1"
BASE_REF="${2:-}"
ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"
WORKTREE_DIR="$ROOT_DIR/.worktrees/$BRANCH_NAME"
GIT_BRANCH="codex/$BRANCH_NAME"

cd "$ROOT_DIR"

if ! git check-ignore -q .worktrees; then
  echo ".worktrees is not ignored. Fix .gitignore before creating worktrees." >&2
  exit 1
fi

if [[ -n "$BASE_REF" ]]; then
  git worktree add "$WORKTREE_DIR" -b "$GIT_BRANCH" "$BASE_REF"
else
  git worktree add "$WORKTREE_DIR" -b "$GIT_BRANCH"
fi
zsh "$WORKTREE_DIR/.codex/setup/bootstrap.sh"

echo "Worktree ready at $WORKTREE_DIR ($GIT_BRANCH)"
