.DEFAULT_GOAL := help

NAME ?=

.PHONY: help setup run test smoke doctor worktree

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make setup           Prepare the native local environment' \
		'  make run             Start the current native service entrypoint' \
		'  make test            Validate tooling scripts' \
		'  make smoke           Run no-Docker bootstrap smoke checks' \
		'  make doctor          Report local prerequisites' \
		'  make worktree NAME=x Bootstrap .worktrees/x for Codex threads'

setup:
	@bash ./scripts/nexus.sh setup

run:
	@bash ./scripts/nexus.sh run

test:
	@bash ./scripts/nexus.sh test

smoke:
	@bash ./scripts/nexus.sh smoke

doctor:
	@bash ./scripts/nexus.sh doctor

worktree:
	@test -n "$(NAME)" || (printf '%s\n' 'error: NAME is required, for example: make worktree NAME=agent-core' >&2; exit 1)
	@bash ./scripts/nexus.sh worktree "$(NAME)"
