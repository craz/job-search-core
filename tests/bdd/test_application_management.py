"""pytest-bdd bindings for the first Core Application user story."""

import httpx
from pytest_bdd import scenarios, then, when
from tests.support import ApiClient, application_payload, create_fixture_vacancy

scenarios("../features/application_management.feature")


@when(
    "клиент создаёт вакансию и дважды фиксирует один отклик",
    target_fixture="application_flow",
)
def create_same_application_twice() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
    """Create a Vacancy, replay one Application and fetch its collection."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client, key="bdd-application-vacancy")
    payload = application_payload(vacancy["id"])
    headers = {"Idempotency-Key": "bdd-application"}
    first = client.post("/api/v1/applications", json=payload, headers=headers)
    replay = client.post("/api/v1/applications", json=payload, headers=headers)
    return first, replay, client.get("/api/v1/applications")


@then("Core сохраняет ровно один отклик для этой вакансии")
def one_application_is_stored(
    application_flow: tuple[httpx.Response, httpx.Response, httpx.Response],
) -> None:
    """Require create/replay semantics and one linked persisted Application."""
    first, replay, listing = application_flow
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["vacancy"]["id"] == first.json()["vacancy"]["id"]


@when(
    "клиент фиксирует отклик на неизвестную вакансию",
    target_fixture="missing_vacancy_response",
)
def create_for_missing_vacancy() -> httpx.Response:
    """Submit normalized input referencing no Core Vacancy."""
    client = ApiClient()
    return client.post(
        "/api/v1/applications",
        json=application_payload("00000000-0000-0000-0000-000000000000"),
        headers={"Idempotency-Key": "bdd-missing-vacancy"},
    )


@then("Core отвечает ошибкой vacancy_not_found")
def response_is_missing_vacancy(missing_vacancy_response: httpx.Response) -> None:
    """Return the stable missing-parent code rather than an integrity error."""
    assert missing_vacancy_response.status_code == 404
    assert missing_vacancy_response.json()["code"] == "vacancy_not_found"
