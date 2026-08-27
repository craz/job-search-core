# Vacancy ingest / content_hash (R2.2.3)

## User Story

```text
Как HH acquisition / следующий SearchRun slice,
Я хочу identity-safe upsert канонической Vacancy с content_hash,
Чтобы повторный ingest давал created|updated|unchanged без потери user state.
```

## Implemented

- `POST /api/v1/vacancies/ingest` (no Idempotency-Key)
- Outcomes: `created` | `updated` | `unchanged`
- Core-owned `content_hash` over source-owned fields only
- Source fields: title, url, description, salary/area/employment/schedule/
  work_format/experience/published texts, archived
- User-owned `Vacancy.status` + relations preserved on update
- Manual `POST /api/v1/vacancies` + Idempotency-Key unchanged
- `idempotency_key` / `request_fingerprint` nullable for ingest rows

## Company note

Stable employer id → Company `(source, external_id)` + name refresh.
Missing employer id → `name:{casefold}` fallback (collision risk documented;
not expanded into fuzzy merge).

## Non-scope

SearchRun/SearchRunItem orchestration, Web CTA, scoring, fuzzy dedupe.
