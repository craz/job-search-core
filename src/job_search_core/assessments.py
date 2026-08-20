"""Transactional service for normalized vacancy assessments."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import Assessment, Vacancy
from job_search_core.schemas import AssessmentCreate


class AssessmentIdempotencyConflictError(Exception):
    """Signal reuse of an Assessment key for different normalized input."""


class AssessmentAlreadyExistsError(Exception):
    """Signal a duplicate external Assessment identity under a new key."""


class AssessmentVacancyNotFoundError(Exception):
    """Signal an Assessment referencing no existing Core Vacancy."""


@dataclass(frozen=True)
class CreateAssessmentResult:
    """Created or replayed Assessment plus whether this call inserted it."""

    assessment: Assessment
    created: bool


def assessment_fingerprint(request: AssessmentCreate) -> str:
    """Hash canonical normalized scoring input for retry comparison."""
    encoded = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_assessment(
    session: Session, request: AssessmentCreate, idempotency_key: str
) -> CreateAssessmentResult:
    """Persist a normalized result without retaining raw model output."""
    fingerprint = assessment_fingerprint(request)
    existing = session.scalar(
        select(Assessment)
        .options(joinedload(Assessment.vacancy))
        .where(Assessment.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise AssessmentIdempotencyConflictError
        return CreateAssessmentResult(existing, False)
    duplicate = session.scalar(
        select(Assessment).where(
            Assessment.source == request.source,
            Assessment.external_id == request.external_id,
        )
    )
    if duplicate is not None:
        raise AssessmentAlreadyExistsError
    vacancy = session.get(Vacancy, request.vacancy_id)
    if vacancy is None:
        raise AssessmentVacancyNotFoundError
    assessment = Assessment(
        vacancy=vacancy,
        source=request.source,
        external_id=request.external_id,
        relevance_score=request.relevance_score,
        verdict=request.verdict,
        reason=request.reason.strip(),
        risk=request.risk,
        action=request.action.strip(),
        model=request.model,
        prompt_version=request.prompt_version,
        assessed_at=request.assessed_at,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    session.add(assessment)
    session.flush()
    return CreateAssessmentResult(assessment, True)


def list_assessments(session: Session, vacancy_id: uuid.UUID | None = None) -> list[Assessment]:
    """Return newest normalized results, optionally for one Vacancy."""
    statement = select(Assessment).options(joinedload(Assessment.vacancy))
    if vacancy_id is not None:
        statement = statement.where(Assessment.vacancy_id == vacancy_id)
    return list(session.scalars(statement.order_by(Assessment.assessed_at.desc())))
