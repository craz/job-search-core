# SearchProfile / SearchRun / SearchRunItem (R2.2.1)

## User Story

```text
Как оператор / следующий HH slice,
Я хочу сохранять SearchProfile и запускать SearchRun с provenance items,
Чтобы позже выполнять HH vacancy acquisition поверх устойчивого Core contract.
```

## Implemented

- mutable `SearchProfile` with **semantic criteria only** (no page_size/max_pages/order);
- `SearchRun` with immutable `criteria_snapshot` + `execution_snapshot`;
- lifecycle `running → success|partial|failed` with `finished_at` only when terminal;
- `SearchRunItem` provenance: unique `(search_run_id, source_external_id)`;
- non-error outcomes require `vacancy_id`; `error` may omit `vacancy_id`;
- finalize recomputes aggregate counters from items;
- HTTP `/api/v1/search-profiles` and `/api/v1/search-runs` (+ items/finalize).

## Uniqueness / terminal immutability

`uq_search_run_items_run_external` on `(search_run_id, source_external_id)`.
No mutation API for existing SearchRunItem outcomes. After finalize, item
writes and repeated finalize are rejected (`SearchRunNotRunningError` → HTTP 409
`search_run_not_running`).

## Non-scope

HH search, Vacancy upsert/content_hash, Web UX, Scoring, browser vacancy search.
