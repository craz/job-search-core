"""Contract tests for the published OpenAPI document."""

from job_search_core.app import create_app


def test_health_contract_is_present_in_openapi() -> None:
    """Both probe paths must remain discoverable to consumers and tooling."""
    paths = create_app().openapi()["paths"]

    assert "/health/live" in paths
    assert "/health/ready" in paths
