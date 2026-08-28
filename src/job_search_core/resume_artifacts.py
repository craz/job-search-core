"""Resume file artifact persistence (auxiliary local archive, R2.1-CORR-01)."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_search_core.models import ResumeArtifact, ResumeVersion, utc_now
from job_search_core.resume_artifact_storage import (
    ResumeArtifactStorageError,
    read_blob,
    sha256_hex,
    write_blob,
)

_FILENAME_RE = re.compile(r"^[^/\\]+$")
_ASCII_FILENAME_RE = re.compile(r"[^\x20-\x7E]")


def content_disposition_attachment(original_filename: str) -> str:
    """Build RFC 5987 Content-Disposition safe for non-ASCII HH filenames."""
    cleaned = Path(original_filename).name.strip() or "resume"
    ascii_fallback = _ASCII_FILENAME_RE.sub("_", cleaned).strip("._") or "resume"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(cleaned)}"


class ResumeArtifactValidationError(Exception):
    """Invalid artifact ingest request."""


@dataclass(frozen=True)
class ResumeArtifactIngestResult:
    artifact: ResumeArtifact
    created: bool
    blob_created: bool


@dataclass(frozen=True)
class ResumeFileMeta:
    """Public metadata for auxiliary resume file (no scoring semantics)."""

    artifact_id: UUID
    mime_type: str
    original_filename: str
    size_bytes: int
    captured_at: datetime
    format_label: str


def format_label_for_mime(mime_type: str, original_filename: str) -> str:
    lowered = mime_type.lower().strip()
    if lowered == "application/pdf" or original_filename.lower().endswith(".pdf"):
        return "PDF"
    if lowered in {"application/rtf", "text/rtf"} or original_filename.lower().endswith(".rtf"):
        return "RTF"
    if lowered in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    } or original_filename.lower().endswith((".doc", ".docx")):
        return "DOC"
    guessed = mimetypes.guess_extension(lowered, strict=False)
    if guessed:
        return guessed.lstrip(".").upper()
    return "FILE"


def latest_resume_artifact(session: Session, resume_version_id: UUID) -> ResumeArtifact | None:
    return session.scalar(
        select(ResumeArtifact)
        .where(ResumeArtifact.resume_version_id == resume_version_id)
        .order_by(ResumeArtifact.captured_at.desc(), ResumeArtifact.id.desc())
        .limit(1)
    )


def get_resume_artifact(session: Session, artifact_id: UUID) -> ResumeArtifact | None:
    return session.get(ResumeArtifact, artifact_id)


def resume_file_meta(session: Session, resume_version_id: UUID | None) -> ResumeFileMeta | None:
    if resume_version_id is None:
        return None
    row = latest_resume_artifact(session, resume_version_id)
    if row is None:
        return None
    return ResumeFileMeta(
        artifact_id=row.id,
        mime_type=row.mime_type,
        original_filename=row.original_filename,
        size_bytes=row.size_bytes,
        captured_at=row.captured_at,
        format_label=format_label_for_mime(row.mime_type, row.original_filename),
    )


def ingest_resume_artifact(
    session: Session,
    *,
    artifact_root: Path,
    resume_version_id: UUID,
    data: bytes,
    mime_type: str,
    original_filename: str,
    source: str = "hh",
    captured_at: datetime | None = None,
) -> ResumeArtifactIngestResult:
    """Attach downloaded bytes to an existing ResumeVersion without changing its identity."""
    version = session.get(ResumeVersion, resume_version_id)
    if version is None:
        raise ResumeArtifactValidationError("resume_version not found")
    if source != "hh":
        raise ResumeArtifactValidationError("unsupported source")
    cleaned_name = original_filename.strip()
    if not cleaned_name or not _FILENAME_RE.match(cleaned_name):
        raise ResumeArtifactValidationError("invalid original_filename")
    cleaned_mime = mime_type.strip().lower()
    if not cleaned_mime or "/" not in cleaned_mime:
        raise ResumeArtifactValidationError("invalid mime_type")
    if not data:
        raise ResumeArtifactValidationError("empty artifact bytes")

    digest = sha256_hex(data)
    existing = session.scalar(
        select(ResumeArtifact).where(
            ResumeArtifact.resume_version_id == resume_version_id,
            ResumeArtifact.sha256 == digest,
        )
    )
    if existing is not None:
        return ResumeArtifactIngestResult(existing, created=False, blob_created=False)

    storage_key, blob_created = write_blob(artifact_root, data)
    captured = captured_at or utc_now()
    if captured.tzinfo is None:
        raise ResumeArtifactValidationError("captured_at must be timezone-aware")

    row = ResumeArtifact(
        resume_version_id=resume_version_id,
        source=source,
        sha256=digest,
        storage_key=storage_key,
        mime_type=cleaned_mime,
        original_filename=cleaned_name,
        size_bytes=len(data),
        captured_at=captured,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return ResumeArtifactIngestResult(row, created=True, blob_created=blob_created)


def load_resume_artifact_bytes(artifact_root: Path, artifact: ResumeArtifact) -> bytes:
    try:
        return read_blob(artifact_root, artifact.storage_key)
    except ResumeArtifactStorageError as error:
        raise ResumeArtifactValidationError(str(error)) from error
