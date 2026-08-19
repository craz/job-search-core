# Application management

## User Story

```text
Как пользователь системы поиска работы,
Я хочу фиксировать и просматривать отклики на сохранённые вакансии,
Чтобы видеть фактическое движение по воронке и следующие действия.
```

## Contract

- an Application belongs to one existing Vacancy;
- external identity is unique by `(source, external_id)`;
- `Idempotency-Key` safely replays an identical create request;
- `applied_at` is an aware UTC timestamp;
- result values are controlled: `reply`, `interview`, `rejected`, `offer`;
- create/list are available through `/api/v1/applications` and JSON CLI;
- unknown vacancies and identity conflicts use stable error codes.

This slice records normalized facts only. Sending an HH response, reading browser
profiles, incrementing Daily Metrics and editing an Application are separate work.
