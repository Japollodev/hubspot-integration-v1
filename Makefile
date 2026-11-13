.DEFAULT_GOAL := help
SHELL := /bin/bash

BACKEND := backend
FRONTEND := frontend

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install backend + frontend dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm ci

db-up: ## Start the local Postgres container (waits until healthy)
	docker compose up -d --wait db

db-down: ## Stop the local Postgres container (data volume is kept)
	docker compose stop db

migrate: ## Apply database migrations (alembic upgrade head)
	cd $(BACKEND) && uv run alembic upgrade head

dev: ## Run API (:8000) and Vite (:5173) together; Ctrl-C stops both
	@trap 'kill 0' INT TERM; \
	  $(MAKE) dev-api & \
	  $(MAKE) dev-web & \
	  wait

dev-api: ## Run the FastAPI dev server with reload
	cd $(BACKEND) && LOG_JSON=false uv run uvicorn app.main:app --reload --port 8000

dev-web: ## Run the Vite dev server
	cd $(FRONTEND) && npm run dev

lint: ## Lint + format check both apps
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && npm run lint && npm run format:check

format: ## Auto-format both apps
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .
	cd $(FRONTEND) && npm run format

typecheck: ## mypy (strict) + tsc
	cd $(BACKEND) && uv run mypy
	cd $(FRONTEND) && npm run typecheck

test: ## pytest + vitest
	cd $(BACKEND) && uv run pytest
	cd $(FRONTEND) && npm test

check: lint typecheck test ## Everything CI runs

build: ## Build the frontend into frontend/dist (served by FastAPI at /)
	cd $(FRONTEND) && npm run build

serve: build ## Production-like: FastAPI serves the built app on :8000
	cd $(BACKEND) && uv run uvicorn app.main:app --port 8000

docker: ## Build and run the container on :8000
	docker compose up --build

.PHONY: help install db-up db-down migrate dev dev-api dev-web lint format typecheck test check build serve docker
