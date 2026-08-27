# ResumeVersion immutable snapshots (R2.1.1)

## User Story

```text
Как система Job Search,
Я хочу хранить неизменяемые локальные версии содержания резюме,
Чтобы позже scoring мог использовать конкретный snapshot без чтения HH.
```

## Implemented

- Table `resume_versions` (immutable content history)
- Canonical allowlist normalization + SHA-256 `content_hash`
- Unchanged content → no new row; changed content → new row
- HTTP:
  - `POST /api/v1/resume-versions` (fixture / future HH sync ingest)
  - `GET /api/v1/resume-versions/{id}` (full snapshot body)
  - `GET /api/v1/candidate-context` includes `resume_content` **metadata only**
- Current local copy = active HH link + latest ResumeVersion for that
  `external_resume_id` (no pointer table)
- `ProfileVersion` remains `r1-default`

## Non-scope

HH browser extractor, Web UI, auto-sync, Scoring, vacancy work, PDF/raw HTML,
SearchProfile redesign, active-pointer table.
