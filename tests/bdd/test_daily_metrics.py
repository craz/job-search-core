"""pytest-bdd bindings for the Daily Metrics user story."""

import httpx
from pytest_bdd import scenarios, then, when
from tests.support import ApiClient

scenarios("../features/daily_metrics.feature")


@when(
    "клиент записывает метрики дня и повторяет тот же запрос",
    target_fixture="replayed_metric",
)
def write_and_replay_metric() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
    """Write one snapshot twice and fetch the bounded collection."""
    client = ApiClient()
    payload = {"views_new": 4, "applications": 2}
    headers = {"Idempotency-Key": "bdd-metric"}
    first = client.put("/api/v1/metrics/2026-08-20", json=payload, headers=headers)
    replay = client.put("/api/v1/metrics/2026-08-20", json=payload, headers=headers)
    return first, replay, client.get("/api/v1/metrics")


@then("Core хранит один снимок с ожидаемыми счётчиками")
def one_metric_is_stored(
    replayed_metric: tuple[httpx.Response, httpx.Response, httpx.Response],
) -> None:
    """Require create/replay status and one persisted dated snapshot."""
    first, replay, listing = replayed_metric
    assert (first.status_code, replay.status_code) == (201, 200)
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["applications"] == 2


@when(
    "клиент обновляет снимок новым ключом и повторяет старый запрос",
    target_fixture="delayed_replay_metric",
)
def update_then_replay_old_metric() -> httpx.Response:
    """Apply a newer value before retrying the original partial write."""
    client = ApiClient()
    path = "/api/v1/metrics/2026-08-20"
    client.put(path, json={"applications": 1}, headers={"Idempotency-Key": "old"})
    client.put(path, json={"applications": 3}, headers={"Idempotency-Key": "new"})
    client.put(path, json={"applications": 1}, headers={"Idempotency-Key": "old"})
    return client.get(path)


@then("Core сохраняет более новое значение")
def newer_value_survives(delayed_replay_metric: httpx.Response) -> None:
    """A delayed retry cannot overwrite the later snapshot value."""
    assert delayed_replay_metric.json()["applications"] == 3
