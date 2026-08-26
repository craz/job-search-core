"""HTTP integration for candidate-context / HH resume linkage (R1.5)."""

from tests.support import ApiClient


def test_candidate_context_empty_then_link_then_clear() -> None:
    client = ApiClient()
    empty = client.get("/api/v1/candidate-context")
    assert empty.status_code == 200
    assert empty.json() == {
        "candidate_profile": None,
        "profile_version": None,
        "hh_resume_link": None,
    }

    linked = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": "resume-fixture-1", "title": "Fixture PM"},
        headers={},
    )
    assert linked.status_code == 200
    body = linked.json()
    assert body["candidate_profile"]["id"]
    assert body["profile_version"]["label"] == "r1-default"
    assert body["hh_resume_link"]["source"] == "hh"
    assert body["hh_resume_link"]["external_resume_id"] == "resume-fixture-1"
    assert body["hh_resume_link"]["status"] == "active"
    assert body["hh_resume_link"]["title"] == "Fixture PM"

    again = client.get("/api/v1/candidate-context")
    assert again.status_code == 200
    assert again.json()["hh_resume_link"]["external_resume_id"] == "resume-fixture-1"

    cleared = client.put(
        "/api/v1/candidate-context/hh-resume-link",
        json={"external_resume_id": None},
        headers={},
    )
    assert cleared.status_code == 200
    assert cleared.json()["hh_resume_link"]["status"] == "cleared"
    assert cleared.json()["candidate_profile"]["id"] == body["candidate_profile"]["id"]
