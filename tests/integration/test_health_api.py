"""HTTP integration tests for infrastructure health contracts."""

from tests.support import ApiClient


def test_liveness_endpoint_returns_versioned_component_identity() -> None:
    """A process probe must receive stable identity without external services."""
    response = ApiClient().get("/health/live")

    assert response.status_code == 200
    assert response.json()["component"] == "job-search-core"
    assert response.json()["status"] == "ok"


def test_readiness_checks_database_connectivity() -> None:
    """Readiness succeeds when the configured database accepts a query."""
    response = ApiClient().get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
