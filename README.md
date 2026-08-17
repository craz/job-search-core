# Job Search Core

Core domain and public API for a local job-search system. This repository owns
normalized business entities and, starting with the first domain slice, the only
PostgreSQL schema. Sibling services integrate through versioned HTTP or JSON CLI
contracts and never access its database directly.

## Current status

The first domain slice is implemented: Core owns PostgreSQL migrations, normalized
Company/Vacancy persistence, database-aware readiness, idempotent `/api/v1`
create/list contracts and equivalent machine-readable CLI operations.

## Quick start

Requirements: Python 3.12, `uv`, GNU Make and optionally Docker/direnv.

```bash
direnv allow       # once; later directory entry activates .venv automatically
make bootstrap
make test
make dev
```

Without direnv, Make and `uv run` use `.venv` automatically; manual `activate` is
not required. API docs are available at <http://127.0.0.1:8000/docs>.

## Commands

```bash
make test          # format, lint, types, unit, integration, contract and BDD
make smoke         # versioned JSON CLI response
make build         # Docker image job-search-core:dev
make dev           # Uvicorn with hot reload
make migrate       # apply Core-owned Alembic migrations
docker compose up --build  # PostgreSQL 17 + migrated Core API
```

Set `CORE_PORT` when port 8000 is occupied, for example
`CORE_PORT=18080 docker compose up --build`.

The Docker build exports a hash-locked runtime requirements file from `uv.lock`;
the image needs only the standard Python base and does not depend on a second
package-manager image registry.

## Contracts

- `GET /health/live` — process liveness without dependency checks.
- `GET /health/ready` — database-backed readiness.
- `POST /api/v1/vacancies` — create with mandatory `Idempotency-Key`.
- `GET /api/v1/vacancies` — list normalized vacancies and companies.
- `job-search-core info` — one versioned JSON envelope on stdout.
- `job-search-core vacancy create|list` — matching JSON CLI workflow.

See [the platform feature spec](docs/specs/core-platform.md) and executable
[Gherkin scenario](tests/features/core_platform.feature).

## Architecture boundaries

- Core is the sole owner of PostgreSQL and Alembic migrations.
- Consumers use public contracts, not Python imports or shared volumes.
- Runtime secrets belong in environment variables; `.env` files are ignored.
- Tests and examples use synthetic data.

## License

MIT. See [LICENSE](LICENSE).
