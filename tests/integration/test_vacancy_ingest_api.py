"""Integration tests for POST /api/v1/vacancies/ingest (R2.2.3)."""

from __future__ import annotations

from tests.support import ApiClient, create_fixture_vacancy, vacancy_payload


def _ingest_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "company_name": "Okkam",
        "company_external_id": "777",
        "source": "hh",
        "external_id": "136706048",
        "title": "Senior Python Developer",
        "url": "https://hh.ru/vacancy/136706048",
        "description": "Full description for scoring.",
        "area_text": "Москва",
        "experience_text": "3–6 лет",
        "archived": False,
    }
    body.update(overrides)
    return body


def test_ingest_created_unchanged_updated_and_manual_create_compat() -> None:
    client = ApiClient()

    created = client.post("/api/v1/vacancies/ingest", json=_ingest_body(), headers={})
    assert created.status_code == 200
    assert created.json()["outcome"] == "created"
    vacancy_id = created.json()["vacancy"]["id"]
    digest = created.json()["vacancy"]["content_hash"]
    assert digest

    unchanged = client.post("/api/v1/vacancies/ingest", json=_ingest_body(), headers={})
    assert unchanged.status_code == 200
    assert unchanged.json()["outcome"] == "unchanged"
    assert unchanged.json()["vacancy"]["id"] == vacancy_id

    updated = client.post(
        "/api/v1/vacancies/ingest",
        json=_ingest_body(description="Updated full description."),
        headers={},
    )
    assert updated.status_code == 200
    assert updated.json()["outcome"] == "updated"
    assert updated.json()["vacancy"]["id"] == vacancy_id
    assert updated.json()["vacancy"]["content_hash"] != digest

    listed = client.get("/api/v1/vacancies")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    # Manual create path remains intact.
    manual = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "manual-1"},
    )
    assert manual.status_code == 201
    replay = client.post(
        "/api/v1/vacancies",
        json=vacancy_payload(),
        headers={"Idempotency-Key": "manual-1"},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == manual.json()["id"]


def test_ingest_preserves_user_status_and_application_relation() -> None:
    client = ApiClient()
    ingest = client.post("/api/v1/vacancies/ingest", json=_ingest_body(), headers={})
    vacancy_id = ingest.json()["vacancy"]["id"]

    patched = client.patch(f"/api/v1/vacancies/{vacancy_id}", json={"status": "reviewing"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "reviewing"

    application = client.post(
        "/api/v1/applications",
        json={
            "vacancy_id": vacancy_id,
            "source": "fixture",
            "external_id": "app-1",
            "applied_at": "2026-08-27T12:00:00Z",
        },
        headers={"Idempotency-Key": "app-1"},
    )
    assert application.status_code == 201
    application_id = application.json()["id"]

    updated = client.post(
        "/api/v1/vacancies/ingest",
        json=_ingest_body(title="Senior Python Developer / Lead"),
        headers={},
    )
    assert updated.json()["outcome"] == "updated"
    assert updated.json()["vacancy"]["status"] == "reviewing"
    assert updated.json()["vacancy"]["id"] == vacancy_id

    apps = client.get("/api/v1/applications")
    assert apps.status_code == 200
    assert apps.json()["total"] == 1
    assert apps.json()["items"][0]["id"] == application_id
    assert apps.json()["items"][0]["vacancy"]["id"] == vacancy_id


def test_ingest_identity_isolation() -> None:
    client = ApiClient()
    a = client.post("/api/v1/vacancies/ingest", json=_ingest_body(), headers={})
    b = client.post(
        "/api/v1/vacancies/ingest",
        json=_ingest_body(source="other", company_external_id="777-other"),
        headers={},
    )
    c = client.post(
        "/api/v1/vacancies/ingest",
        json=_ingest_body(external_id="999", url="https://hh.ru/vacancy/999"),
        headers={},
    )
    assert a.json()["vacancy"]["id"] != b.json()["vacancy"]["id"]
    assert a.json()["vacancy"]["id"] != c.json()["vacancy"]["id"]
    assert client.get("/api/v1/vacancies").json()["total"] == 3


def test_fixture_vacancy_helper_still_works() -> None:
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    assert vacancy["source"] == "fixture"
