"""HTTP integration coverage for Hypothesis behavior."""

from tests.support import ApiClient


def payload() -> dict[str, object]:
    """Return one synthetic public experiment request."""
    return {
        "source": "fixture",
        "external_id": "hypothesis-api-100",
        "title": "Targeted applications improve replies",
        "description": "Synthetic API experiment.",
        "test_size": 12,
        "metric": "reply_rate",
    }


def test_create_replay_filter_and_close_hypothesis() -> None:
    """HTTP supports one replay-safe experiment and explicit observed result."""
    client = ApiClient()
    headers = {"Idempotency-Key": "hypothesis-api-key"}
    first = client.post("/api/v1/hypotheses", json=payload(), headers=headers)
    replay = client.post("/api/v1/hypotheses", json=payload(), headers=headers)
    active = client.get("/api/v1/hypotheses?status=active")
    closed = client.post(
        f"/api/v1/hypotheses/{first.json()['id']}/close",
        json={"result": "Reply rate increased"},
        headers={},
    )

    assert (first.status_code, replay.status_code) == (201, 200)
    assert active.json()["total"] == 1
    assert closed.json()["status"] == "done"
    assert closed.json()["result"] == "Reply rate increased"


def test_closed_result_and_missing_identity_have_stable_errors() -> None:
    """HTTP rejects result replacement and unknown close targets predictably."""
    client = ApiClient()
    created = client.post(
        "/api/v1/hypotheses",
        json=payload(),
        headers={"Idempotency-Key": "close-errors"},
    ).json()
    path = f"/api/v1/hypotheses/{created['id']}/close"
    client.post(path, json={"result": "First result"}, headers={})
    conflict = client.post(path, json={"result": "Replacement"}, headers={})
    missing = client.post(
        "/api/v1/hypotheses/00000000-0000-0000-0000-000000000000/close",
        json={"result": "Unknown"},
        headers={},
    )

    assert conflict.status_code == 409
    assert conflict.json()["code"] == "hypothesis_already_closed"
    assert missing.status_code == 404
    assert missing.json()["code"] == "hypothesis_not_found"
