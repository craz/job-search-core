"""pytest-bdd bindings for ResumeVersion history semantics (R2.1.4)."""

from __future__ import annotations

import httpx
from pytest_bdd import given, scenarios, then, when
from tests.support import ApiClient

scenarios("../features/resume_version_history.feature")


def _content(*, title: str) -> dict[str, object]:
    return {
        "title": title,
        "about": "About",
        "skills": ["Python"],
        "experience": [{"company": "Labs", "position": "PM", "description": "Work"}],
    }


def _ingest(client: ApiClient, *, external_id: str, title: str) -> httpx.Response:
    return client.post(
        "/api/v1/resume-versions",
        json={
            "source": "hh",
            "external_resume_id": external_id,
            "transport": "fixture",
            "extractor_version": "r214-bdd",
            "content": _content(title=title),
        },
        headers={},
    )


@given("an active HH resume link for resume A", target_fixture="history_state")
def active_link_a() -> dict[str, object]:
    client = ApiClient()
    linked = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": "bdd-resume-a", "title": "A"},
        headers={},
    )
    assert linked.status_code == 200
    return {"client": client, "v1": None, "v2": None}


@given("a ResumeVersion v1 ingested from fixture content for resume A")
def ingest_v1(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = _ingest(client, external_id="bdd-resume-a", title="bdd-v1")
    assert response.status_code == 200
    assert response.json()["created"] is True
    history_state["v1"] = response.json()["resume_version"]["id"]


@when("the operator ingests changed fixture content for resume A")
def ingest_changed(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = _ingest(client, external_id="bdd-resume-a", title="bdd-v2")
    assert response.status_code == 200
    assert response.json()["created"] is True
    history_state["v2"] = response.json()["resume_version"]["id"]


@then("a new ResumeVersion v2 is created")
def v2_created(history_state: dict[str, object]) -> None:
    assert history_state["v2"]
    assert history_state["v2"] != history_state["v1"]


@then("v1 remains readable by id")
def v1_readable(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = client.get(f"/api/v1/resume-versions/{history_state['v1']}")
    assert response.status_code == 200
    assert response.json()["content"]["title"] == "bdd-v1"


@then("candidate-context current copy points at v2")
def context_points_v2(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    context = client.get("/api/v1/candidate-context")
    assert context.status_code == 200
    assert context.json()["resume_content"]["resume_version_id"] == history_state["v2"]


@given(
    "ResumeVersions v1 and v2 for resume A where v2 is latest",
    target_fixture="history_state",
)
def two_versions() -> dict[str, object]:
    client = ApiClient()
    assert (
        client.put(
            "/api/v1/candidate-context/hh-resume-link",
            json={"external_resume_id": "bdd-resume-a2", "title": "A"},
            headers={},
        ).status_code
        == 200
    )
    v1 = _ingest(client, external_id="bdd-resume-a2", title="bdd-a2-v1")
    v2 = _ingest(client, external_id="bdd-resume-a2", title="bdd-a2-v2")
    assert v1.json()["created"] is True
    assert v2.json()["created"] is True
    return {
        "client": client,
        "v1": v1.json()["resume_version"]["id"],
        "v2": v2.json()["resume_version"]["id"],
        "external_id": "bdd-resume-a2",
    }


@when("the operator ingests content identical to v2")
def ingest_identical_v2(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = _ingest(
        client,
        external_id=str(history_state["external_id"]),
        title="bdd-a2-v2",
    )
    history_state["identical"] = response.json()


@then("no third ResumeVersion is created for resume A")
def no_third(history_state: dict[str, object]) -> None:
    identical = history_state["identical"]
    assert isinstance(identical, dict)
    assert identical["created"] is False
    assert identical["resume_version"]["id"] == history_state["v2"]


@given("ResumeVersion history exists for resume A", target_fixture="history_state")
def history_for_switch() -> dict[str, object]:
    client = ApiClient()
    assert (
        client.put(
            "/api/v1/candidate-context/hh-resume-link",
            json={"external_resume_id": "bdd-resume-switch-a", "title": "A"},
            headers={},
        ).status_code
        == 200
    )
    v1 = _ingest(client, external_id="bdd-resume-switch-a", title="switch-v1")
    assert v1.json()["created"] is True
    return {
        "client": client,
        "v1": v1.json()["resume_version"]["id"],
        "external_id": "bdd-resume-switch-a",
    }


@when("the operator activates never-synced resume C")
def activate_c(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": "bdd-resume-c", "title": "C"},
        headers={},
    )
    history_state["switch_c"] = response.json()


@then("candidate-context shows content_state not_synced for C")
def not_synced_c(history_state: dict[str, object]) -> None:
    body = history_state["switch_c"]
    assert isinstance(body, dict)
    meta = body["resume_content"]
    assert meta["content_state"] == "not_synced"
    assert meta["external_resume_id"] == "bdd-resume-c"
    assert meta["resume_version_id"] is None


@when("the operator activates resume A again")
def activate_a_again(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": str(history_state["external_id"]), "title": "A"},
        headers={},
    )
    history_state["back_a"] = response.json()


@then("candidate-context shows synced metadata for A's latest version")
def synced_a(history_state: dict[str, object]) -> None:
    body = history_state["back_a"]
    assert isinstance(body, dict)
    meta = body["resume_content"]
    assert meta["content_state"] == "synced"
    assert meta["resume_version_id"] == history_state["v1"]
    assert meta["captured_at"]


@when("the operator clears the active HH resume")
def clear_active(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": None},
        headers={},
    )
    history_state["cleared"] = response.json()


@then("candidate-context content_state is none")
def content_none(history_state: dict[str, object]) -> None:
    body = history_state["cleared"]
    assert isinstance(body, dict)
    assert body["resume_content"]["content_state"] == "none"
    assert body["resume_content"]["resume_version_id"] is None


@then("historical ResumeVersions for A remain readable")
def history_readable(history_state: dict[str, object]) -> None:
    client: ApiClient = history_state["client"]  # type: ignore[assignment]
    response = client.get(f"/api/v1/resume-versions/{history_state['v1']}")
    assert response.status_code == 200
    assert response.json()["content"]["title"] == "switch-v1"
