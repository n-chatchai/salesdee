.DEFAULT_GOAL := help
UV := uv run

.PHONY: help install run worker shell migrate makemigrations test cov lint fmt typecheck check superuser

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## uv sync (install deps)
	uv sync

run: ## Run dev server
	$(UV) python manage.py runserver

worker: ## Run the background task worker (django.tasks DatabaseBackend)
	$(UV) python manage.py db_worker

shell: ## Django shell
	$(UV) python manage.py shell

migrate: ## Apply migrations
	$(UV) python manage.py migrate

makemigrations: ## Create migrations
	$(UV) python manage.py makemigrations

superuser: ## Create a Django superuser
	$(UV) python manage.py createsuperuser

seed: ## Seed demo data into the 'wandeedee' tenant (use --force to re-run)
	$(UV) python manage.py seed_demo --tenant wandeedee

test: ## Run tests
	$(UV) pytest

cov: ## Run tests with coverage
	$(UV) pytest --cov=apps --cov-report=term-missing

lint: ## Lint + format check
	$(UV) ruff check .
	$(UV) ruff format --check .

fmt: ## Auto-fix lint + format
	$(UV) ruff check --fix .
	$(UV) ruff format .

typecheck: ## Run mypy
	$(UV) mypy .

check: lint typecheck test ## Run all checks (do this before calling a task done)
