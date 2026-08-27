"""Canonical resume snapshot normalization and content hashing (R2.1.1)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

RESUME_SNAPSHOT_SCHEMA_VERSION = 1

_TOP_LEVEL_ALLOWLIST = frozenset(
    {
        "title",
        "desired_position",
        "about",
        "skills",
        "experience",
        "education",
        "languages",
        "salary",
        "location",
        "employment_preferences",
    }
)
_EXPERIENCE_ALLOWLIST = frozenset({"company", "position", "period", "description"})
_EDUCATION_ALLOWLIST = frozenset({"institution", "degree", "year"})
_LANGUAGE_ALLOWLIST = frozenset({"name", "level"})
_SALARY_ALLOWLIST = frozenset({"text", "amount", "currency"})
_PREFERENCES_ALLOWLIST = frozenset({"text"})


class ResumeSnapshotValidationError(Exception):
    """Snapshot payload is empty or not allowlist-compatible."""


def _clean_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _normalize_string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = _clean_str(item)
        if cleaned is None or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out or None


def _normalize_object_list(
    value: object, *, allowlist: frozenset[str], optional_numbers: frozenset[str] | None = None
) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    numbers = optional_numbers or frozenset()
    out: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        item: dict[str, Any] = {}
        for key in sorted(allowlist):
            if key not in raw:
                continue
            if key in numbers:
                num = raw[key]
                if isinstance(num, bool) or not isinstance(num, (int, float)):
                    continue
                item[key] = num
                continue
            cleaned = _clean_str(raw[key])
            if cleaned is not None:
                item[key] = cleaned
        if item:
            out.append(item)
    return out or None


def _normalize_salary(value: object) -> dict[str, Any] | None:
    if isinstance(value, str):
        cleaned = _clean_str(value)
        return {"text": cleaned} if cleaned else None
    if not isinstance(value, dict):
        return None
    item: dict[str, Any] = {}
    for key in sorted(_SALARY_ALLOWLIST):
        if key not in value:
            continue
        if key == "amount":
            num = value[key]
            if isinstance(num, bool) or not isinstance(num, (int, float)):
                continue
            item[key] = num
            continue
        cleaned = _clean_str(value[key])
        if cleaned is not None:
            item[key] = cleaned
    return item or None


def _normalize_preferences(value: object) -> dict[str, Any] | None:
    if isinstance(value, str):
        cleaned = _clean_str(value)
        return {"text": cleaned} if cleaned else None
    if not isinstance(value, dict):
        return None
    item: dict[str, Any] = {}
    for key in sorted(_PREFERENCES_ALLOWLIST):
        if key not in value:
            continue
        cleaned = _clean_str(value[key])
        if cleaned is not None:
            item[key] = cleaned
    return item or None


def canonicalize_resume_content(raw: dict[str, Any]) -> dict[str, Any]:
    """Return allowlisted, trimmed, stable-key snapshot suitable for hashing."""
    if not isinstance(raw, dict):
        raise ResumeSnapshotValidationError("content must be an object")

    normalized: dict[str, Any] = {"schema_version": RESUME_SNAPSHOT_SCHEMA_VERSION}
    for key in sorted(_TOP_LEVEL_ALLOWLIST):
        if key not in raw:
            continue
        value = raw[key]
        if key in {"title", "desired_position", "about", "location"}:
            cleaned = _clean_str(value)
            if cleaned is not None:
                normalized[key] = cleaned
        elif key == "skills":
            skills = _normalize_string_list(value)
            if skills is not None:
                normalized[key] = skills
        elif key == "experience":
            experience = _normalize_object_list(value, allowlist=_EXPERIENCE_ALLOWLIST)
            if experience is not None:
                normalized[key] = experience
        elif key == "education":
            education = _normalize_object_list(value, allowlist=_EDUCATION_ALLOWLIST)
            if education is not None:
                normalized[key] = education
        elif key == "languages":
            languages = _normalize_object_list(value, allowlist=_LANGUAGE_ALLOWLIST)
            if languages is not None:
                normalized[key] = languages
        elif key == "salary":
            salary = _normalize_salary(value)
            if salary is not None:
                normalized[key] = salary
        elif key == "employment_preferences":
            preferences = _normalize_preferences(value)
            if preferences is not None:
                normalized[key] = preferences

    # Only schema_version means empty factual content.
    if len(normalized) == 1:
        raise ResumeSnapshotValidationError("normalized resume content is empty")
    return normalized


def content_hash(canonical: dict[str, Any]) -> str:
    """SHA-256 hex digest of canonical UTF-8 JSON (sorted keys, compact)."""
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
