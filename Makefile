.PHONY: bootstrap dev migrate format format-check lint typecheck unit integration contract bdd test build smoke

UV ?= env -u VIRTUAL_ENV uv
export UV_LINK_MODE := copy

bootstrap:
	./scripts/ensure-venv.sh

dev: bootstrap
	$(UV) run uvicorn job_search_core.app:app --host 0.0.0.0 --port 8000 --reload

migrate: bootstrap
	$(UV) run alembic upgrade head

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

format-check:
	$(UV) run ruff format --check .

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy src

unit:
	$(UV) run pytest -q tests/unit

integration:
	$(UV) run pytest -q tests/integration

contract:
	$(UV) run pytest -q tests/contract

bdd:
	$(UV) run pytest -q tests/bdd

test: format-check lint typecheck unit integration contract bdd

build:
	$(UV) export --quiet --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.runtime.txt
	docker build -t job-search-core:dev .

smoke:
	$(UV) run job-search-core info
