"""pytest-bdd bindings for normalized Assessment management."""

import httpx
from pytest_bdd import scenarios, then, when
from tests.support import ApiClient, assessment_payload, create_fixture_vacancy

scenarios("../features/assessment_management.feature")


@when("клиент создаёт вакансию и дважды записывает нормализованную оценку", target_fixture="flow")
def create_twice() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
    """Create and replay one normalized result through public HTTP."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = assessment_payload(vacancy["id"])
    headers = {"Idempotency-Key": "bdd-assessment"}
    return (
        client.post("/api/v1/assessments", json=payload, headers=headers),
        client.post("/api/v1/assessments", json=payload, headers=headers),
        client.get("/api/v1/assessments"),
    )


@then("Core хранит один объяснимый Assessment")
def one_result(flow: tuple[httpx.Response, httpx.Response, httpx.Response]) -> None:
    """Require replay semantics and normalized explanation fields."""
    first, replay, listing = flow
    assert (first.status_code, replay.status_code) == (201, 200)
    assert listing.json()["total"] == 1 and first.json()["reason"]
