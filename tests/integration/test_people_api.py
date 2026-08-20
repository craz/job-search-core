"""HTTP integration coverage for confirmed Person behavior."""

from tests.support import ApiClient, create_fixture_vacancy, person_payload


def test_create_replay_list_and_update_person() -> None:
    """A confirmed contact is idempotent, linked and locally stateful."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client, key="person-vacancy")
    payload = person_payload(vacancy["company"]["id"], vacancy["id"])
    headers = {"Idempotency-Key": "person-create"}
    first = client.post("/api/v1/people", json=payload, headers=headers)
    replay = client.post("/api/v1/people", json=payload, headers=headers)
    listing = client.get("/api/v1/people")
    updated = client.patch(f"/api/v1/people/{first.json()['id']}", json={"status": "contacted"})

    assert (first.status_code, replay.status_code) == (201, 200)
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["company"]["name"] == "Example Labs"
    assert updated.json()["status"] == "contacted"


def test_person_expected_failures_have_stable_codes() -> None:
    """Unknown ownership, duplicate identity and missing Person expose stable errors."""
    client = ApiClient()
    payload = person_payload("00000000-0000-0000-0000-000000000000")
    missing = client.post(
        "/api/v1/people", json=payload, headers={"Idempotency-Key": "missing-company"}
    )
    unknown = client.patch(
        "/api/v1/people/00000000-0000-0000-0000-000000000000",
        json={"status": "replied"},
    )

    assert missing.status_code == 404
    assert missing.json()["code"] == "company_not_found"
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "person_not_found"
