"""pytest-bdd bindings that execute the Core platform Gherkin contract."""

import anyio
import httpx
from pytest_bdd import scenarios, then, when

from job_search_core.app import create_app

scenarios("../features/core_platform.feature")


def request(path: str) -> httpx.Response:
    """Send a synchronous BDD step through HTTPX's maintained ASGI transport."""

    async def send() -> httpx.Response:
        """Isolate the asynchronous client lifecycle from pytest-bdd steps."""
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://core.test") as client:
            return await client.get(path)

    return anyio.run(send)


@when("клиент запрашивает статус готовности Core", target_fixture="response")
def request_readiness() -> httpx.Response:
    """Call readiness through ASGI so the scenario exercises routing and schema."""
    return request("/health/ready")


@then("Core отвечает успешно")
def response_is_successful(response: httpx.Response) -> None:
    """Require an HTTP success and the explicit healthy status value."""
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@then("ответ идентифицирует компонент job-search-core")
def response_identifies_core(response: httpx.Response) -> None:
    """Prevent a healthy response from an incorrectly wired sibling service."""
    assert response.json()["component"] == "job-search-core"
