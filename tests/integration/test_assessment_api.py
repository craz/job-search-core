"""HTTP integration coverage for normalized Assessments."""

from tests.support import ApiClient, assessment_payload, create_fixture_vacancy


def test_create_replay_and_filter_assessment() -> None:
    """HTTP persists one auditable result linked to an existing Vacancy."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = assessment_payload(vacancy["id"])
    headers = {"Idempotency-Key": "assessment-api"}
    first = client.post("/api/v1/assessments", json=payload, headers=headers)
    replay = client.post("/api/v1/assessments", json=payload, headers=headers)
    listing = client.get(f"/api/v1/assessments?vacancy_id={vacancy['id']}")
    assert (first.status_code, replay.status_code) == (201, 200)
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["vacancy"]["id"] == vacancy["id"]


def test_unknown_vacancy_has_stable_error() -> None:
    """A normalized result cannot reference an unknown Vacancy."""
    client = ApiClient()
    response = client.post(
        "/api/v1/assessments",
        json=assessment_payload("00000000-0000-0000-0000-000000000000"),
        headers={"Idempotency-Key": "missing-vacancy"},
    )
    assert response.status_code == 404 and response.json()["code"] == "vacancy_not_found"
