"""Transactional application service for creating, listing and updating vacancies."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import Company, Vacancy, VacancyStatus
from job_search_core.schemas import VacancyCreate


class IdempotencyConflictError(Exception):
    """Signal reuse of one idempotency key for a materially different request."""


class VacancyAlreadyExistsError(Exception):
    """Signal that a source vacancy identity is already owned by another request."""


class VacancyNotFoundError(Exception):
    """Signal that a requested vacancy identifier does not exist."""


@dataclass(frozen=True)
class CreateResult:
    """Created or replayed vacancy plus whether this request inserted it."""

    vacancy: Vacancy
    created: bool


def request_fingerprint(request: VacancyCreate) -> str:
    """Hash canonical validated input to distinguish safe retries from key reuse."""
    payload = request.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_vacancy(session: Session, request: VacancyCreate, idempotency_key: str) -> CreateResult:
    """Create one normalized vacancy or replay an identical idempotent request."""
    fingerprint = request_fingerprint(request)
    existing = session.scalar(
        select(Vacancy)
        .options(joinedload(Vacancy.company))
        .where(Vacancy.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflictError
        return CreateResult(vacancy=existing, created=False)

    source_match = session.scalar(
        select(Vacancy).where(
            Vacancy.source == request.source,
            Vacancy.external_id == request.external_id,
        )
    )
    if source_match is not None:
        raise VacancyAlreadyExistsError

    company = session.scalar(
        select(Company).where(
            Company.source == request.source,
            Company.external_id == request.company_external_id,
        )
    )
    if company is None:
        company = Company(
            name=request.company_name,
            source=request.source,
            external_id=request.company_external_id,
        )
        session.add(company)

    vacancy = Vacancy(
        company=company,
        source=request.source,
        external_id=request.external_id,
        title=request.title,
        url=str(request.url),
        description=request.description,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    session.add(vacancy)
    session.flush()
    return CreateResult(vacancy=vacancy, created=True)


def list_vacancies(session: Session) -> list[Vacancy]:
    """Return vacancies newest first with companies loaded inside the transaction."""
    return list(
        session.scalars(
            select(Vacancy)
            .options(joinedload(Vacancy.company))
            .order_by(Vacancy.created_at.desc(), Vacancy.id.desc())
        )
    )


def update_vacancy_status(
    session: Session, vacancy_id: uuid.UUID, vacancy_status: VacancyStatus
) -> Vacancy:
    """Set one vacancy status and return the fully loaded persisted representation."""
    vacancy = session.scalar(
        select(Vacancy).options(joinedload(Vacancy.company)).where(Vacancy.id == vacancy_id)
    )
    if vacancy is None:
        raise VacancyNotFoundError
    vacancy.status = vacancy_status
    session.flush()
    return vacancy
