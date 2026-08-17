"""Unit tests for Vacancy application-service invariants."""

import pytest
from tests.support import create_test_database, vacancy_payload

from job_search_core.schemas import VacancyCreate
from job_search_core.vacancies import (
    IdempotencyConflictError,
    create_vacancy,
    request_fingerprint,
)


def request(*, title: str = "Backend Engineer") -> VacancyCreate:
    """Build validated synthetic input for application-service tests."""
    return VacancyCreate.model_validate(vacancy_payload(title=title))


def test_request_fingerprint_is_stable_for_validated_input() -> None:
    """Equivalent requests must produce one stable idempotency fingerprint."""
    assert request_fingerprint(request()) == request_fingerprint(request())


def test_idempotency_replays_same_vacancy_and_rejects_changed_input() -> None:
    """The service replays identical requests but rejects semantic key reuse."""
    database = create_test_database()
    with database.session() as session:
        first = create_vacancy(session, request(), "unit-key")
        replay = create_vacancy(session, request(), "unit-key")

        assert first.created is True
        assert replay.created is False
        assert first.vacancy.id == replay.vacancy.id
        with pytest.raises(IdempotencyConflictError):
            create_vacancy(session, request(title="Different role"), "unit-key")
