"""R2.1.4 ResumeVersion history / switch / clear semantics (fixture-driven)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from tests.support import create_test_database

from job_search_core.candidate_context import set_hh_resume_link
from job_search_core.models import ResumeVersion
from job_search_core.resume_versions import (
    ingest_resume_version,
    latest_resume_version,
    resume_content_meta,
)
from job_search_core.schemas import HhResumeLinkUpdate, ResumeVersionIngest


def _content(*, title: str, about: str = "About") -> dict[str, object]:
    return {
        "title": title,
        "about": about,
        "skills": ["Python"],
        "experience": [{"company": "Labs", "position": "PM", "description": "Work"}],
    }


def _ingest(
    session: object,
    *,
    external_resume_id: str,
    title: str,
    captured_at: datetime,
) -> object:
    return ingest_resume_version(
        session,  # type: ignore[arg-type]
        ResumeVersionIngest(
            source="hh",
            external_resume_id=external_resume_id,
            content=_content(title=title),
            transport="fixture",
            extractor_version="r214-fixture",
            captured_at=captured_at,
        ),
    )


def test_history_identical_changed_identical_and_independent_ids() -> None:
    """A–D: dedup, new version on change, no third duplicate, separate resume ids."""
    database = create_test_database()
    with database.session() as session:
        set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id="resume-a", title="A"),
        )
        v1 = _ingest(
            session,
            external_resume_id="resume-a",
            title="v1",
            captured_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        assert v1.created is True
        v1_id = v1.resume_version.id
        v1_hash = v1.resume_version.content_hash

        identical = _ingest(
            session,
            external_resume_id="resume-a",
            title="v1",
            captured_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
        )
        assert identical.created is False
        assert identical.resume_version.id == v1_id
        assert identical.resume_version.content_hash == v1_hash

        v2 = _ingest(
            session,
            external_resume_id="resume-a",
            title="v2-changed",
            captured_at=datetime(2026, 8, 2, tzinfo=UTC),
        )
        assert v2.created is True
        v2_id = v2.resume_version.id
        assert v2_id != v1_id

        unchanged_latest = _ingest(
            session,
            external_resume_id="resume-a",
            title="v2-changed",
            captured_at=datetime(2026, 8, 2, 12, tzinfo=UTC),
        )
        assert unchanged_latest.created is False
        assert unchanged_latest.resume_version.id == v2_id

        rows_a = session.scalars(
            select(ResumeVersion).where(ResumeVersion.external_resume_id == "resume-a")
        ).all()
        assert len(rows_a) == 2
        assert {row.id for row in rows_a} == {v1_id, v2_id}
        preserved = session.get(ResumeVersion, v1_id)
        assert preserved is not None
        assert preserved.content["title"] == "v1"

        latest = latest_resume_version(
            session,
            profile_version_id=v2.resume_version.profile_version_id,
            source="hh",
            external_resume_id="resume-a",
        )
        assert latest is not None
        assert latest.id == v2_id

        # D: other external_resume_id has independent history / no cross-dedup
        other = _ingest(
            session,
            external_resume_id="resume-b",
            title="v1",  # same title/hash payload as A's v1, different id scope
            captured_at=datetime(2026, 8, 3, tzinfo=UTC),
        )
        assert other.created is True
        assert other.resume_version.id not in {v1_id, v2_id}
        assert other.resume_version.content_hash == v1_hash
        count_a = session.scalar(
            select(func.count())
            .select_from(ResumeVersion)
            .where(ResumeVersion.external_resume_id == "resume-a")
        )
        count_b = session.scalar(
            select(func.count())
            .select_from(ResumeVersion)
            .where(ResumeVersion.external_resume_id == "resume-b")
        )
        assert count_a == 2
        assert count_b == 1


def test_switch_unsynced_synced_and_clear_preserve_history() -> None:
    """E–G: switch / return / clear without pointer table or history deletion."""
    database = create_test_database()
    with database.session() as session:
        set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id="resume-a", title="A"),
        )
        v1 = _ingest(
            session,
            external_resume_id="resume-a",
            title="A-v1",
            captured_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        meta_a = resume_content_meta(session, v1.candidate_context)
        assert meta_a is not None
        assert meta_a.content_state == "synced"
        assert meta_a.resume_version_id == v1.resume_version.id

        # E: switch to never-synced resume B — honest not_synced, no A snapshot
        ctx_b = set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id="resume-b", title="B"),
        )
        meta_b = resume_content_meta(session, ctx_b)
        assert meta_b is not None
        assert meta_b.content_state == "not_synced"
        assert meta_b.external_resume_id == "resume-b"
        assert meta_b.resume_version_id is None
        assert meta_b.captured_at is None

        # F: return to previously synced A — latest local for A, no new ingest
        before_count = session.scalar(select(func.count()).select_from(ResumeVersion))
        ctx_back = set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id="resume-a", title="A"),
        )
        meta_back = resume_content_meta(session, ctx_back)
        assert meta_back is not None
        assert meta_back.content_state == "synced"
        assert meta_back.resume_version_id == v1.resume_version.id
        assert meta_back.external_resume_id == "resume-a"
        assert meta_back.captured_at == v1.resume_version.captured_at
        after_switch = session.scalar(select(func.count()).select_from(ResumeVersion))
        assert after_switch == before_count

        # G: clear — no current content; history kept
        ctx_clear = set_hh_resume_link(session, HhResumeLinkUpdate(external_resume_id=None))
        meta_clear = resume_content_meta(session, ctx_clear)
        assert meta_clear is not None
        assert meta_clear.content_state == "none"
        assert meta_clear.resume_version_id is None
        assert meta_clear.external_resume_id is None
        assert session.get(ResumeVersion, v1.resume_version.id) is not None
        assert ctx_clear.hh_resume_link is not None
        assert ctx_clear.hh_resume_link.status.value == "cleared"
