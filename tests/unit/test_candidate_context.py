"""Unit tests for CandidateProfile / ProfileVersion / HH resume link (R1.5)."""

from __future__ import annotations

from tests.support import create_test_database

from job_search_core.candidate_context import get_candidate_context, set_hh_resume_link
from job_search_core.models import HhResumeLinkStatus
from job_search_core.schemas import HhResumeLinkUpdate


def test_fresh_install_has_no_automatic_candidate_context() -> None:
    database = create_test_database()
    with database.session() as session:
        context = get_candidate_context(session)
    assert context.candidate_profile is None
    assert context.profile_version is None
    assert context.hh_resume_link is None


def test_select_creates_linkage_and_survives_reload() -> None:
    database = create_test_database()
    with database.session() as session:
        context = set_hh_resume_link(
            session,
            HhResumeLinkUpdate(
                external_resume_id="resumehash01",
                title="Product Manager",
            ),
        )
        assert context.candidate_profile is not None
        assert context.profile_version is not None
        assert context.profile_version.label == "r1-default"
        assert context.hh_resume_link is not None
        assert context.hh_resume_link.source == "hh"
        assert context.hh_resume_link.external_resume_id == "resumehash01"
        assert context.hh_resume_link.status == HhResumeLinkStatus.ACTIVE
        profile_id = context.candidate_profile.id
        version_id = context.profile_version.id

    with database.session() as session:
        restored = get_candidate_context(session)
        assert restored.candidate_profile is not None
        assert restored.candidate_profile.id == profile_id
        assert restored.profile_version is not None
        assert restored.profile_version.id == version_id
        assert restored.hh_resume_link is not None
        assert restored.hh_resume_link.external_resume_id == "resumehash01"
        assert restored.hh_resume_link.status == HhResumeLinkStatus.ACTIVE


def test_clear_marks_inactive_without_deleting_profile() -> None:
    database = create_test_database()
    with database.session() as session:
        set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id="resumehash01", title="Engineer"),
        )
        cleared = set_hh_resume_link(
            session,
            HhResumeLinkUpdate(external_resume_id=None),
        )
        assert cleared.candidate_profile is not None
        assert cleared.profile_version is not None
        assert cleared.hh_resume_link is not None
        assert cleared.hh_resume_link.status == HhResumeLinkStatus.CLEARED
        assert cleared.hh_resume_link.external_resume_id is None
