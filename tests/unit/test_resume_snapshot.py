"""Unit tests for resume snapshot canonicalization and hashing."""

from __future__ import annotations

import pytest

from job_search_core.resume_snapshot import (
    ResumeSnapshotValidationError,
    canonicalize_resume_content,
    content_hash,
)


def test_canonicalize_allowlist_and_strip_pii_keys() -> None:
    raw = {
        "title": "  Product Manager  ",
        "phone": "+70000000000",
        "email": "secret@example.test",
        "contacts": {"phone": "x"},
        "about": "Summary text",
        "skills": [" Python ", "Python", "", "SQL"],
        "experience": [
            {
                "company": "Acme",
                "position": "PM",
                "period": "2020—2022",
                "description": "Led delivery",
                "phone": "drop-me",
            }
        ],
        "garbage": "ignored",
    }
    canonical = canonicalize_resume_content(raw)
    assert canonical["schema_version"] == 1
    assert canonical["title"] == "Product Manager"
    assert canonical["about"] == "Summary text"
    assert canonical["skills"] == ["Python", "SQL"]
    assert canonical["experience"] == [
        {
            "company": "Acme",
            "description": "Led delivery",
            "period": "2020—2022",
            "position": "PM",
        }
    ]
    assert "phone" not in canonical
    assert "email" not in canonical
    assert "contacts" not in canonical
    assert "garbage" not in canonical


def test_hash_stable_for_equivalent_payloads() -> None:
    a = canonicalize_resume_content({"title": "A", "skills": ["x", "y"]})
    b = canonicalize_resume_content({"skills": ["x", "y"], "title": "A", "email": "n@e.test"})
    assert content_hash(a) == content_hash(b)


def test_hash_changes_when_content_changes() -> None:
    a = canonicalize_resume_content({"title": "A"})
    b = canonicalize_resume_content({"title": "B"})
    assert content_hash(a) != content_hash(b)


def test_empty_content_rejected() -> None:
    with pytest.raises(ResumeSnapshotValidationError):
        canonicalize_resume_content({"phone": "1", "email": "a@b.c"})
