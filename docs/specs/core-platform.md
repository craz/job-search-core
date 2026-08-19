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
- PostgreSQL-backed readiness.

## Non-scope

Company/Vacancy and Application behavior are specified separately by executable
feature files. Metrics, people, hypotheses and assessments remain outside this
platform increment.
