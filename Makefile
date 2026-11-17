.DEFAULT_GOAL := help
BACKEND := cd backend &&

.PHONY: help install lint format typecheck test check

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install backend dependencies and git hooks
	$(BACKEND) uv sync
	$(BACKEND) uv run pre-commit install --config ../.pre-commit-config.yaml

lint: ## Ruff lint + format check + architecture contracts
	$(BACKEND) uv run ruff check .
	$(BACKEND) uv run ruff format --check .
	$(BACKEND) uv run lint-imports

format: ## Auto-fix lint issues and format
	$(BACKEND) uv run ruff check --fix .
	$(BACKEND) uv run ruff format .

typecheck: ## mypy (strict)
	$(BACKEND) uv run mypy

test: ## Unit + integration tests (no network)
	$(BACKEND) uv run pytest

check: lint typecheck test ## Everything CI runs
