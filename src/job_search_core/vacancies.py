"""Transactional application service for creating, listing and updating vacancies."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import Company, Vacancy, VacancyStatus
from job_search_core.schemas import VacancyCreate, VacancyIngest, VacancyIngestOutcome
from job_search_core.vacancy_content import (
    VacancyContentValidationError,
    hash_vacancy_payload,
)


class IdempotencyConflictError(Exception):
    """Signal reuse of one idempotency key for a materially different request."""


class VacancyAlreadyExistsError(Exception):
    """Signal that a source vacancy identity is already owned by another request."""


class VacancyNotFoundError(Exception):
    """Signal that a requested vacancy identifier does not exist."""


class VacancyIngestValidationError(Exception):
    """Signal that an ingest payload failed canonical validation."""


@dataclass(frozen=True)
class CreateResult:
    """Created or replayed vacancy plus whether this request inserted it."""

    vacancy: Vacancy
    created: bool


@dataclass(frozen=True)
class IngestResult:
    """Identity-safe upsert outcome for provider ingestion."""

    vacancy: Vacancy
    outcome: VacancyIngestOutcome


def request_fingerprint(request: VacancyCreate) -> str:
    """Hash canonical validated input to distinguish safe retries from key reuse."""
    payload = request.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _apply_source_fields(vacancy: Vacancy, canonical: dict[str, object], digest: str) -> None:
    vacancy.title = str(canonical["title"])
    vacancy.url = str(canonical["url"])
    vacancy.description = (
        str(canonical["description"]) if canonical.get("description") is not None else None
    )
    vacancy.salary_text = (
        str(canonical["salary_text"]) if canonical.get("salary_text") is not None else None
    )
    vacancy.area_text = (
        str(canonical["area_text"]) if canonical.get("area_text") is not None else None
    )
    vacancy.employment_text = (
        str(canonical["employment_text"]) if canonical.get("employment_text") is not None else None
    )
    vacancy.schedule_text = (
        str(canonical["schedule_text"]) if canonical.get("schedule_text") is not None else None
    )
    vacancy.work_format_text = (
        str(canonical["work_format_text"])
        if canonical.get("work_format_text") is not None
        else None
    )
    vacancy.experience_text = (
        str(canonical["experience_text"]) if canonical.get("experience_text") is not None else None
    )
    vacancy.published_text = (
        str(canonical["published_text"]) if canonical.get("published_text") is not None else None
    )
    archived = canonical.get("archived")
    vacancy.archived = archived if isinstance(archived, bool) else None
    vacancy.content_hash = digest


def _ensure_company(
    session: Session,
    *,
    source: str,
    company_external_id: str,
    company_name: str,
    update_name: bool,
) -> Company:
    """Resolve Company by (source, external_id); optionally refresh source-owned name."""
    company = session.scalar(
        select(Company).where(
            Company.source == source,
            Company.external_id == company_external_id,
        )
    )
    if company is None:
        company = Company(
            name=company_name,
            source=source,
            external_id=company_external_id,
        )
        session.add(company)
        session.flush()
        return company
    if update_name and company.name != company_name:
        company.name = company_name
        session.flush()
    return company


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

    company = _ensure_company(
        session,
        source=request.source,
        company_external_id=request.company_external_id,
        company_name=request.company_name,
        update_name=False,
    )

    try:
        canonical, digest = hash_vacancy_payload(
            {
                **request.model_dump(mode="json"),
                "url": str(request.url),
            }
        )
    except VacancyContentValidationError as error:
        raise VacancyIngestValidationError(str(error)) from error

    vacancy = Vacancy(
        company=company,
        source=str(canonical["source"]),
        external_id=str(canonical["external_id"]),
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    _apply_source_fields(vacancy, canonical, digest)
    session.add(vacancy)
    session.flush()
    return CreateResult(vacancy=vacancy, created=True)


def ingest_vacancy(session: Session, request: VacancyIngest) -> IngestResult:
    """Upsert by (source, external_id) using Core-owned content_hash semantics."""
    try:
        payload = request.model_dump(mode="json")
        payload["url"] = str(request.url)
        canonical, digest = hash_vacancy_payload(payload)
    except VacancyContentValidationError as error:
        raise VacancyIngestValidationError(str(error)) from error

    company_name = " ".join(request.company_name.split()).strip()
    company = _ensure_company(
        session,
        source=str(canonical["source"]),
        company_external_id=str(canonical["company_external_id"]),
        company_name=company_name,
        update_name=True,
    )

    existing = session.scalar(
        select(Vacancy)
        .options(joinedload(Vacancy.company))
        .where(
            Vacancy.source == canonical["source"],
            Vacancy.external_id == canonical["external_id"],
        )
    )
    if existing is None:
        vacancy = Vacancy(
            company=company,
            source=str(canonical["source"]),
            external_id=str(canonical["external_id"]),
            status=VacancyStatus.NEW,
            idempotency_key=None,
            request_fingerprint=None,
        )
        _apply_source_fields(vacancy, canonical, digest)
        session.add(vacancy)
        session.flush()
        session.refresh(vacancy, attribute_names=["company"])
        return IngestResult(vacancy=vacancy, outcome=VacancyIngestOutcome.CREATED)

    if existing.content_hash == digest:
        if existing.company_id != company.id:
            existing.company = company
            session.flush()
        return IngestResult(vacancy=existing, outcome=VacancyIngestOutcome.UNCHANGED)

    prior_status = existing.status
    _apply_source_fields(existing, canonical, digest)
    existing.company = company
    existing.status = prior_status
    session.flush()
    return IngestResult(vacancy=existing, outcome=VacancyIngestOutcome.UPDATED)


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
