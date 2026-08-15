"""HTTP integration tests for infrastructure health contracts."""

import anyio
import httpx

from job_search_core.app import create_app


def request(path: str) -> httpx.Response:
    """Send one request through ASGI without deprecated TestClient adapters."""

    async def send() -> httpx.Response:
        """Own the AsyncClient lifecycle inside the synchronous pytest test."""
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://core.test") as client:
            return await client.get(path)

    return anyio.run(send)


def test_liveness_endpoint_returns_versioned_component_identity() -> None:
    """A process probe must receive stable identity without external services."""
    response = request("/health/live")

    assert response.status_code == 200
    assert response.json()["component"] == "job-search-core"
    assert response.json()["status"] == "ok"
