.PHONY: dev dev-down migrate test lint typecheck evals golden fmt seed stress serve

COMPOSE = docker compose -f infra/docker/docker-compose.yml
CORE = services/core

dev: ## bring up Postgres+pgvector, NATS, MinIO, IdP and run migrations
	$(COMPOSE) up -d
	$(MAKE) migrate

dev-down:
	$(COMPOSE) down

migrate: ## apply migrations as the `migrator` role
	cd $(CORE) && uv run alembic upgrade head

test: ## unit + integration tests (needs a migrated database, see migrate)
	cd $(CORE) && uv run pytest -q

serve: ## run the REST API (needs a migrated database)
	cd $(CORE) && uv run uvicorn app.main:app --reload --port 8000

seed: ## populate the demo tenant (produce/herbs wholesaler) -- see app/seed.py
	cd $(CORE) && uv run --extra dev python -m app.seed

stress: ## fire concurrent load at a running API; see scripts/stress_test.py
	cd $(CORE) && uv run --extra dev python scripts/stress_test.py

lint: ## ruff + mypy (this is what CI's "Static" stage runs)
	uv run ruff check $(CORE)
	uv run ruff format --check $(CORE)
	uv run mypy $(CORE)/app --config-file pyproject.toml

fmt:
	uv run ruff format $(CORE)
	uv run ruff check --fix $(CORE)

evals: ## MCP tool-selection evals (phase 2+; no-op until services/mcp-gateway exists)
	@echo "no evals yet -- gateway lands in phase 2, see docs/ROADMAP.md"

golden: ## document/render golden tests (phase 3+; no-op until services/renderer exists)
	@echo "no golden tests yet -- renderer lands in phase 3, see docs/ROADMAP.md"
