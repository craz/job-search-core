"""pytest-bdd bindings that execute the Core platform Gherkin contract."""

import httpx
from pytest_bdd import scenarios, then, when
from tests.support import ApiClient

scenarios("../features/core_platform.feature")


def request(path: str) -> httpx.Response:
    """Send a synchronous BDD step through HTTPX's maintained ASGI transport."""
    return ApiClient().get(path)


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
