# People management

## User Story

Как пользователь системы поиска работы, я хочу хранить подтверждённые
профессиональные контакты у компаний и вакансий, чтобы управлять referral и
коммуникационным workflow без сырых OSINT-данных.

## Contract

- a Person belongs to one existing Company and may reference a Vacancy of that Company;
- external identity is unique by `(source, external_id)` and create is idempotent;
- roles are `hiring_manager`, `recruiter`, `referral`, `peer`;
- statuses are `new`, `researching`, `contacted`, `replied`, `dropped`;
- create/list/status are available through `/api/v1/people` and JSON CLI;
- confidence, when present, is between zero and one;
- status changes record local workflow only and never send messages.

Raw provider responses, search queries, provenance caches and automatic discovery
remain owned by OSINT. Core accepts only a confirmed normalized result.
