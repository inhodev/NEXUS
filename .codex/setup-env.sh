#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"

exec bash "$repo_root/scripts/nexus.sh" setup "$@"
