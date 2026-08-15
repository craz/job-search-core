# Core platform scaffold

## User Story

```text
Как разработчик системы поиска работы,
Я хочу получить машиночитаемый статус Core,
Чтобы автоматически проверять готовность компонента к интеграции.
```

## Implemented

- ASGI application factory;
- liveness and readiness endpoints;
- versioned JSON `info` CLI;
- executable Gherkin acceptance scenario;
- reproducible local, CI and Docker commands.

## Non-scope

PostgreSQL, Alembic and domain resources enter the first vertical Core slice.
Until then readiness intentionally has no external dependency to inspect.

