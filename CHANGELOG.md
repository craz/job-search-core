# Changelog

All notable changes to this project will be documented here. The format follows
Keep a Changelog and versions follow Semantic Versioning.

## [Unreleased]

### Added

- Reproducible Python, direnv, CI and Docker development scaffold.
- FastAPI liveness/readiness contracts and versioned JSON info CLI.
- Unit, integration, contract and executable BDD test layers.
- PostgreSQL Company/Vacancy schema and first Alembic migration.
- Idempotent Vacancy create/list contracts through `/api/v1` and JSON CLI.
- Controlled Vacancy status updates through `PATCH /api/v1/vacancies/{vacancy_id}`.
- Application migration, idempotent create/list API and equivalent JSON CLI.
- Daily Metric migration, replay-safe partial snapshots, dated/list API and JSON CLI.
- Confirmed Person migration, idempotent create/list/status API and matching JSON CLI.
- Hypothesis migration, replay-safe create/list and immutable close-result API/JSON CLI.
- Normalized Assessment migration and replay-safe create/list API/JSON CLI.
- Database-aware readiness and an independent PostgreSQL 17 Compose stack.
