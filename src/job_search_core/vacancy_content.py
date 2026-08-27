"""Canonical vacancy source-content normalization and hashing (R2.2.3)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

VACANCY_CONTENT_SCHEMA_VERSION = 1

# Source-owned fields that participate in content_hash.
# Excludes: Core UUID, Vacancy.status, Applications/Assessments/People,
# idempotency_key, request_fingerprint, created_at/updated_at, first_seen_at,
# last_seen_at, company display name (Company.name is refreshed separately
# when employer id is stable). source_published_at is source-owned when supplied.
_HASH_FIELDS = (
    "schema_version",
    "source",
    "external_id",
    "company_external_id",
    "title",
    "url",
    "description",
    "salary_text",
    "area_text",
    "employment_text",
    "schedule_text",
    "work_format_text",
    "experience_text",
    "published_text",
    "source_published_at",
    "archived",
)


class VacancyContentValidationError(Exception):
    """Ingest payload is incomplete or not allowlist-compatible."""


def _clean_str(value: object, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return None
    if max_length is not None and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def canonicalize_vacancy_content(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the stable source-owned dict used for hashing and persistence."""
    source = _clean_str(raw.get("source"), max_length=64)
    external_id = _clean_str(raw.get("external_id"), max_length=255)
    company_external_id = _clean_str(raw.get("company_external_id"), max_length=255)
    title = _clean_str(raw.get("title"), max_length=500)
    url = _clean_str(raw.get("url"), max_length=2048)
    if not source or not external_id or not company_external_id or not title or not url:
        raise VacancyContentValidationError("incomplete_vacancy_content")

    archived_raw = raw.get("archived")
    archived: bool | None
    if archived_raw is None:
        archived = None
    elif isinstance(archived_raw, bool):
        archived = archived_raw
    else:
        archived = None

    source_published_at_raw = raw.get("source_published_at")
    source_published_at: str | None = None
    if isinstance(source_published_at_raw, datetime):
        source_published_at = source_published_at_raw.isoformat()
    elif isinstance(source_published_at_raw, str):
        cleaned = source_published_at_raw.strip()
        if cleaned:
            source_published_at = cleaned

    canonical: dict[str, Any] = {
        "schema_version": VACANCY_CONTENT_SCHEMA_VERSION,
        "source": source,
        "external_id": external_id,
        "company_external_id": company_external_id,
        "title": title,
        "url": url,
        "description": _clean_str(raw.get("description")),
        "salary_text": _clean_str(raw.get("salary_text"), max_length=500),
        "area_text": _clean_str(raw.get("area_text"), max_length=500),
        "employment_text": _clean_str(raw.get("employment_text"), max_length=255),
        "schedule_text": _clean_str(raw.get("schedule_text"), max_length=255),
        "work_format_text": _clean_str(raw.get("work_format_text"), max_length=255),
        "experience_text": _clean_str(raw.get("experience_text"), max_length=255),
        "published_text": _clean_str(raw.get("published_text"), max_length=255),
        "source_published_at": source_published_at,
        "archived": archived,
    }
    return canonical


def content_hash(canonical: dict[str, Any]) -> str:
    """SHA-256 over deterministic JSON of source-owned fields only."""
    payload = {key: canonical.get(key) for key in _HASH_FIELDS}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def hash_vacancy_payload(raw: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Canonicalize then hash; returns (canonical, digest)."""
    canonical = canonicalize_vacancy_content(raw)
    return canonical, content_hash(canonical)
