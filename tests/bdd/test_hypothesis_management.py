"""pytest-bdd bindings for measurable Hypothesis management."""

import httpx
from pytest_bdd import scenarios, then, when
from tests.support import ApiClient

scenarios("../features/hypothesis_management.feature")


def payload() -> dict[str, object]:
    """Build one synthetic measurable search experiment."""
    return {
        "source": "fixture",
        "external_id": "bdd-hypothesis",
        "title": "Focused applications improve replies",
        "test_size": 8,
        "metric": "reply_rate",
    }


@when(
    "клиент дважды создаёт измеримую гипотезу и закрывает её",
    target_fixture="hypothesis_flow",
)
def create_twice_and_close() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
    """Create, replay and close one experiment through public HTTP."""
    client = ApiClient()
    headers = {"Idempotency-Key": "bdd-hypothesis-key"}
    first = client.post("/api/v1/hypotheses", json=payload(), headers=headers)
    replay = client.post("/api/v1/hypotheses", json=payload(), headers=headers)
    closed = client.post(
        f"/api/v1/hypotheses/{first.json()['id']}/close",
        json={"result": "Observed a higher reply rate"},
        headers={},
    )
    return first, replay, closed


@then("Core хранит один эксперимент с результатом")
def one_closed_experiment(
    hypothesis_flow: tuple[httpx.Response, httpx.Response, httpx.Response],
) -> None:
    """Require replay semantics and an explicit immutable result."""
    first, replay, closed = hypothesis_flow
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    assert closed.json()["status"] == "done"


@when(
    "клиент повторно закрывает гипотезу другим результатом",
    target_fixture="close_conflict",
)
def close_with_replacement() -> httpx.Response:
    """Attempt to overwrite the first observed result."""
    client = ApiClient()
    created = client.post(
        "/api/v1/hypotheses",
        json=payload(),
        headers={"Idempotency-Key": "bdd-close-key"},
    ).json()
    path = f"/api/v1/hypotheses/{created['id']}/close"
    client.post(path, json={"result": "First"}, headers={})
    return client.post(path, json={"result": "Second"}, headers={})


@then("Core отвечает ошибкой hypothesis_already_closed")
def immutable_result_error(close_conflict: httpx.Response) -> None:
    """Expose a stable conflict instead of replacing evidence."""
    assert close_conflict.status_code == 409
    assert close_conflict.json()["code"] == "hypothesis_already_closed"
