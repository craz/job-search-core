"""Unit tests for resume artifact persistence and download contract."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from tests.support import ApiClient, create_fixture_vacancy

from job_search_core.models import ResumeVersion
from job_search_core.resume_artifact_storage import sha256_hex
from job_search_core.resume_artifacts import (
    ResumeArtifactValidationError,
    format_label_for_mime,
    ingest_resume_artifact,
    load_resume_artifact_bytes,
)


def _resume_version_id(client: ApiClient) -> uuid.UUID:
    create_fixture_vacancy(client)
    response = client.request(
        "POST",
        "/api/v1/resume-versions",
        json={
            "source": "hh",
            "external_resume_id": "resume-artifact-fixture",
            "transport": "fixture",
            "content": {
                "title": "Backend Engineer",
                "about": "Synthetic resume",
                "skills": ["python"],
            },
        },
    )
    assert response.status_code == 200
    return uuid.UUID(response.json()["resume_version"]["id"])


def test_format_label_for_pdf() -> None:
    assert format_label_for_mime("application/pdf", "resume.pdf") == "PDF"


def test_ingest_and_download_round_trip(tmp_path) -> None:
    client = ApiClient()
    version_id = _resume_version_id(client)
    payload = b"%PDF-1.4\n% resume bytes"
    with client.database.session() as session:
        result = ingest_resume_artifact(
            session,
            artifact_root=tmp_path,
            resume_version_id=version_id,
            data=payload,
            mime_type="application/pdf",
            original_filename="resume.pdf",
            captured_at=datetime(2026, 8, 28, 0, 40, tzinfo=UTC),
        )
        assert result.created is True
        assert result.artifact.sha256 == sha256_hex(payload)
        replay = ingest_resume_artifact(
            session,
            artifact_root=tmp_path,
            resume_version_id=version_id,
            data=payload,
            mime_type="application/pdf",
            original_filename="resume.pdf",
            captured_at=datetime(2026, 8, 28, 0, 40, tzinfo=UTC),
        )
        assert replay.created is False
        loaded = load_resume_artifact_bytes(tmp_path, result.artifact)
        assert loaded == payload


def test_ingest_rejects_path_traversal_filename(tmp_path) -> None:
    client = ApiClient()
    version_id = _resume_version_id(client)
    with client.database.session() as session:
        with pytest.raises(ResumeArtifactValidationError):
            ingest_resume_artifact(
                session,
                artifact_root=tmp_path,
                resume_version_id=version_id,
                data=b"data",
                mime_type="application/pdf",
                original_filename="../evil.pdf",
            )


def test_existing_resume_version_can_receive_artifact_without_new_version(tmp_path) -> None:
    client = ApiClient()
    version_id = _resume_version_id(client)
    with client.database.session() as session:
        row = session.get(ResumeVersion, version_id)
        assert row is not None
        before_hash = row.content_hash
        ingest_resume_artifact(
            session,
            artifact_root=tmp_path,
            resume_version_id=version_id,
            data=b"rtf-content",
            mime_type="application/rtf",
            original_filename="resume.rtf",
        )
        after = session.get(ResumeVersion, version_id)
        assert after is not None
        assert after.content_hash == before_hash
