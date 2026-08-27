"""Immutable ResumeVersion ingest and lookup (R2.1.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_search_core.candidate_context import (
    CandidateContext,
    _ensure_profile_version,
    get_candidate_context,
)
from job_search_core.models import HhResumeLinkStatus, ResumeVersion, utc_now
from job_search_core.resume_snapshot import (
    RESUME_SNAPSHOT_SCHEMA_VERSION,
    ResumeSnapshotValidationError,
    canonicalize_resume_content,
    content_hash,
)
from job_search_core.schemas import ResumeVersionIngest

ALLOWED_SOURCES = frozenset({"hh"})
ALLOWED_TRANSPORTS = frozenset({"browser_readonly", "fixture"})


class ResumeVersionValidationError(Exception):
    """Invalid ResumeVersion ingest payload."""


@dataclass(frozen=True)
class ResumeVersionIngestResult:
    """Outcome of ingest: created new row or reused identical latest."""

    resume_version: ResumeVersion
    created: bool
    candidate_context: CandidateContext


@dataclass(frozen=True)
class ResumeContentMeta:
    """Public metadata for candidate-context (no CV body)."""

    content_state: str
    resume_version_id: UUID | None
    external_resume_id: str | None
    captured_at: datetime | None
    source: str | None = None
    schema_version: int | None = None


def latest_resume_version(
    session: Session,
    *,
    profile_version_id: UUID,
    source: str,
    external_resume_id: str,
) -> ResumeVersion | None:
    """Return newest ResumeVersion for one HH resume id under a ProfileVersion."""
    return session.scalar(
        select(ResumeVersion)
        .where(
            ResumeVersion.profile_version_id == profile_version_id,
            ResumeVersion.source == source,
            ResumeVersion.external_resume_id == external_resume_id,
        )
        .order_by(ResumeVersion.captured_at.desc(), ResumeVersion.id.desc())
        .limit(1)
    )


def get_resume_version(session: Session, resume_version_id: UUID) -> ResumeVersion | None:
    """Load one ResumeVersion by id."""
    return session.get(ResumeVersion, resume_version_id)


def resume_content_meta(session: Session, context: CandidateContext) -> ResumeContentMeta | None:
    """Derive current local resume content metadata from active link + latest version.

    No separate pointer table: current = active HH link + latest ResumeVersion
    for that external_resume_id.
    """
    link = context.hh_resume_link
    version = context.profile_version
    if link is None or version is None:
        return None
    if link.status != HhResumeLinkStatus.ACTIVE or not link.external_resume_id:
        return ResumeContentMeta(
            content_state="not_synced",
            resume_version_id=None,
            external_resume_id=None,
            captured_at=None,
        )
    latest = latest_resume_version(
        session,
        profile_version_id=version.id,
        source=link.source or "hh",
        external_resume_id=link.external_resume_id,
    )
    if latest is None:
        return ResumeContentMeta(
            content_state="not_synced",
            resume_version_id=None,
            external_resume_id=link.external_resume_id,
            captured_at=None,
            source=link.source,
        )
    return ResumeContentMeta(
        content_state="synced",
        resume_version_id=latest.id,
        external_resume_id=latest.external_resume_id,
        captured_at=latest.captured_at,
        source=latest.source,
        schema_version=latest.schema_version,
    )


def ingest_resume_version(
    session: Session, request: ResumeVersionIngest
) -> ResumeVersionIngestResult:
    """Insert immutable ResumeVersion or reuse latest when content_hash matches.

    Never updates an existing row's content. Empty/fake snapshots are rejected.
    """
    source = (request.source or "").strip()
    if source not in ALLOWED_SOURCES:
        raise ResumeVersionValidationError("unsupported source")
    external_id = (request.external_resume_id or "").strip()
    if not external_id:
        raise ResumeVersionValidationError("external_resume_id required")
    transport = (request.transport or "browser_readonly").strip()
    if transport not in ALLOWED_TRANSPORTS:
        raise ResumeVersionValidationError("unsupported transport")
    if not isinstance(request.content, dict):
        raise ResumeVersionValidationError("content must be an object")

    try:
        canonical = canonicalize_resume_content(request.content)
    except ResumeSnapshotValidationError as error:
        raise ResumeVersionValidationError(str(error)) from error

    digest = content_hash(canonical)
    _profile, profile_version = _ensure_profile_version(session)

    latest = latest_resume_version(
        session,
        profile_version_id=profile_version.id,
        source=source,
        external_resume_id=external_id,
    )
    if latest is not None and latest.content_hash == digest:
        context = get_candidate_context(session)
        return ResumeVersionIngestResult(
            resume_version=latest,
            created=False,
            candidate_context=context,
        )

    captured_at = request.captured_at or utc_now()
    if captured_at.tzinfo is None:
        raise ResumeVersionValidationError("captured_at must be timezone-aware")

    extractor = request.extractor_version.strip() if request.extractor_version else None
    row = ResumeVersion(
        profile_version_id=profile_version.id,
        source=source,
        external_resume_id=external_id,
        schema_version=RESUME_SNAPSHOT_SCHEMA_VERSION,
        content_hash=digest,
        content=canonical,
        captured_at=captured_at,
        transport=transport,
        extractor_version=extractor,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    context = get_candidate_context(session)
    return ResumeVersionIngestResult(
        resume_version=row,
        created=True,
        candidate_context=context,
    )
