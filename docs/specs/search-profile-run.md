# SearchProfile / SearchRun / SearchRunItem (R2.2.1)

## User Story

```text
Как оператор / следующий HH slice,
Я хочу сохранять SearchProfile и запускать SearchRun с provenance items,
Чтобы позже выполнять HH vacancy acquisition поверх устойчивого Core contract.
```

## Implemented

- mutable `SearchProfile` with **semantic criteria only** (no page_size/max_pages/order);
- `SearchRun` with immutable `criteria_snapshot` + `execution_snapshot`
  (`order`, `max_pages`; optional `page_size` — omitted for browser transport);
- **`acquisition_kind`** (R2.2.5): `profile_search` | `resume_suitable`;
  - `profile_search` → `search_profile_id` **required**, criteria from SearchProfile;
  - `resume_suitable` → `search_profile_id` **NULL**, `criteria_snapshot={}`,
    resume provenance in `candidate_context_snapshot`
    (`hh_resume_external_id`, `hh_resume_title`, optional version ids);
- optional **`source_total`**: HH-reported suitable total (distinct from
  `found_count` = processed SearchRunItems in this bounded run);
- lifecycle `running → success|partial|failed` with `finished_at` only when terminal;
- `SearchRunItem` provenance: unique `(search_run_id, source_external_id)`;
- non-error outcomes require `vacancy_id`; `error` may omit `vacancy_id`;
- finalize recomputes aggregate counters from items;
- HTTP `/api/v1/search-profiles` and `/api/v1/search-runs` (+ items/finalize).
- Migration head: **`20260827_12`**.

## Uniqueness / terminal immutability

`uq_search_run_items_run_external` on `(search_run_id, source_external_id)`.
No mutation API for existing SearchRunItem outcomes. After finalize, item
writes and repeated finalize are rejected (`SearchRunNotRunningError` → HTTP 409
`search_run_not_running`).

## Non-scope

HH search transport, Web UX, Scoring.
