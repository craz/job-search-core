"""Transactional service for normalized vacancy assessments."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import Assessment, Vacancy
from job_search_core.schemas import AssessmentCreate, AssessmentDetail


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


def _explanation_fields(request: AssessmentCreate) -> tuple[str | None, str | None, str | None]:
    if request.detail is not None:
        return (
            request.detail.reason.strip(),
            request.detail.risk,
            request.detail.action.strip(),
        )
    reason = request.reason.strip() if request.reason else None
    action = request.action.strip() if request.action else None
    return reason, request.risk, action


def _detail_payload(request: AssessmentCreate) -> dict[str, object] | None:
    if request.detail is not None:
        return request.detail.model_dump(mode="json")
    if request.schema_version == 1:
        return None
    if request.reason is None or request.action is None:
        return None
    return AssessmentDetail(
        reason=request.reason,
        risk=request.risk,
        action=request.action,
    ).model_dump(mode="json")


def _load_existing_by_identity(
    session: Session, scoring_identity_hash: str | None
) -> Assessment | None:
    if not scoring_identity_hash:
        return None
    return session.scalar(
        select(Assessment)
        .options(joinedload(Assessment.vacancy))
        .where(Assessment.scoring_identity_hash == scoring_identity_hash)
    )


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

    identity_match = _load_existing_by_identity(session, request.scoring_identity_hash)
    if identity_match is not None:
        return CreateAssessmentResult(identity_match, False)

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

    reason, risk, action = _explanation_fields(request)
    assessment = Assessment(
        vacancy=vacancy,
        source=request.source,
        external_id=request.external_id,
        relevance_score=request.relevance_score,
        verdict=request.verdict,
        reason=reason,
        risk=risk,
        action=action,
        model=request.model,
        prompt_version=request.prompt_version,
        assessed_at=request.assessed_at,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        vacancy_content_hash=request.vacancy_content_hash,
        profile_version_id=request.profile_version_id,
        resume_version_id=request.resume_version_id,
        candidate_context_hash=request.candidate_context_hash,
        scoring_mode=request.scoring_mode,
        policy_id=request.policy_id,
        policy_version=request.policy_version,
        policy_hash=request.policy_hash,
        model_fingerprint=request.model_fingerprint,
        scoring_identity_hash=request.scoring_identity_hash,
        schema_version=request.schema_version,
        detail=_detail_payload(request),
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
