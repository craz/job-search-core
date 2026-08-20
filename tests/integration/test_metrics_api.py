"""HTTP integration coverage for Daily Metric contracts."""

from tests.support import ApiClient


def test_put_replay_get_and_list_daily_metric() -> None:
    """One dated snapshot is replay-safe and visible through both read paths."""
    client = ApiClient()
    payload = {"views_total": 12, "views_new": 3, "applications": 2, "notes": "Synthetic"}
    headers = {"Idempotency-Key": "metric-2026-08-20"}
    first = client.put("/api/v1/metrics/2026-08-20", json=payload, headers=headers)
    replay = client.put("/api/v1/metrics/2026-08-20", json=payload, headers=headers)
    single = client.get("/api/v1/metrics/2026-08-20")
    listing = client.get("/api/v1/metrics?since=2026-08-20&limit=10")

    assert (first.status_code, replay.status_code) == (201, 200)
    assert single.json()["applications"] == 2
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["metric_date"] == "2026-08-20"


def test_metric_errors_have_stable_codes_and_validation() -> None:
    """Missing snapshots, empty writes, conflicts and negative counts are explicit."""
    client = ApiClient()
    path = "/api/v1/metrics/2026-08-20"
    headers = {"Idempotency-Key": "metric-key"}
    assert client.get(path).json()["code"] == "metric_not_found"
    assert client.put(path, json={}, headers=headers).json()["code"] == "empty_metric_update"
    assert client.put(path, json={"replies": -1}, headers=headers).status_code == 422
    assert client.put(path, json={"replies": 1}, headers=headers).status_code == 201
    conflict = client.put(path, json={"replies": 2}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
