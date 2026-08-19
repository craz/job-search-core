"""HTTP integration coverage for transactional Application behavior."""

from tests.support import ApiClient, application_payload, create_fixture_vacancy


def test_create_replay_and_list_application() -> None:
    """An identical retry persists one Application linked to its Vacancy."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = application_payload(vacancy["id"])
    headers = {"Idempotency-Key": "fixture-application-create"}

    first = client.post("/api/v1/applications", json=payload, headers=headers)
    replay = client.post("/api/v1/applications", json=payload, headers=headers)
    listing = client.get("/api/v1/applications")

    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["vacancy"]["title"] == "Backend Engineer"


def test_application_conflicts_and_unknown_vacancy_have_stable_codes() -> None:
    """Expected Application failures do not leak persistence exceptions."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = application_payload(vacancy["id"])
    client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Idempotency-Key": "fixture-application-first"},
    )
    duplicate = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Idempotency-Key": "fixture-application-second"},
    )
    payload["vacancy_id"] = "00000000-0000-0000-0000-000000000000"
    payload["external_id"] = "application-missing-vacancy"
    missing = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Idempotency-Key": "fixture-application-missing"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "application_exists"
    assert missing.status_code == 404
    assert missing.json()["code"] == "vacancy_not_found"
