# Assessment management

## User Story

Как пользователь системы поиска работы, я хочу хранить объяснимую оценку
вакансии, чтобы быстрее выбирать действие и видеть риски.

## Contract

- an Assessment belongs to an existing Vacancy and records score 0–100, verdict
  `apply/maybe/skip`, reason, optional risk and recommended action;
- model, prompt version and timezone-aware assessment time make results auditable;
- external identity is unique and create is replay-safe under Idempotency-Key;
- Core stores normalized results only; raw model output and prompts remain Scoring-owned;
- create/list with optional Vacancy filter are available through HTTP and JSON CLI.
