"""Transactional service for measurable job-search hypotheses."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_search_core.models import Hypothesis, HypothesisStatus
from job_search_core.schemas import HypothesisCreate


class HypothesisIdempotencyConflictError(Exception):
    """Signal reuse of a Hypothesis key for different input."""


class HypothesisAlreadyExistsError(Exception):
    """Signal a duplicate external experiment identity under a new key."""


class HypothesisNotFoundError(Exception):
    """Signal an unknown experiment requested for closing."""


class HypothesisAlreadyClosedError(Exception):
    """Signal an attempt to replace the recorded result of a closed experiment."""


@dataclass(frozen=True)
class CreateHypothesisResult:
    """Created or replayed experiment plus whether this call inserted it."""

    hypothesis: Hypothesis
    created: bool


def hypothesis_fingerprint(request: HypothesisCreate) -> str:
    """Hash canonical validated experiment input for retry comparison."""
    encoded = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_hypothesis(
    session: Session, request: HypothesisCreate, idempotency_key: str
) -> CreateHypothesisResult:
    """Persist one active measurable experiment or safely replay identical input."""
    fingerprint = hypothesis_fingerprint(request)
    existing = session.scalar(
        select(Hypothesis).where(Hypothesis.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise HypothesisIdempotencyConflictError
        return CreateHypothesisResult(existing, False)
    duplicate = session.scalar(
        select(Hypothesis).where(
            Hypothesis.source == request.source,
            Hypothesis.external_id == request.external_id,
        )
    )
    if duplicate is not None:
        raise HypothesisAlreadyExistsError
    hypothesis = Hypothesis(
        source=request.source,
        external_id=request.external_id,
        title=request.title.strip(),
        description=request.description,
        test_size=request.test_size,
        metric=request.metric,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    session.add(hypothesis)
    session.flush()
    return CreateHypothesisResult(hypothesis, True)


def list_hypotheses(session: Session, status: HypothesisStatus | None = None) -> list[Hypothesis]:
    """Return experiments newest first, optionally filtered by lifecycle state."""
    statement = select(Hypothesis)
    if status is not None:
        statement = statement.where(Hypothesis.status == status)
    return list(session.scalars(statement.order_by(Hypothesis.created_at.desc())))


def close_hypothesis(session: Session, hypothesis_id: uuid.UUID, result: str) -> Hypothesis:
    """Close one active experiment while preserving its first observed result."""
    hypothesis = session.get(Hypothesis, hypothesis_id)
    if hypothesis is None:
        raise HypothesisNotFoundError
    if hypothesis.status == HypothesisStatus.DONE:
        if hypothesis.result != result.strip():
            raise HypothesisAlreadyClosedError
        return hypothesis
    hypothesis.status = HypothesisStatus.DONE
    hypothesis.result = result.strip()
    session.flush()
    return hypothesis
