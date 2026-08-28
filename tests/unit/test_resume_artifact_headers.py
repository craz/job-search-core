"""Unit tests for resume artifact HTTP helpers."""

from __future__ import annotations

from job_search_core.resume_artifacts import content_disposition_attachment


def test_content_disposition_supports_unicode_filename() -> None:
    header = content_disposition_attachment("Иванов Иван.pdf")
    assert header.startswith('attachment; filename="')
    assert "filename*=UTF-8''" in header
    assert "%D0" in header
