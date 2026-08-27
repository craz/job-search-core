"""HTTP integration for SearchProfile / SearchRun / SearchRunItem (R2.2.1)."""

from __future__ import annotations

from tests.support import ApiClient, create_fixture_vacancy


def test_search_profile_run_lifecycle_and_items() -> None:
    client = ApiClient()
    created = client.post(
        "/api/v1/search-profiles",
        json={
            "label": "Default HH",
            "text": "project manager",
            "area_id": "1",
            "salary": {"from": 200000, "to": 400000, "currency": "RUR"},
            "experience": "between3And6",
            "search_field": "name",
            "only_with_salary": True,
        },
        headers={},
    )
    assert created.status_code == 201
    profile = created.json()
    assert profile["text"] == "project manager"
    assert "page_size" not in profile
    assert "max_pages" not in profile
    assert "order" not in profile
    assert profile["salary"]["from"] == 200000

    run_resp = client.post(
        "/api/v1/search-runs",
        json={
            "search_profile_id": profile["id"],
            "execution": {"order": "publication_time", "page_size": 20, "max_pages": 3},
        },
        headers={},
    )
    assert run_resp.status_code == 201
    run = run_resp.json()
    assert run["status"] == "running"
    assert run["finished_at"] is None
    assert run["source"] == "hh"
    assert run["criteria_snapshot"]["text"] == "project manager"
    assert run["criteria_snapshot"]["salary"]["from"] == 200000
    assert "page_size" not in run["criteria_snapshot"]
    assert run["execution_snapshot"]["page_size"] == 20
    assert run["execution_snapshot"]["max_pages"] == 3
    assert run["execution_snapshot"]["order"] == "publication_time"
    run_id = run["id"]

    patched = client.patch(
        f"/api/v1/search-profiles/{profile['id']}",
        json={"text": "golang developer"},
    )
    assert patched.status_code == 200
    assert patched.json()["text"] == "golang developer"

    unchanged_run = client.get(f"/api/v1/search-runs/{run_id}").json()
    assert unchanged_run["criteria_snapshot"]["text"] == "project manager"

    vacancy = create_fixture_vacancy(client)
    created_item = client.post(
        f"/api/v1/search-runs/{run_id}/items",
        json={
            "source_external_id": vacancy["external_id"],
            "vacancy_id": vacancy["id"],
            "outcome": "created",
            "page": 0,
        },
        headers={},
    )
    assert created_item.status_code == 201
    assert created_item.json()["vacancy_id"] == vacancy["id"]

    error_item = client.post(
        f"/api/v1/search-runs/{run_id}/items",
        json={
            "source_external_id": "hh-missing-99",
            "outcome": "error",
            "error_code": "detail_failed",
            "error_detail": "timeout",
        },
        headers={},
    )
    assert error_item.status_code == 201
    assert error_item.json()["vacancy_id"] is None
    assert error_item.json()["source_external_id"] == "hh-missing-99"

    reject = client.post(
        f"/api/v1/search-runs/{run_id}/items",
        json={"source_external_id": "hh-no-vacancy", "outcome": "updated"},
        headers={},
    )
    assert reject.status_code == 400
    assert reject.json()["code"] == "invalid_search_run_item"

    duplicate = client.post(
        f"/api/v1/search-runs/{run_id}/items",
        json={
            "source_external_id": vacancy["external_id"],
            "vacancy_id": vacancy["id"],
            "outcome": "unchanged",
        },
        headers={},
    )
    assert duplicate.status_code == 409

    finalized = client.post(
        f"/api/v1/search-runs/{run_id}/finalize",
        json={"status": "partial"},
        headers={},
    )
    assert finalized.status_code == 200
    body = finalized.json()
    assert body["status"] == "partial"
    assert body["finished_at"] is not None
    assert body["found_count"] == 2
    assert body["created_count"] == 1
    assert body["error_count"] == 1
    assert body["updated_count"] == 0
    assert body["unchanged_count"] == 0

    items = client.get(f"/api/v1/search-runs/{run_id}/items").json()
    assert items["total"] == 2

    after_terminal = client.post(
        f"/api/v1/search-runs/{run_id}/items",
        json={
            "source_external_id": "late",
            "vacancy_id": vacancy["id"],
            "outcome": "unchanged",
        },
        headers={},
    )
    assert after_terminal.status_code == 409
    assert after_terminal.json()["code"] == "search_run_not_running"

    repeat_finalize = client.post(
        f"/api/v1/search-runs/{run_id}/finalize",
        json={"status": "partial"},
        headers={},
    )
    assert repeat_finalize.status_code == 409
    assert repeat_finalize.json()["code"] == "search_run_not_running"

    switch_terminal = client.post(
        f"/api/v1/search-runs/{run_id}/finalize",
        json={"status": "success"},
        headers={},
    )
    assert switch_terminal.status_code == 409
    assert switch_terminal.json()["code"] == "search_run_not_running"

    frozen = client.get(f"/api/v1/search-runs/{run_id}").json()
    assert frozen["status"] == "partial"
    assert frozen["found_count"] == 2
    assert frozen["created_count"] == 1
    assert frozen["error_count"] == 1
    assert client.get(f"/api/v1/search-runs/{run_id}/items").json()["total"] == 2
