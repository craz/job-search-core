# Vacancy management

## User Story

```text
Как пользователь системы поиска работы,
Я хочу добавлять и просматривать вакансии,
Чтобы управлять своей воронкой поиска.
```

## Implemented

- normalized `Company` and `Vacancy` tables owned by Core;
- PostgreSQL 17 runtime and Alembic migration `20260817_01`;
- source identity uniqueness on `(source, external_id)`;
- mandatory `Idempotency-Key` with safe replay and conflict detection;
- `POST/GET /api/v1/vacancies` and matching versioned JSON CLI commands;
- stable expected-error bodies with `code`, `message`, and `trace_id`;
- executable unit, integration, OpenAPI contract and Gherkin coverage.

The create request carries normalized company identity together with the vacancy.
Core reuses a company with the same source identity. An identical retry under one
idempotency key returns the existing vacancy; changed input under that key returns
`409 idempotency_conflict` and does not overwrite data.

## Non-scope

- updates and status transitions;
- pagination and search;
- applications and remaining Core entities;
- imports from HH or other providers;
- authentication and public internet exposure;
- migration of the archived SQLite database.
