"""BDD bindings for confirmed Company website updates."""

from typing import Any

from pytest_bdd import scenarios, then, when
from tests.support import ApiClient, create_fixture_vacancy

scenarios("../features/company_website.feature")


@when("клиент создаёт вакансию и подтверждает сайт её компании", target_fixture="company")
def confirm_website() -> dict[str, Any]:
    """Create a synthetic Company and set its confirmed website."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    response = client.put(
        f"/api/v1/companies/{vacancy['company']['id']}/website",
        json={"website_url": "https://example.test/"},
        headers={"Idempotency-Key": "unused-by-idempotent-put"},
    )
    assert response.status_code == 200
    return dict(response.json())


@then("Core возвращает нормализованный сайт компании")
def website_is_normalized(company: dict[str, Any]) -> None:
    """Require the public Company contract to expose the confirmed URL."""
    assert company["website_url"] == "https://example.test/"
