"""HTTP integration coverage for confirmed normalized Company websites."""

from tests.support import ApiClient, create_fixture_vacancy


def test_set_company_website_and_report_missing_company() -> None:
    """The idempotent PUT exposes one confirmed URL and stable missing error."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    path = f"/api/v1/companies/{vacancy['company']['id']}/website"
    headers = {"Idempotency-Key": "not-required-by-put-semantics"}
    first = client.put(path, json={"website_url": "https://example.test"}, headers=headers)
    replay = client.put(path, json={"website_url": "https://example.test/"}, headers=headers)
    missing = client.put(
        "/api/v1/companies/00000000-0000-0000-0000-000000000000/website",
        json={"website_url": "https://example.test/"},
        headers=headers,
    )
    assert first.status_code == 200 and replay.status_code == 200
    assert replay.json()["website_url"] == "https://example.test/"
    assert missing.status_code == 404 and missing.json()["code"] == "company_not_found"
