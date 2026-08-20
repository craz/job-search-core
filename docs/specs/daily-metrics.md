# Daily Metrics

## User Story

Как пользователь системы поиска работы, я хочу сохранять дневной снимок
активности и получать историю по датам, чтобы видеть фактический темп воронки.

## Contract

- one `DailyMetric` exists per ISO calendar date;
- optional non-negative counters are `views_total`, `views_new`, `applications`,
  `replies`, `invitations` and `rejections`;
- `notes` carries bounded context without replacing normalized counters;
- `PUT /api/v1/metrics/{date}` applies explicitly supplied fields and requires
  `Idempotency-Key`;
- replaying the same request key does not reapply an old partial update after a
  newer write; reusing it for different input returns `idempotency_conflict`;
- `GET /api/v1/metrics/{date}` and bounded `GET /api/v1/metrics` expose snapshots;
- JSON CLI `metric set|show|list` mirrors the resource workflow.

## Boundaries

This slice does not infer counts from Applications, read HH, calculate conversion
rates or render charts. Those consumers must use the versioned Core contract.
