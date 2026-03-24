#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/nexus.sh <setup|run|test|smoke|doctor|worktree|help> [args]

Commands:
  setup   Prepare a local native environment without Docker.
  run     Start the current native service entrypoint, if one exists.
  test    Validate repository tooling scripts.
  smoke   Run lightweight no-Docker bootstrap checks.
  doctor  Report local prerequisites and repo conventions.
  worktree Bootstrap an isolated .worktrees/ branch for Codex threads.
EOF
}

repo_root="$(git rev-parse --show-toplevel)"
action="${1:-help}"
shift || true

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

ensure_git_repo() {
  git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git repository"
}

create_runtime_dirs() {
  runtime_root="${NEXUS_RUNTIME_DIR:-/tmp/nexus}"

  mkdir -p "$repo_root/.worktrees" \
    "$runtime_root/runtime" \
    "$runtime_root/logs" \
    "$runtime_root/tmp"
}

has_file() {
  [[ -f "$repo_root/$1" ]]
}

setup_cmd() {
  dry_run=0
  if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
  fi

  if [[ $# -gt 0 ]]; then
    die "unexpected setup arguments: $*"
  fi

  runtime_root="${NEXUS_RUNTIME_DIR:-/tmp/nexus}"

  if [[ $dry_run -eq 1 ]]; then
    log "Would create local runtime directories:"
    log "  .worktrees/"
    log "  ${NEXUS_RUNTIME_DIR:-/tmp/nexus}/runtime/"
    log "  ${NEXUS_RUNTIME_DIR:-/tmp/nexus}/logs/"
    log "  ${NEXUS_RUNTIME_DIR:-/tmp/nexus}/tmp/"
    if has_file pyproject.toml; then
      log "Would attempt native Python dependency sync with uv."
    fi
    if has_file package.json; then
      log "Would attempt native Node dependency sync with pnpm or npm."
    fi
    return
  fi

  create_runtime_dirs

  if has_file pyproject.toml; then
    command -v uv >/dev/null 2>&1 || die "uv is required when pyproject.toml is present"
    log "Running uv sync for native Python setup."
    if ! (cd "$repo_root" && env \
      UV_CACHE_DIR="$runtime_root/uv-cache" \
      XDG_CACHE_HOME="$runtime_root/cache" \
      uv sync) >"$runtime_root/logs/uv-sync.log" 2>&1; then
      log "warning: uv sync did not complete in this environment; see $runtime_root/logs/uv-sync.log"
    fi
    return
  fi

  if has_file package.json; then
    if command -v pnpm >/dev/null 2>&1; then
      log "Running pnpm install for native Node setup."
      if ! (cd "$repo_root" && pnpm install) >"$runtime_root/logs/pnpm-install.log" 2>&1; then
        log "warning: pnpm install did not complete in this environment; see $runtime_root/logs/pnpm-install.log"
      fi
      return
    fi

    command -v npm >/dev/null 2>&1 || die "npm is required when package.json is present"
    log "Running npm install for native Node setup."
    if ! (cd "$repo_root" && npm install) >"$runtime_root/logs/npm-install.log" 2>&1; then
      log "warning: npm install did not complete in this environment; see $runtime_root/logs/npm-install.log"
    fi
    return
  fi

  log "No pyproject.toml or package.json found."
  log "Created local runtime directories only; the first service can be added later."
}

run_cmd() {
  if has_file pyproject.toml && [[ -f "$repo_root/scripts/run.py" ]]; then
    log "Launching scripts/run.py."
    (cd "$repo_root" && python3 scripts/run.py)
    return
  fi

  if has_file package.json && [[ -f "$repo_root/scripts/run.mjs" ]]; then
    log "Launching scripts/run.mjs."
    (cd "$repo_root" && node scripts/run.mjs)
    return
  fi

  log "No runnable service entrypoint exists yet."
  log "Add the first native NEXUS service, then point scripts/nexus.sh run at it."
}

test_cmd() {
  create_runtime_dirs

  shell_files="$(find "$repo_root" \
    -path "$repo_root/.git" -prune -o \
    -type f \( -name '*.sh' -o -name '*.bash' \) -print)"

  [[ -n "$shell_files" ]] || die "no shell scripts found to validate"

  find "$repo_root" \
    -path "$repo_root/.git" -prune -o \
    -type f \( -name '*.sh' -o -name '*.bash' \) \
    -exec bash -n {} +

  log "Shell script syntax checks passed."
}

smoke_cmd() {
  create_runtime_dirs

  git -C "$repo_root" check-ignore -q .worktrees || die ".worktrees must stay ignored"

  bash "$repo_root/.codex/setup-env.sh" --dry-run
  bash "$repo_root/.codex/bootstrap-worktree.sh" --dry-run smoke-check

  log "Smoke checks passed."
}

doctor_cmd() {
  ensure_git_repo

  for cmd in git bash; do
    command -v "$cmd" >/dev/null 2>&1 || die "missing required command: $cmd"
  done

  log "Required local tools are available."
  if command -v uv >/dev/null 2>&1; then
    log "uv: available"
  else
    log "uv: not installed yet"
  fi

  if command -v pnpm >/dev/null 2>&1; then
    log "pnpm: available"
  else
    log "pnpm: not installed yet"
  fi
}

worktree_cmd() {
  if [[ $# -lt 1 ]]; then
    die "worktree name is required"
  fi

  exec bash "$repo_root/.codex/bootstrap-worktree.sh" "$@"
}

case "$action" in
  setup) setup_cmd "$@" ;;
  run) run_cmd "$@" ;;
  test) test_cmd "$@" ;;
  smoke) smoke_cmd "$@" ;;
  doctor) doctor_cmd "$@" ;;
  worktree) worktree_cmd "$@" ;;
  help|-h|--help) usage ;;
  *)
    usage >&2
    die "unknown command: $action"
    ;;
esac
