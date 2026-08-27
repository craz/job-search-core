"""BDD steps for SearchProfile / SearchRun persistence (R2.2.1)."""

from __future__ import annotations

from pytest_bdd import given, scenarios, then, when
from tests.support import ApiClient, create_fixture_vacancy

scenarios("../features/search_profile_run.feature")


@given('a SearchProfile with text "project manager"', target_fixture="search_ctx")
def search_profile_created() -> dict[str, object]:
    client = ApiClient()
    response = client.post(
        "/api/v1/search-profiles",
        json={"text": "project manager"},
        headers={},
    )
    assert response.status_code == 201
    return {"client": client, "profile": response.json()}


@when("I start a SearchRun with execution page_size 20")
def start_run(search_ctx: dict[str, object]) -> None:
    client = search_ctx["client"]
    profile = search_ctx["profile"]
    assert isinstance(client, ApiClient)
    response = client.post(
        "/api/v1/search-runs",
        json={
            "search_profile_id": profile["id"],  # type: ignore[index]
            "execution": {"order": "publication_time", "page_size": 20, "max_pages": 2},
        },
        headers={},
    )
    assert response.status_code == 201
    search_ctx["run"] = response.json()


@when('I change the SearchProfile text to "golang"')
def patch_profile(search_ctx: dict[str, object]) -> None:
    client = search_ctx["client"]
    profile = search_ctx["profile"]
    assert isinstance(client, ApiClient)
    response = client.patch(
        f"/api/v1/search-profiles/{profile['id']}",  # type: ignore[index]
        json={"text": "golang"},
    )
    assert response.status_code == 200


@then('the SearchRun criteria_snapshot text remains "project manager"')
def criteria_frozen(search_ctx: dict[str, object]) -> None:
    client = search_ctx["client"]
    run = search_ctx["run"]
    assert isinstance(client, ApiClient)
    body = client.get(f"/api/v1/search-runs/{run['id']}").json()  # type: ignore[index]
    assert body["criteria_snapshot"]["text"] == "project manager"
    search_ctx["run"] = body


@then("the SearchRun execution_snapshot contains page_size 20")
def execution_present(search_ctx: dict[str, object]) -> None:
    run = search_ctx["run"]
    assert run["execution_snapshot"]["page_size"] == 20  # type: ignore[index]


@when("I add a created SearchRunItem linked to a Vacancy")
def add_created_item(search_ctx: dict[str, object]) -> None:
    client = search_ctx["client"]
    run = search_ctx["run"]
    assert isinstance(client, ApiClient)
    vacancy = create_fixture_vacancy(client)
    response = client.post(
        f"/api/v1/search-runs/{run['id']}/items",  # type: ignore[index]
        json={
            "source_external_id": vacancy["external_id"],
            "vacancy_id": vacancy["id"],
            "outcome": "created",
        },
        headers={},
    )
    assert response.status_code == 201


@when("I add an error SearchRunItem without vacancy_id")
def add_error_item(search_ctx: dict[str, object]) -> None:
    client = search_ctx["client"]
    run = search_ctx["run"]
    assert isinstance(client, ApiClient)
    response = client.post(
        f"/api/v1/search-runs/{run['id']}/items",  # type: ignore[index]
        json={
            "source_external_id": "hh-error-1",
            "outcome": "error",
            "error_code": "failed",
        },
        headers={},
    )
    assert response.status_code == 201


@when("I finalize the SearchRun as partial")
def finalize_partial(search_ctx: dict[str, object]) -> None:
    client = search_ctx["client"]
    run = search_ctx["run"]
    assert isinstance(client, ApiClient)
    response = client.post(
        f"/api/v1/search-runs/{run['id']}/finalize",  # type: ignore[index]
        json={"status": "partial"},
        headers={},
    )
    assert response.status_code == 200
    search_ctx["run"] = response.json()


@then("the SearchRun status is partial with finished_at set")
def assert_terminal(search_ctx: dict[str, object]) -> None:
    run = search_ctx["run"]
    assert run["status"] == "partial"  # type: ignore[index]
    assert run["finished_at"] is not None  # type: ignore[index]


@then("counters match created 1 and error 1")
def assert_counters(search_ctx: dict[str, object]) -> None:
    run = search_ctx["run"]
    assert run["created_count"] == 1  # type: ignore[index]
    assert run["error_count"] == 1  # type: ignore[index]
    assert run["found_count"] == 2  # type: ignore[index]
