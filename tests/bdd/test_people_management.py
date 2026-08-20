"""pytest-bdd bindings for confirmed People management."""

import httpx
from pytest_bdd import scenarios, then, when
from tests.support import ApiClient, create_fixture_vacancy, person_payload, vacancy_payload

scenarios("../features/people_management.feature")


@when(
    "клиент создаёт вакансию и дважды добавляет подтверждённый контакт",
    target_fixture="person_flow",
)
def create_person_twice() -> tuple[httpx.Response, httpx.Response, httpx.Response, httpx.Response]:
    """Create one confirmed Person twice, list and update it."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client, key="bdd-person-vacancy")
    payload = person_payload(vacancy["company"]["id"], vacancy["id"])
    headers = {"Idempotency-Key": "bdd-person"}
    first = client.post("/api/v1/people", json=payload, headers=headers)
    replay = client.post("/api/v1/people", json=payload, headers=headers)
    listing = client.get("/api/v1/people")
    updated = client.patch(f"/api/v1/people/{first.json()['id']}", json={"status": "researching"})
    return first, replay, listing, updated


@then("Core хранит один контакт и позволяет изменить его статус")
def one_person_is_stateful(
    person_flow: tuple[httpx.Response, httpx.Response, httpx.Response, httpx.Response],
) -> None:
    """Require idempotency, one row and a controlled local status."""
    first, replay, listing, updated = person_flow
    assert (first.status_code, replay.status_code) == (201, 200)
    assert listing.json()["total"] == 1
    assert updated.json()["status"] == "researching"


@when("клиент связывает контакт с чужой вакансией", target_fixture="mismatch_response")
def create_cross_company_person() -> httpx.Response:
    """Reference Company A with a Vacancy owned by Company B."""
    client = ApiClient()
    first = create_fixture_vacancy(client, key="bdd-person-first")
    second_payload = vacancy_payload(title="Second Company Vacancy")
    second_payload["company_name"] = "Second Labs"
    second_payload["company_external_id"] = "company-second"
    second_payload["external_id"] = "vacancy-second"
    second = client.post(
        "/api/v1/vacancies",
        json=second_payload,
        headers={"Idempotency-Key": "bdd-person-second"},
    ).json()
    return client.post(
        "/api/v1/people",
        json=person_payload(first["company"]["id"], second["id"]),
        headers={"Idempotency-Key": "bdd-person-mismatch"},
    )


@then("Core отвечает ошибкой person_company_mismatch")
def mismatch_is_stable(mismatch_response: httpx.Response) -> None:
    """Reject cross-company linkage with a stable machine code."""
    assert mismatch_response.status_code == 409
    assert mismatch_response.json()["code"] == "person_company_mismatch"
