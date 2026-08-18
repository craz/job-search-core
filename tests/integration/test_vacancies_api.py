"""HTTP integration coverage for transactional Vacancy behavior."""

from tests.support import ApiClient, vacancy_payload


def test_create_replay_and_list_vacancy() -> None:
    """An identical idempotent retry returns one persisted vacancy."""
    client = ApiClient()
    first = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "fixture-create-100"},
    )
    replay = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "fixture-create-100"},
    )
    listing = client.get("/api/v1/vacancies")

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["id"] == replay.json()["id"]
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["company"]["name"] == "Example Labs"


def test_idempotency_key_reuse_with_different_payload_conflicts() -> None:
    """One key cannot silently alias two materially different vacancy requests."""
    client = ApiClient()
    first = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "fixture-conflict"},
    )
    conflict = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(title="Different role"),
        headers={"Idempotency-Key": "fixture-conflict"},
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    assert conflict.json()["trace_id"]


def test_source_identity_cannot_be_created_under_a_second_key() -> None:
    """Source uniqueness returns a stable conflict instead of a database failure."""
    client = ApiClient()
    first = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "fixture-source-first"},
    )
    duplicate = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "fixture-source-second"},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "vacancy_exists"


def test_update_vacancy_status_and_report_missing_identifier() -> None:
    """A consumer can move a vacancy through the funnel without database access."""
    client = ApiClient()
    created = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "fixture-status-update"},
    ).json()

    updated = client.patch(f"/api/v1/vacancies/{created['id']}", json={"status": "shortlisted"})
    missing = client.patch(
        "/api/v1/vacancies/00000000-0000-0000-0000-000000000000",
        json={"status": "rejected"},
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "shortlisted"
    assert missing.status_code == 404
    assert missing.json()["code"] == "vacancy_not_found"
