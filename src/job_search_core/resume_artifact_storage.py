"""Local blob storage for auxiliary resume file artifacts (R2.1-CORR-01)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_STORAGE_KEY_RE = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{64}$")


class ResumeArtifactStorageError(Exception):
    """Invalid storage key or artifact bytes."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def storage_key_for_digest(digest: str) -> str:
    if len(digest) != 64 or not all(char in "0123456789abcdef" for char in digest):
        raise ResumeArtifactStorageError("invalid sha256 digest")
    return f"{digest[:2]}/{digest}"


def resolve_blob_path(artifact_root: Path, storage_key: str) -> Path:
    if not _STORAGE_KEY_RE.match(storage_key):
        raise ResumeArtifactStorageError("invalid storage key")
    candidate = (artifact_root / storage_key).resolve()
    root = artifact_root.resolve()
    if root not in candidate.parents and candidate != root:
        raise ResumeArtifactStorageError("path traversal blocked")
    return candidate


def write_blob(artifact_root: Path, data: bytes) -> tuple[str, bool]:
    """Persist bytes under content-addressed key; return (storage_key, created)."""
    if not data:
        raise ResumeArtifactStorageError("empty artifact")
    digest = sha256_hex(data)
    storage_key = storage_key_for_digest(digest)
    target = resolve_blob_path(artifact_root, storage_key)
    if target.is_file():
        return storage_key, False
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(".part")
    temp_path.write_bytes(data)
    temp_path.replace(target)
    return storage_key, True


def read_blob(artifact_root: Path, storage_key: str) -> bytes:
    target = resolve_blob_path(artifact_root, storage_key)
    if not target.is_file():
        raise ResumeArtifactStorageError("artifact blob missing")
    return target.read_bytes()
