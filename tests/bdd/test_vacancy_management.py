"""pytest-bdd bindings for the first Core Vacancy user story."""

import httpx
from pytest_bdd import scenarios, then, when
from tests.support import ApiClient, vacancy_payload

scenarios("../features/vacancy_management.feature")


@when(
    "клиент дважды создаёт одну вакансию с одинаковым ключом",
    target_fixture="vacancy_flow",
)
def create_same_vacancy_twice() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
    """Create and replay one vacancy before obtaining its collection."""
    client = ApiClient()
    headers = {"Idempotency-Key": "bdd-replay"}
    first = client.post("/api/v1/vacancies", json=vacancy_payload(), headers=headers)
    replay = client.post("/api/v1/vacancies", json=vacancy_payload(), headers=headers)
    return first, replay, client.get("/api/v1/vacancies")


@then("Core сохраняет ровно одну вакансию")
def one_vacancy_is_stored(
    vacancy_flow: tuple[httpx.Response, httpx.Response, httpx.Response],
) -> None:
    """Require create/replay status semantics and one durable row."""
    first, replay, listing = vacancy_flow
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    assert listing.json()["total"] == 1


@then("список вакансий содержит созданную вакансию и компанию")
def listing_contains_vacancy_and_company(
    vacancy_flow: tuple[httpx.Response, httpx.Response, httpx.Response],
) -> None:
    """Expose normalized vacancy and company fields through the public response."""
    item = vacancy_flow[2].json()["items"][0]
    assert item["title"] == "Backend Engineer"
    assert item["company"]["name"] == "Example Labs"


@when(
    "клиент использует один ключ для разных данных вакансии",
    target_fixture="conflict_response",
)
def reuse_key_for_changed_request() -> httpx.Response:
    """Send two materially different requests under one key."""
    client = ApiClient()
    headers = {"Idempotency-Key": "bdd-conflict"}
    client.post("/api/v1/vacancies", json=vacancy_payload(), headers=headers)
    return client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(title="Changed title"),
        headers=headers,
    )


@then("Core отвечает конфликтом идемпотентности")
def response_is_idempotency_conflict(conflict_response: httpx.Response) -> None:
    """Return the stable conflict code rather than overwriting existing data."""
    assert conflict_response.status_code == 409
    assert conflict_response.json()["code"] == "idempotency_conflict"


@when(
    "клиент создаёт вакансию и меняет её статус на shortlisted",
    target_fixture="status_response",
)
def create_and_shortlist_vacancy() -> httpx.Response:
    """Create one vacancy and update it only through versioned HTTP contracts."""
    client = ApiClient()
    vacancy = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "bdd-status"},
    ).json()
    return client.patch(f"/api/v1/vacancies/{vacancy['id']}", json={"status": "shortlisted"})


@then("Core возвращает вакансию со статусом shortlisted")
def vacancy_is_shortlisted(status_response: httpx.Response) -> None:
    """Expose the committed funnel status to consumers."""
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "shortlisted"
