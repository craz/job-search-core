"""HTTP integration coverage for normalized Assessments and v1 provenance."""

from tests.support import (
    ApiClient,
    assessment_payload,
    assessment_v1_payload,
    create_fixture_vacancy,
)


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


def test_v1_assessment_exposes_provenance_on_read() -> None:
    """Canonical v1 writes round-trip identity fields through the public API."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = assessment_v1_payload(vacancy["id"])
    headers = {"Idempotency-Key": "assessment-v1-api"}
    created = client.post("/api/v1/assessments", json=payload, headers=headers)
    listing = client.get(f"/api/v1/assessments?vacancy_id={vacancy['id']}")
    assert created.status_code == 201
    body = listing.json()["items"][0]
    assert body["schema_version"] == 1
    assert body["scoring_identity_hash"] == payload["scoring_identity_hash"]
    assert body["candidate_context_hash"] == payload["candidate_context_hash"]
    assert body["detail"]["strengths"] == ["python"]
    assert body["reason"] == body["detail"]["reason"]
    assert body["action"] == body["detail"]["action"]


def test_v1_identity_reuse_returns_existing_assessment() -> None:
    """Duplicate exact identity reuses the stored Assessment over HTTP."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = assessment_v1_payload(vacancy["id"])
    first = client.post(
        "/api/v1/assessments",
        json=payload,
        headers={"Idempotency-Key": "identity-http-a"},
    )
    second_payload = {**payload, "external_id": "assessment-v1-dup"}
    second = client.post(
        "/api/v1/assessments",
        json=second_payload,
        headers={"Idempotency-Key": "identity-http-b"},
    )
    listing = client.get(f"/api/v1/assessments?vacancy_id={vacancy['id']}")
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert listing.json()["total"] == 1
