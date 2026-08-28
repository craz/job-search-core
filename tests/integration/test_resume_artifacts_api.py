"""HTTP integration coverage for resume artifact download."""

from __future__ import annotations

from tests.support import ApiClient, create_fixture_vacancy


def test_resume_artifact_download_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOB_SEARCH_CORE_ARTIFACT_DIR", str(tmp_path))
    client = ApiClient()
    create_fixture_vacancy(client)
    ingest = client.request(
        "POST",
        "/api/v1/resume-versions",
        json={
            "source": "hh",
            "external_resume_id": "artifact-api",
            "transport": "fixture",
            "content": {"title": "Engineer", "about": "About", "skills": ["go"]},
        },
    )
    assert ingest.status_code == 200
    version_id = ingest.json()["resume_version"]["id"]
    link = client.request(
        "PUT",
        "/api/v1/candidate-context/hh-resume-link",
        json={
            "external_resume_id": "artifact-api",
            "title": "Engineer",
            "status": "active",
        },
    )
    assert link.status_code == 200
    files = {"file": ("resume.pdf", b"%PDF-1.4 test", "application/pdf")}
    created = client.request(
        "POST",
        f"/api/v1/resume-versions/{version_id}/artifacts?captured_at=2026-08-28T00%3A40%3A00Z",
        files=files,
    )
    assert created.status_code == 200
    artifact_id = created.json()["artifact"]["id"]
    meta = client.get(f"/api/v1/resume-artifacts/{artifact_id}")
    assert meta.status_code == 200
    assert meta.json()["mime_type"] == "application/pdf"
    assert meta.json()["original_filename"] == "resume.pdf"
    downloaded = client.request("GET", f"/api/v1/resume-artifacts/{artifact_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.4 test"
    assert downloaded.headers["content-type"].startswith("application/pdf")
    context = client.get("/api/v1/candidate-context")
    resume_file = context.json().get("resume_file")
    assert resume_file is not None
    assert resume_file["artifact_id"] == artifact_id
    assert resume_file["format_label"] == "PDF"
