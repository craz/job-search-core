"""Temporal provenance fields for vacancy ingest (R2.2.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from tests.support import create_test_database

from job_search_core.schemas import VacancyIngest, VacancyIngestOutcome
from job_search_core.vacancies import ingest_vacancy
from job_search_core.vacancy_content import _HASH_FIELDS


def _ingest_payload(**overrides: object) -> VacancyIngest:
    base: dict[str, object] = {
        "company_name": "Acme LLC",
        "company_external_id": "42",
        "source": "hh",
        "external_id": "1001",
        "title": "Python Engineer",
        "url": "https://hh.ru/vacancy/1001",
        "description": "Full description for scoring.",
    }
    base.update(overrides)
    return VacancyIngest.model_validate(base)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def test_created_sets_first_and_last_seen_equal() -> None:
    database = create_test_database()
    fixed = datetime(2026, 8, 28, 20, 15, tzinfo=UTC)
    with (
        patch("job_search_core.vacancies.utc_now", return_value=fixed),
        database.session() as session,
    ):
        result = ingest_vacancy(session, _ingest_payload())
    assert result.outcome == VacancyIngestOutcome.CREATED
    assert _as_utc(result.vacancy.first_seen_at) == fixed
    assert _as_utc(result.vacancy.last_seen_at) == fixed


def test_unchanged_preserves_first_seen_and_advances_last_seen() -> None:
    database = create_test_database()
    t0 = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 28, 21, 0, tzinfo=UTC)
    with patch("job_search_core.vacancies.utc_now", return_value=t0), database.session() as session:
        created = ingest_vacancy(session, _ingest_payload())
        digest = created.vacancy.content_hash
    with patch("job_search_core.vacancies.utc_now", return_value=t1), database.session() as session:
        again = ingest_vacancy(session, _ingest_payload())
    assert again.outcome == VacancyIngestOutcome.UNCHANGED
    assert _as_utc(again.vacancy.first_seen_at) == t0
    assert _as_utc(again.vacancy.last_seen_at) == t1
    assert again.vacancy.content_hash == digest


def test_updated_preserves_first_seen_and_advances_last_seen() -> None:
    database = create_test_database()
    t0 = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 28, 21, 30, tzinfo=UTC)
    with patch("job_search_core.vacancies.utc_now", return_value=t0), database.session() as session:
        ingest_vacancy(session, _ingest_payload())
    with patch("job_search_core.vacancies.utc_now", return_value=t1), database.session() as session:
        updated = ingest_vacancy(
            session, _ingest_payload(description="Changed description for scoring.")
        )
    assert updated.outcome == VacancyIngestOutcome.UPDATED
    assert _as_utc(updated.vacancy.first_seen_at) == t0
    assert _as_utc(updated.vacancy.last_seen_at) == t1


def test_provenance_fields_not_in_content_hash() -> None:
    assert "first_seen_at" not in _HASH_FIELDS
    assert "last_seen_at" not in _HASH_FIELDS
    assert "created_at" not in _HASH_FIELDS
    assert "updated_at" not in _HASH_FIELDS


def test_source_published_at_only_when_supplied() -> None:
    database = create_test_database()
    published = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    with database.session() as session:
        without = ingest_vacancy(session, _ingest_payload())
        with_ts = ingest_vacancy(
            session,
            _ingest_payload(
                external_id="1002",
                url="https://hh.ru/vacancy/1002",
                source_published_at=published,
            ),
        )
    assert without.vacancy.source_published_at is None
    assert _as_utc(with_ts.vacancy.source_published_at) == published
