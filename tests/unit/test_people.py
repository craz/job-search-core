"""Unit coverage for confirmed Person invariants."""

import uuid

import pytest
from sqlalchemy.orm import Session
from tests.support import create_test_database, person_payload

from job_search_core.models import Company, PersonStatus, Vacancy
from job_search_core.people import (
    PersonCompanyMismatchError,
    PersonIdempotencyConflictError,
    PersonNotFoundError,
    create_person,
    list_people,
    update_person_status,
)
from job_search_core.schemas import PersonCreate


def company_and_vacancy(session: Session) -> tuple[Company, Vacancy]:
    """Persist one synthetic Company/Vacancy pair for Person tests."""
    company = Company(name="Example Labs", source="fixture", external_id=str(uuid.uuid4()))
    vacancy = Vacancy(
        company=company,
        source="fixture",
        external_id=str(uuid.uuid4()),
        title="People Engineer",
        url="https://example.com/vacancy",
        idempotency_key=str(uuid.uuid4()),
        request_fingerprint="fixture",
    )
    session.add(vacancy)
    session.flush()
    return company, vacancy


def test_create_replay_list_and_status_are_local() -> None:
    """Identical retry stores one confirmed contact and status changes locally."""
    database = create_test_database()
    with database.session() as session:
        company, vacancy = company_and_vacancy(session)
        request = PersonCreate.model_validate(person_payload(company.id, vacancy.id))
        first = create_person(session, request, "person-key")
        replay = create_person(session, request, "person-key")
        updated = update_person_status(session, first.person.id, PersonStatus.CONTACTED)

        assert first.created is True
        assert replay.created is False
        assert first.person.id == replay.person.id
        assert updated.status == PersonStatus.CONTACTED
        assert len(list_people(session)) == 1
        with pytest.raises(PersonIdempotencyConflictError):
            create_person(
                session,
                request.model_copy(update={"full_name": "Changed Example"}),
                "person-key",
            )


def test_vacancy_company_mismatch_and_missing_person_are_explicit() -> None:
    """Cross-company links and unknown status targets fail before persistence."""
    database = create_test_database()
    with database.session() as session:
        company, _ = company_and_vacancy(session)
        _, other_vacancy = company_and_vacancy(session)
        request = PersonCreate.model_validate(person_payload(company.id, other_vacancy.id))
        with pytest.raises(PersonCompanyMismatchError):
            create_person(session, request, "mismatch")
        with pytest.raises(PersonNotFoundError):
            update_person_status(session, uuid.uuid4(), PersonStatus.REPLIED)
