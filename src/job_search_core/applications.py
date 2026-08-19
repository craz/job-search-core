"""Transactional application service for idempotent Application create/list."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import Application, Vacancy
from job_search_core.schemas import ApplicationCreate


class ApplicationIdempotencyConflictError(Exception):
    """Signal reuse of one Application key for materially different input."""


class ApplicationAlreadyExistsError(Exception):
    """Signal a duplicate external Application identity under a new key."""


class ApplicationVacancyNotFoundError(Exception):
    """Signal that an Application references no existing Core Vacancy."""


@dataclass(frozen=True)
class CreateApplicationResult:
    """Created or replayed Application plus whether this request inserted it."""

    application: Application
    created: bool


def application_fingerprint(request: ApplicationCreate) -> str:
    """Hash canonical validated input for safe idempotent Application retries."""
    canonical = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_application(
    session: Session, request: ApplicationCreate, idempotency_key: str
) -> CreateApplicationResult:
    """Create one Application or replay an identical idempotent request."""
    fingerprint = application_fingerprint(request)
    existing = session.scalar(
        select(Application)
        .options(joinedload(Application.vacancy))
        .where(Application.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ApplicationIdempotencyConflictError
        return CreateApplicationResult(application=existing, created=False)

    duplicate = session.scalar(
        select(Application).where(
            Application.source == request.source,
            Application.external_id == request.external_id,
        )
    )
    if duplicate is not None:
        raise ApplicationAlreadyExistsError

    vacancy = session.scalar(select(Vacancy).where(Vacancy.id == request.vacancy_id))
    if vacancy is None:
        raise ApplicationVacancyNotFoundError

    application = Application(
        vacancy=vacancy,
        source=request.source,
        external_id=request.external_id,
        applied_at=request.applied_at or datetime.now(UTC),
        resume_version=request.resume_version,
        cover_letter_version=request.cover_letter_version,
        cover_letter_text=request.cover_letter_text,
        result=request.result,
        next_action=request.next_action,
        next_action_at=request.next_action_at,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    session.add(application)
    session.flush()
    return CreateApplicationResult(application=application, created=True)


def list_applications(session: Session) -> list[Application]:
    """Return Applications newest first with Vacancy loaded transactionally."""
    return list(
        session.scalars(
            select(Application)
            .options(joinedload(Application.vacancy))
            .order_by(Application.applied_at.desc(), Application.id.desc())
        )
    )
