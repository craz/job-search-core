"""Transactional service for CandidateProfile / ProfileVersion / HH resume link."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import (
    ActiveHhResumeLink,
    CandidateProfile,
    HhResumeLinkStatus,
    ProfileVersion,
    utc_now,
)
from job_search_core.schemas import HhResumeLinkUpdate

OPERATOR_SINGLETON_KEY = "operator"
DEFAULT_VERSION_LABEL = "r1-default"


class HhResumeLinkValidationError(Exception):
    """Signal invalid HH resume link payload."""


@dataclass(frozen=True)
class CandidateContext:
    """Resolved local candidate context for product consumers."""

    candidate_profile: CandidateProfile | None
    profile_version: ProfileVersion | None
    hh_resume_link: ActiveHhResumeLink | None


def get_candidate_context(session: Session) -> CandidateContext:
    """Return current operator context without creating rows on empty install."""
    profile = session.scalar(
        select(CandidateProfile).where(CandidateProfile.singleton_key == OPERATOR_SINGLETON_KEY)
    )
    if profile is None:
        return CandidateContext(None, None, None)
    version = session.scalar(
        select(ProfileVersion)
        .options(joinedload(ProfileVersion.hh_resume_link))
        .where(
            ProfileVersion.candidate_profile_id == profile.id,
            ProfileVersion.label == DEFAULT_VERSION_LABEL,
        )
    )
    link = version.hh_resume_link if version is not None else None
    return CandidateContext(profile, version, link)


def _ensure_profile_version(session: Session) -> tuple[CandidateProfile, ProfileVersion]:
    profile = session.scalar(
        select(CandidateProfile).where(CandidateProfile.singleton_key == OPERATOR_SINGLETON_KEY)
    )
    if profile is None:
        profile = CandidateProfile(singleton_key=OPERATOR_SINGLETON_KEY)
        session.add(profile)
        session.flush()
    version = session.scalar(
        select(ProfileVersion).where(
            ProfileVersion.candidate_profile_id == profile.id,
            ProfileVersion.label == DEFAULT_VERSION_LABEL,
        )
    )
    if version is None:
        version = ProfileVersion(candidate_profile_id=profile.id, label=DEFAULT_VERSION_LABEL)
        session.add(version)
        session.flush()
    return profile, version


def set_hh_resume_link(session: Session, request: HhResumeLinkUpdate) -> CandidateContext:
    """Create/update HH resume linkage for the operator ProfileVersion.

    ``external_resume_id=null`` marks the link cleared without deleting history rows.
    Fresh installs receive CandidateProfile/ProfileVersion only on first write —
    never from legacy_job_search bootstrap.
    """
    if request.external_resume_id is not None:
        external_id = request.external_resume_id.strip()
        if not external_id:
            raise HhResumeLinkValidationError
    else:
        external_id = None

    status = request.status
    if status is None:
        status = HhResumeLinkStatus.ACTIVE if external_id else HhResumeLinkStatus.CLEARED
    if external_id is None and status == HhResumeLinkStatus.ACTIVE:
        raise HhResumeLinkValidationError

    _profile, version = _ensure_profile_version(session)
    link = session.scalar(
        select(ActiveHhResumeLink).where(ActiveHhResumeLink.profile_version_id == version.id)
    )
    now = utc_now()
    if link is None:
        link = ActiveHhResumeLink(
            profile_version_id=version.id,
            source="hh",
            external_resume_id=external_id,
            title=(request.title.strip() if request.title else None),
            selected_at=now if status == HhResumeLinkStatus.ACTIVE else None,
            status=status,
            updated_at=now,
        )
        session.add(link)
    else:
        link.source = "hh"
        link.external_resume_id = external_id
        if request.title is not None:
            link.title = request.title.strip() or None
        elif status == HhResumeLinkStatus.CLEARED:
            pass
        link.status = status
        link.selected_at = now if status == HhResumeLinkStatus.ACTIVE else link.selected_at
        link.updated_at = now
    session.flush()
    session.refresh(link)
    return CandidateContext(_profile, version, link)
