"""HTTP integration for R2.1.4 ResumeVersion history / switch / clear."""

from __future__ import annotations

from tests.support import ApiClient


def _content(*, title: str) -> dict[str, object]:
    return {
        "title": title,
        "about": "About",
        "skills": ["Python"],
        "experience": [{"company": "Labs", "position": "PM", "description": "Work"}],
    }


def _ingest(client: ApiClient, *, external_id: str, title: str) -> dict:
    response = client.post(
        "/api/v1/resume-versions",
        json={
            "source": "hh",
            "external_resume_id": external_id,
            "transport": "fixture",
            "extractor_version": "r214-integration",
            "content": _content(title=title),
        },
        headers={},
    )
    assert response.status_code == 200
    return response.json()


def test_history_switch_return_clear_http() -> None:
    client = ApiClient()

    linked_a = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": "hist-resume-a", "title": "A"},
        headers={},
    )
    assert linked_a.status_code == 200
    assert linked_a.json()["resume_content"]["content_state"] == "not_synced"

    first = _ingest(client, external_id="hist-resume-a", title="A-v1")
    assert first["created"] is True
    v1 = first["resume_version"]["id"]
    v1_hash = first["resume_version"]["content_hash"]

    same = _ingest(client, external_id="hist-resume-a", title="A-v1")
    assert same["created"] is False
    assert same["resume_version"]["id"] == v1

    changed = _ingest(client, external_id="hist-resume-a", title="A-v2")
    assert changed["created"] is True
    v2 = changed["resume_version"]["id"]
    assert v2 != v1

    same_v2 = _ingest(client, external_id="hist-resume-a", title="A-v2")
    assert same_v2["created"] is False
    assert same_v2["resume_version"]["id"] == v2

    full_v1 = client.get(f"/api/v1/resume-versions/{v1}")
    assert full_v1.status_code == 200
    assert full_v1.json()["content"]["title"] == "A-v1"
    assert full_v1.json()["content_hash"] == v1_hash

    full_v2 = client.get(f"/api/v1/resume-versions/{v2}")
    assert full_v2.status_code == 200
    assert full_v2.json()["content"]["title"] == "A-v2"

    ctx = client.get("/api/v1/candidate-context")
    assert ctx.json()["resume_content"]["resume_version_id"] == v2

    # Independent history for another resume id (same title payload as A-v1)
    other = _ingest(client, external_id="hist-resume-b", title="A-v1")
    assert other["created"] is True
    assert other["resume_version"]["id"] not in {v1, v2}
    assert other["resume_version"]["content_hash"] == v1_hash

    # E: switch to unsynced C
    switch_c = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": "hist-resume-c", "title": "C"},
        headers={},
    )
    assert switch_c.status_code == 200
    meta_c = switch_c.json()["resume_content"]
    assert meta_c["content_state"] == "not_synced"
    assert meta_c["external_resume_id"] == "hist-resume-c"
    assert meta_c["resume_version_id"] is None

    # F: return to A — latest local v2, no fetch required
    back_a = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": "hist-resume-a", "title": "A"},
        headers={},
    )
    assert back_a.status_code == 200
    meta_a = back_a.json()["resume_content"]
    assert meta_a["content_state"] == "synced"
    assert meta_a["resume_version_id"] == v2
    assert meta_a["external_resume_id"] == "hist-resume-a"
    assert meta_a["captured_at"]

    # G: clear — no current content; history still readable
    cleared = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": None},
        headers={},
    )
    assert cleared.status_code == 200
    assert cleared.json()["hh_resume_link"]["status"] == "cleared"
    meta_clear = cleared.json()["resume_content"]
    assert meta_clear["content_state"] == "none"
    assert meta_clear["resume_version_id"] is None
    assert meta_clear["external_resume_id"] is None
    assert client.get(f"/api/v1/resume-versions/{v1}").status_code == 200
    assert client.get(f"/api/v1/resume-versions/{v2}").status_code == 200
