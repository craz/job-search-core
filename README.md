# Job Search Core

Core domain and public API for a local job-search system. This repository owns
normalized business entities and, starting with the first domain slice, the only
PostgreSQL schema. Sibling services integrate through versioned HTTP or JSON CLI
contracts and never access its database directly.

## Current status

The platform scaffold is implemented: application factory, health endpoints,
JSON component-info CLI, quality gates, executable Gherkin, CI and Docker build.
Domain entities and PostgreSQL are the next increment and are not implemented yet.

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
```

The Docker build exports a hash-locked runtime requirements file from `uv.lock`;
the image needs only the standard Python base and does not depend on a second
package-manager image registry.

## Contracts

- `GET /health/live` — process liveness without dependency checks.
- `GET /health/ready` — readiness; PostgreSQL check will be added with persistence.
- `job-search-core info` — one versioned JSON envelope on stdout.

See [the platform feature spec](docs/specs/core-platform.md) and executable
[Gherkin scenario](tests/features/core_platform.feature).

## Architecture boundaries

- Core will be the sole owner of PostgreSQL and migrations.
- Consumers use public contracts, not Python imports or shared volumes.
- Runtime secrets belong in environment variables; `.env` files are ignored.
- Tests and examples use synthetic data.

## License

MIT. See [LICENSE](LICENSE).
