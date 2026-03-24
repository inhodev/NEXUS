#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${0:A}")/../.." && pwd)"

cd "$ROOT_DIR"

for cmd in git zsh; do
  command -v "$cmd" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "$cmd" >&2
    exit 1
  }
done

printf 'git: available\n'
printf 'zsh: available\n'

if command -v uv >/dev/null 2>&1; then
  printf 'uv: available\n'
else
  printf 'uv: missing\n'
fi

if command -v pnpm >/dev/null 2>&1; then
  printf 'pnpm: available\n'
else
  printf 'pnpm: missing\n'
fi

if git check-ignore -q .worktrees; then
  printf '.worktrees: ignored\n'
else
  printf '.worktrees: not ignored\n'
fi
