.DEFAULT_GOAL := help

NAME ?=
BASE_REF ?=

.PHONY: help setup run test smoke claim-smoke doctor worktree

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make setup           Prepare the native local environment' \
		'  make run             Start the local-first NEXUS control plane' \
		'  make test            Run lint and tests for the current slice' \
		'  make smoke           Start the API temporarily and smoke-check it' \
		'  make claim-smoke     Opt in to the real dispatch claim smoke path' \
		'  make doctor          Report local prerequisites' \
		'  make worktree NAME=x BASE_REF=<sha> Bootstrap .worktrees/x for Codex threads'

setup:
	@zsh ./.codex/actions/setup.sh

run:
	@zsh ./.codex/actions/run-api.sh

test:
	@zsh ./.codex/actions/test.sh

smoke:
	@zsh ./.codex/actions/smoke.sh

claim-smoke:
	@zsh ./.codex/actions/claim-smoke.sh

doctor:
	@zsh ./.codex/actions/doctor.sh

worktree:
	@test -n "$(NAME)" || (printf '%s\n' 'error: NAME is required, for example: make worktree NAME=agent-core' >&2; exit 1)
	@zsh ./.codex/setup/create-worktree.sh "$(NAME)" "$(BASE_REF)"
