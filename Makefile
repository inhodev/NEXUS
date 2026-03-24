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
	@bash ./.codex/actions/setup.sh

run:
	@bash ./.codex/actions/run-api.sh

test:
	@bash ./.codex/actions/test.sh

smoke:
	@bash ./.codex/actions/smoke.sh

doctor:
	@bash ./.codex/actions/doctor.sh

worktree:
	@test -n "$(NAME)" || (printf '%s\n' 'error: NAME is required, for example: make worktree NAME=agent-core' >&2; exit 1)
	@bash ./.codex/setup/create-worktree.sh "$(NAME)"
