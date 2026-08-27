# Changelog

All notable changes to this project will be documented here. The format follows
Keep a Changelog and versions follow Semantic Versioning.

## Unreleased

### Added

- R2.2.5 temporal: `first_seen_at`, `last_seen_at`, nullable `source_published_at`
  on Vacancy; migration `20260828_13` with approximate backfill from `created_at`.
- R2.2.5: SearchRun `acquisition_kind` (`profile_search` | `resume_suitable`),
  nullable `search_profile_id`, optional `source_total` (HH total ≠ processed
  `found_count`); migration `20260827_12`.
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
