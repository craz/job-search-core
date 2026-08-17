"""Contract tests for the published OpenAPI document."""

from job_search_core.app import create_app


def test_health_contract_is_present_in_openapi() -> None:
    """Both probe paths must remain discoverable to consumers and tooling."""
    paths = create_app().openapi()["paths"]

    assert "/health/live" in paths
    assert "/health/ready" in paths


def test_vacancy_v1_contract_requires_idempotency_and_publishes_schemas() -> None:
    """Consumers can discover create/list endpoints and the mandatory retry key."""
    document = create_app().openapi()
    path = document["paths"]["/api/v1/vacancies"]

    assert {"get", "post"} <= path.keys()
    parameters = path["post"]["parameters"]
    key = next(item for item in parameters if item["name"] == "Idempotency-Key")
    assert key["required"] is True
    assert "VacancyRead" in document["components"]["schemas"]
    assert "ErrorDetail" in document["components"]["schemas"]
