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
    assert "patch" in document["paths"]["/api/v1/vacancies/{vacancy_id}"]
    assert "VacancyStatusUpdate" in document["components"]["schemas"]


def test_application_v1_contract_requires_idempotency_and_publishes_schemas() -> None:
    """Consumers can discover Application create/list and required retry metadata."""
    document = create_app().openapi()
    path = document["paths"]["/api/v1/applications"]

    assert {"get", "post"} <= path.keys()
    key = next(item for item in path["post"]["parameters"] if item["name"] == "Idempotency-Key")
    assert key["required"] is True
    assert "ApplicationCreate" in document["components"]["schemas"]
    assert "ApplicationRead" in document["components"]["schemas"]


def test_daily_metric_v1_contract_publishes_dated_put_and_reads() -> None:
    """Consumers discover bounded list/single reads and the mandatory write key."""
    document = create_app().openapi()
    collection = document["paths"]["/api/v1/metrics"]
    dated = document["paths"]["/api/v1/metrics/{metric_date}"]

    assert "get" in collection
    assert {"get", "put"} <= dated.keys()
    key = next(item for item in dated["put"]["parameters"] if item["name"] == "Idempotency-Key")
    assert key["required"] is True
    assert "DailyMetricUpdate" in document["components"]["schemas"]
    assert "DailyMetricRead" in document["components"]["schemas"]


def test_people_v1_contract_requires_idempotency_and_controlled_status() -> None:
    """Consumers discover confirmed-contact create/list/status contracts."""
    document = create_app().openapi()
    collection = document["paths"]["/api/v1/people"]
    item = document["paths"]["/api/v1/people/{person_id}"]

    assert {"get", "post"} <= collection.keys()
    assert "patch" in item
    key = next(
        parameter
        for parameter in collection["post"]["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert key["required"] is True
    assert "PersonCreate" in document["components"]["schemas"]
    assert "PersonStatusUpdate" in document["components"]["schemas"]
