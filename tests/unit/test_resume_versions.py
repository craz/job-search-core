"""Unit tests for immutable ResumeVersion ingest / dedup (R2.1.1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from tests.support import create_test_database

from job_search_core.candidate_context import set_hh_resume_link
from job_search_core.models import ResumeVersion
from job_search_core.resume_versions import (
    ResumeVersionValidationError,
    ingest_resume_version,
    latest_resume_version,
    resume_content_meta,
)
from job_search_core.schemas import HhResumeLinkUpdate, ResumeVersionIngest


def _fixture_content(*, title: str = "Fixture PM") -> dict[str, object]:
    return {
        "title": title,
        "about": "About text",
        "skills": ["Python", "SQL"],
        "experience": [
            {
                "company": "Example Labs",
                "position": "PM",
                "period": "2021—2023",
                "description": "Delivery",
            }
        ],
    }


def test_ingest_creates_immutable_row_and_metadata() -> None:
    database = create_test_database()
    with database.session() as session:
        set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id="resumehash01", title="Fixture PM"),
        )
        result = ingest_resume_version(
            session,
            ResumeVersionIngest(
                source="hh",
                external_resume_id="resumehash01",
                content=_fixture_content(),
                transport="fixture",
                extractor_version="unit-1",
            ),
        )
        assert result.created is True
        assert result.resume_version.content_hash
        assert result.resume_version.content["title"] == "Fixture PM"
        assert "phone" not in result.resume_version.content
        meta = resume_content_meta(session, result.candidate_context)
        assert meta is not None
        assert meta.content_state == "synced"
        assert meta.resume_version_id == result.resume_version.id
        assert meta.external_resume_id == "resumehash01"


def test_unchanged_ingest_does_not_duplicate() -> None:
    database = create_test_database()
    with database.session() as session:
        first = ingest_resume_version(
            session,
            ResumeVersionIngest(
                external_resume_id="resumehash01",
                content=_fixture_content(),
                transport="fixture",
            ),
        )
        second = ingest_resume_version(
            session,
            ResumeVersionIngest(
                external_resume_id="resumehash01",
                content=_fixture_content(title="  Fixture PM  "),
                transport="fixture",
            ),
        )
        assert first.created is True
        assert second.created is False
        assert second.resume_version.id == first.resume_version.id
        count = len(session.scalars(select(ResumeVersion)).all())
        assert count == 1


def test_changed_ingest_creates_new_version_keeps_old() -> None:
    database = create_test_database()
    with database.session() as session:
        first = ingest_resume_version(
            session,
            ResumeVersionIngest(
                external_resume_id="resumehash01",
                content=_fixture_content(title="v1"),
                transport="fixture",
                captured_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        )
        second = ingest_resume_version(
            session,
            ResumeVersionIngest(
                external_resume_id="resumehash01",
                content=_fixture_content(title="v2"),
                transport="fixture",
                captured_at=datetime(2026, 8, 2, tzinfo=UTC),
            ),
        )
        assert first.created is True
        assert second.created is True
        assert second.resume_version.id != first.resume_version.id
        rows = session.scalars(select(ResumeVersion)).all()
        assert len(rows) == 2
        latest = latest_resume_version(
            session,
            profile_version_id=second.resume_version.profile_version_id,
            source="hh",
            external_resume_id="resumehash01",
        )
        assert latest is not None
        assert latest.id == second.resume_version.id
        assert latest.content["title"] == "v2"


def test_empty_snapshot_rejected() -> None:
    database = create_test_database()
    with database.session() as session:
        with pytest.raises(ResumeVersionValidationError):
            ingest_resume_version(
                session,
                ResumeVersionIngest(
                    external_resume_id="resumehash01",
                    content={"phone": "+7000", "email": "a@b.c"},
                    transport="fixture",
                ),
            )
        assert session.scalars(select(ResumeVersion)).all() == []


def test_active_link_without_version_is_not_synced() -> None:
    database = create_test_database()
    with database.session() as session:
        context = set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id="resumehash01", title="PM"),
        )
        meta = resume_content_meta(session, context)
        assert meta is not None
        assert meta.content_state == "not_synced"
        assert meta.resume_version_id is None
        assert meta.external_resume_id == "resumehash01"
