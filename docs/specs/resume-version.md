# ResumeVersion immutable snapshots (R2.1.1 / R2.1.4)

## User Story

```text
Как система Job Search,
Я хочу хранить неизменяемые локальные версии содержания резюме,
Чтобы позже scoring мог использовать конкретный snapshot без чтения HH.
```

## Implemented

- Table `resume_versions` (immutable content history)
- Canonical allowlist normalization + SHA-256 `content_hash`
- Unchanged content (same hash as **latest** for that resume scope) → no new row
- Changed content → new immutable row; previous rows kept and readable
- HTTP:
  - `POST /api/v1/resume-versions` (fixture / HH manual sync ingest)
  - `GET /api/v1/resume-versions/{id}` (full snapshot body)
  - `GET /api/v1/candidate-context` includes `resume_content` **metadata only**
- Current local copy = active HH link + latest ResumeVersion for
  `(profile_version_id, source, external_resume_id)` (**no** pointer table)
- History scope is per resume id: dedup never crosses different
  `external_resume_id` values
- `resume_content.content_state`:
  - `synced` — active link + at least one ResumeVersion for that id
  - `not_synced` — active link, no ResumeVersion yet
  - `none` — link cleared / inactive (no current copy; history retained)
- Switch back to a previously synced resume uses latest local copy for that
  id without requiring a new HH fetch
- `ProfileVersion` remains `r1-default`

## Non-scope

Web UI (R2.1.5), auto-sync, Scoring, vacancy work, PDF/raw HTML,
SearchProfile redesign, active-pointer table.
