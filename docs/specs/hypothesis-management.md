# Hypothesis management

## User Story

Как пользователь системы поиска работы, я хочу формулировать измеримые гипотезы
и фиксировать результат проверки, чтобы улучшать стратегию на основании
экспериментов, а не впечатлений.

## Contract

- a Hypothesis has a source identity, title, optional description, positive test
  size and explicit metric;
- external identity is unique by `(source, external_id)` and create is idempotent;
- lifecycle states are `active` and `done`;
- closing an active hypothesis requires a non-empty observed result;
- the first closing result is immutable; an identical close is a safe replay;
- create/list/close are available through `/api/v1/hypotheses` and JSON CLI;
- Core records experiments only and triggers no external job-search action.
