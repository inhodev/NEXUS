.DEFAULT_GOAL := help

NAME ?=

.PHONY: help setup run test smoke doctor worktree

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make setup           Prepare the native local environment' \
		'  make run             Start the local-first NEXUS control plane' \
		'  make test            Run lint and tests for the current slice' \
		'  make smoke           Start the API temporarily and smoke-check it' \
		'  make doctor          Report local prerequisites' \
		'  make worktree NAME=x Bootstrap .worktrees/x for Codex threads'

setup:
	@zsh ./.codex/actions/setup.sh

run:
	@zsh ./.codex/actions/run-api.sh

test:
	@zsh ./.codex/actions/test.sh

smoke:
	@zsh ./.codex/actions/smoke.sh

doctor:
	@zsh ./.codex/actions/doctor.sh

worktree:
	@test -n "$(NAME)" || (printf '%s\n' 'error: NAME is required, for example: make worktree NAME=agent-core' >&2; exit 1)
	@zsh ./.codex/setup/create-worktree.sh "$(NAME)"
