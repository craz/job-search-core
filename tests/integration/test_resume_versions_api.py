"""HTTP integration for ResumeVersion ingest / read (R2.1.1)."""

from tests.support import ApiClient


def _content(*, title: str = "Fixture PM") -> dict[str, object]:
    return {
        "title": title,
        "about": "About",
        "skills": ["Python"],
        "experience": [{"company": "Labs", "position": "PM", "description": "Work"}],
    }


def test_resume_version_ingest_dedup_and_full_read() -> None:
    client = ApiClient()
    linked = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": "resume-fixture-1", "title": "Fixture PM"},
        headers={},
    )
    assert linked.status_code == 200
    assert linked.json()["resume_content"]["content_state"] == "not_synced"

    created = client.post(
        "/api/v1/resume-versions",
        json={
            "source": "hh",
            "external_resume_id": "resume-fixture-1",
            "transport": "fixture",
            "extractor_version": "integration-1",
            "content": _content(),
        },
        headers={},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["created"] is True
    version_id = body["resume_version"]["id"]
    assert body["candidate_context"]["resume_content"]["content_state"] == "synced"
    assert body["candidate_context"]["resume_content"]["resume_version_id"] == version_id
    assert "content" not in body["resume_version"]
    assert "about" not in str(body["candidate_context"])

    again = client.post(
        "/api/v1/resume-versions",
        json={
            "source": "hh",
            "external_resume_id": "resume-fixture-1",
            "transport": "fixture",
            "content": _content(title="  Fixture PM  "),
        },
        headers={},
    )
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["resume_version"]["id"] == version_id

    changed = client.post(
        "/api/v1/resume-versions",
        json={
            "source": "hh",
            "external_resume_id": "resume-fixture-1",
            "transport": "fixture",
            "content": _content(title="Fixture PM v2"),
        },
        headers={},
    )
    assert changed.status_code == 200
    assert changed.json()["created"] is True
    new_id = changed.json()["resume_version"]["id"]
    assert new_id != version_id

    full = client.get(f"/api/v1/resume-versions/{new_id}")
    assert full.status_code == 200
    snapshot = full.json()
    assert snapshot["content"]["title"] == "Fixture PM v2"
    assert snapshot["content"]["skills"] == ["Python"]
    assert "phone" not in snapshot["content"]

    context = client.get("/api/v1/candidate-context")
    assert context.status_code == 200
    meta = context.json()["resume_content"]
    assert meta["content_state"] == "synced"
    assert meta["resume_version_id"] == new_id
    assert "content" not in context.json()


def test_candidate_context_empty_includes_null_resume_content() -> None:
    client = ApiClient()
    empty = client.get("/api/v1/candidate-context")
    assert empty.status_code == 200
    assert empty.json() == {
        "candidate_profile": None,
        "profile_version": None,
        "hh_resume_link": None,
        "resume_content": None,
    }
