"""Transactional service for confirmed professional contacts."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import Company, Person, PersonStatus, Vacancy
from job_search_core.schemas import PersonCreate


class PersonIdempotencyConflictError(Exception):
    """Signal reuse of a Person key for materially different input."""


class PersonAlreadyExistsError(Exception):
    """Signal a duplicate external Person identity under a new key."""


class PersonCompanyNotFoundError(Exception):
    """Signal a Person referencing no existing Core Company."""


class PersonVacancyNotFoundError(Exception):
    """Signal a Person referencing no existing Core Vacancy."""


class PersonCompanyMismatchError(Exception):
    """Signal a Vacancy that belongs to a different Company."""


class PersonNotFoundError(Exception):
    """Signal a missing Person for status changes."""


@dataclass(frozen=True)
class CreatePersonResult:
    """Created or replayed Person plus whether this request inserted it."""

    person: Person
    created: bool


def person_fingerprint(request: PersonCreate) -> str:
    """Hash canonical validated contact input for retry comparison."""
    encoded = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_person(
    session: Session, request: PersonCreate, idempotency_key: str
) -> CreatePersonResult:
    """Persist one confirmed contact or safely replay identical input."""
    fingerprint = person_fingerprint(request)
    existing = session.scalar(
        select(Person)
        .options(joinedload(Person.company), joinedload(Person.vacancy))
        .where(Person.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise PersonIdempotencyConflictError
        return CreatePersonResult(existing, False)
    duplicate = session.scalar(
        select(Person).where(
            Person.source == request.source, Person.external_id == request.external_id
        )
    )
    if duplicate is not None:
        raise PersonAlreadyExistsError
    company = session.get(Company, request.company_id)
    if company is None:
        raise PersonCompanyNotFoundError
    vacancy = session.get(Vacancy, request.vacancy_id) if request.vacancy_id else None
    if request.vacancy_id and vacancy is None:
        raise PersonVacancyNotFoundError
    if vacancy is not None and vacancy.company_id != company.id:
        raise PersonCompanyMismatchError
    person = Person(
        company=company,
        vacancy=vacancy,
        source=request.source,
        external_id=request.external_id,
        full_name=request.full_name.strip(),
        role=request.role,
        title=request.title,
        url=str(request.url) if request.url else None,
        confidence=request.confidence,
        notes=request.notes,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    session.add(person)
    session.flush()
    return CreatePersonResult(person, True)


def list_people(session: Session) -> list[Person]:
    """Return confirmed contacts newest first with related identities loaded."""
    return list(
        session.scalars(
            select(Person)
            .options(joinedload(Person.company), joinedload(Person.vacancy))
            .order_by(Person.created_at.desc(), Person.id.desc())
        )
    )


def update_person_status(session: Session, person_id: uuid.UUID, status: PersonStatus) -> Person:
    """Change one controlled contact-workflow state without external messaging."""
    person = session.scalar(
        select(Person)
        .options(joinedload(Person.company), joinedload(Person.vacancy))
        .where(Person.id == person_id)
    )
    if person is None:
        raise PersonNotFoundError
    person.status = status
    session.flush()
    return person
