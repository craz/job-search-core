"""Unit tests for Application application-service invariants."""

import uuid

import pytest
from tests.support import application_payload, create_test_database

from job_search_core.applications import (
    ApplicationIdempotencyConflictError,
    ApplicationVacancyNotFoundError,
    application_fingerprint,
    create_application,
)
from job_search_core.models import Company, Vacancy
from job_search_core.schemas import ApplicationCreate


def request(vacancy_id: uuid.UUID, *, external_id: str = "application-100") -> ApplicationCreate:
    """Build validated synthetic Application input."""
    payload = application_payload(vacancy_id)
    payload["external_id"] = external_id
    return ApplicationCreate.model_validate(payload)


def test_fingerprint_and_idempotent_replay() -> None:
    """Equivalent requests replay while changed input under one key conflicts."""
    database = create_test_database()
    with database.session() as session:
        company = Company(name="Example Labs", source="fixture", external_id="company-app")
        vacancy = Vacancy(
            company=company,
            source="fixture",
            external_id="vacancy-app",
            title="Application Engineer",
            url="https://example.com/vacancy-app",
            idempotency_key="vacancy-app-key",
            request_fingerprint="fixture",
        )
        session.add(vacancy)
        session.flush()
        initial = request(vacancy.id)
        assert application_fingerprint(initial) == application_fingerprint(initial)
        first = create_application(session, initial, "application-key")
        replay = create_application(session, initial, "application-key")

        assert first.created is True
        assert replay.created is False
        assert first.application.id == replay.application.id
        with pytest.raises(ApplicationIdempotencyConflictError):
            create_application(
                session, request(vacancy.id, external_id="application-changed"), "application-key"
            )


def test_unknown_vacancy_is_rejected() -> None:
    """Core cannot create an orphan Application."""
    database = create_test_database()
    with database.session() as session, pytest.raises(ApplicationVacancyNotFoundError):
        create_application(session, request(uuid.uuid4()), "missing-vacancy-key")
