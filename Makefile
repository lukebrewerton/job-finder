COMPOSE := docker compose

.PHONY: help up down logs lock migrate migrate-autogen test lint format fetch seed shell

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Build and run the dev stack (hot reload)
	$(COMPOSE) up --build

down: ## Stop the dev stack
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f

lock: ## Regenerate uv.lock from pyproject.toml (run after changing deps)
	uv lock

migrate: ## Apply migrations to head
	$(COMPOSE) run --rm api alembic upgrade head

migrate-autogen: ## Autogenerate a migration: make migrate-autogen m="add jobs table"
	$(COMPOSE) run --rm api alembic revision --autogenerate -m "$(m)"

test: ## Run the test suite
	$(COMPOSE) run --rm api pytest

lint: ## Lint + format-check + type-check (black --check, ruff, mypy)
	$(COMPOSE) run --rm api sh -c "ruff check . && black --check . && mypy app"

format: ## Auto-fix lint issues and format the code
	$(COMPOSE) run --rm api sh -c "ruff check --fix . && black ."

fetch: ## Run one source adapter: make fetch SOURCE=<key> [QUERY="cloud engineer"]
	$(COMPOSE) run --rm api python -m app.cli fetch --source $(SOURCE) $(if $(QUERY),--query "$(QUERY)",)

seed: ## Seed sources and local dev data
	$(COMPOSE) run --rm api python -m app.cli seed

shell: ## Shell into the api container
	$(COMPOSE) run --rm api sh
