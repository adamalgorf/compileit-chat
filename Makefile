.DEFAULT_GOAL := help
BACKEND := cd backend &&
FRONTEND := cd frontend &&

.PHONY: help install api web ingest index docs eval lint format typecheck test check

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install backend + frontend dependencies and git hooks
	$(BACKEND) uv sync
	$(BACKEND) uv run pre-commit install --config ../.pre-commit-config.yaml
	$(FRONTEND) npm ci

api: ## Run the API with auto-reload on http://localhost:8000
	$(BACKEND) uv run uvicorn compileit_chat.interface.api.main:app --reload --port 8000

web: ## Run the frontend dev server on http://localhost:3000
	$(FRONTEND) npm run dev

ingest: ## Re-crawl compileit.com, update the snapshot, rebuild the index
	$(BACKEND) uv run compileit-chat ingest

index: ## Rebuild the index from the committed snapshot (no crawl)
	$(BACKEND) uv run compileit-chat ingest --no-crawl

docs: ## Regenerate the orchestration graph in docs/architecture.md from code
	$(BACKEND) uv run compileit-chat docs

eval: ## Run the golden-question eval against OpenAI (costs cents) -> docs/eval-report.md
	$(BACKEND) uv run python -m tests.eval.run

lint: ## Backend: ruff + architecture contracts. Frontend: ESLint + Prettier
	$(BACKEND) uv run ruff check .
	$(BACKEND) uv run ruff format --check .
	$(BACKEND) uv run lint-imports
	$(FRONTEND) npm run lint
	$(FRONTEND) npm run format:check

format: ## Auto-fix lint issues and format both apps
	$(BACKEND) uv run ruff check --fix .
	$(BACKEND) uv run ruff format .
	$(FRONTEND) npm run format

typecheck: ## mypy (strict) + tsc
	$(BACKEND) uv run mypy
	$(FRONTEND) npm run typecheck

test: ## Backend unit + integration tests, frontend Vitest (no network)
	$(BACKEND) uv run pytest
	$(FRONTEND) npm test

check: lint typecheck test ## Everything CI runs
