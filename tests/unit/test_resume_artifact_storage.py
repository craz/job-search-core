"""Unit tests for auxiliary resume artifact storage."""

from __future__ import annotations

import pytest

from job_search_core.resume_artifact_storage import (
    ResumeArtifactStorageError,
    read_blob,
    resolve_blob_path,
    storage_key_for_digest,
    write_blob,
)


def test_storage_key_and_path_traversal_blocked(tmp_path) -> None:
    digest = "a" * 64
    key = storage_key_for_digest(digest)
    assert key == f"aa/{'a' * 64}"
    with pytest.raises(ResumeArtifactStorageError):
        resolve_blob_path(tmp_path, "../escape")


def test_write_blob_dedupes_identical_bytes(tmp_path) -> None:
    data = b"%PDF-1.4 sample resume"
    first_key, first_created = write_blob(tmp_path, data)
    second_key, second_created = write_blob(tmp_path, data)
    assert first_key == second_key
    assert first_created is True
    assert second_created is False
    assert read_blob(tmp_path, first_key) == data
