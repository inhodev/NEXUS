#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: .codex/bootstrap-worktree.sh [--dry-run] <name>

Creates an isolated Codex worktree under .worktrees/<name> and runs setup.
EOF
}

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=1
  shift
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

name="$1"
repo_root="$(git rev-parse --show-toplevel)"
worktree_root="$repo_root/.worktrees"
worktree_path="$worktree_root/$name"
branch_name="codex/$name"

if ! git -C "$repo_root" check-ignore -q .worktrees; then
  echo "error: .worktrees must be ignored before creating local worktrees" >&2
  exit 1
fi

mkdir -p "$worktree_root"

if [[ $dry_run -eq 1 ]]; then
  cat <<EOF
Would create worktree:
  path: $worktree_path
  branch: $branch_name
Would run setup:
  $worktree_path/.codex/setup-env.sh
EOF
  exit 0
fi

if [[ -e "$worktree_path" ]]; then
  echo "error: worktree path already exists: $worktree_path" >&2
  exit 1
fi

git -C "$repo_root" worktree add "$worktree_path" -b "$branch_name"
bash "$worktree_path/.codex/setup-env.sh"

cat <<EOF
Worktree ready at $worktree_path
Branch: $branch_name
EOF
