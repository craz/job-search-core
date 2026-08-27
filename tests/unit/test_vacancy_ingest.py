"""Unit tests for vacancy content hashing and identity-safe ingest (R2.2.3)."""

from __future__ import annotations

from tests.support import create_test_database

from job_search_core.models import VacancyStatus
from job_search_core.schemas import VacancyIngest, VacancyIngestOutcome
from job_search_core.vacancies import ingest_vacancy, update_vacancy_status
from job_search_core.vacancy_content import content_hash, hash_vacancy_payload


def _ingest_payload(**overrides: object) -> VacancyIngest:
    base: dict[str, object] = {
        "company_name": "Acme LLC",
        "company_external_id": "42",
        "source": "hh",
        "external_id": "1001",
        "title": "Python Engineer",
        "url": "https://hh.ru/vacancy/1001",
        "description": "Full description for scoring.",
        "salary_text": "от 200 000 ₽",
        "area_text": "Москва",
        "employment_text": "Полная занятость",
        "schedule_text": "График: 5/2",
        "work_format_text": "Формат работы: удалённо",
        "experience_text": "1–3 года",
        "archived": False,
    }
    base.update(overrides)
    return VacancyIngest.model_validate(base)


def test_content_hash_is_deterministic_and_ignores_key_order() -> None:
    left, digest_a = hash_vacancy_payload(
        {
            "source": "hh",
            "external_id": "1",
            "company_external_id": "9",
            "title": "  A  B ",
            "url": "https://hh.ru/vacancy/1",
            "description": "x",
        }
    )
    right, digest_b = hash_vacancy_payload(
        {
            "description": "x",
            "url": "https://hh.ru/vacancy/1",
            "title": "A B",
            "company_external_id": "9",
            "external_id": "1",
            "source": "hh",
        }
    )
    assert left["title"] == "A B"
    assert digest_a == digest_b == content_hash(right)


def test_ingest_created_unchanged_updated_cycle() -> None:
    database = create_test_database()
    with database.session() as session:
        first = ingest_vacancy(session, _ingest_payload())
        assert first.outcome == VacancyIngestOutcome.CREATED
        vacancy_id = first.vacancy.id
        digest = first.vacancy.content_hash

        second = ingest_vacancy(session, _ingest_payload())
        assert second.outcome == VacancyIngestOutcome.UNCHANGED
        assert second.vacancy.id == vacancy_id
        assert second.vacancy.content_hash == digest

        third = ingest_vacancy(
            session, _ingest_payload(description="Changed description for scoring.")
        )
        assert third.outcome == VacancyIngestOutcome.UPDATED
        assert third.vacancy.id == vacancy_id
        assert third.vacancy.content_hash != digest
        assert third.vacancy.description == "Changed description for scoring."

        fourth = ingest_vacancy(
            session, _ingest_payload(description="Changed description for scoring.")
        )
        assert fourth.outcome == VacancyIngestOutcome.UNCHANGED
        assert fourth.vacancy.id == vacancy_id


def test_user_status_preserved_across_source_update() -> None:
    database = create_test_database()
    with database.session() as session:
        created = ingest_vacancy(session, _ingest_payload())
        update_vacancy_status(session, created.vacancy.id, VacancyStatus.REVIEWING)
        updated = ingest_vacancy(session, _ingest_payload(title="Renamed title"))
        assert updated.outcome == VacancyIngestOutcome.UPDATED
        assert updated.vacancy.status == VacancyStatus.REVIEWING
        assert updated.vacancy.title == "Renamed title"


def test_identity_isolation_by_source_and_external_id() -> None:
    database = create_test_database()
    with database.session() as session:
        hh = ingest_vacancy(session, _ingest_payload())
        other_source = ingest_vacancy(session, _ingest_payload(source="other"))
        other_id = ingest_vacancy(
            session, _ingest_payload(external_id="1002", url="https://hh.ru/vacancy/1002")
        )
        assert hh.vacancy.id != other_source.vacancy.id
        assert hh.vacancy.id != other_id.vacancy.id


def test_status_change_does_not_change_content_hash() -> None:
    database = create_test_database()
    with database.session() as session:
        created = ingest_vacancy(session, _ingest_payload())
        digest = created.vacancy.content_hash
        update_vacancy_status(session, created.vacancy.id, VacancyStatus.SHORTLISTED)
        again = ingest_vacancy(session, _ingest_payload())
        assert again.outcome == VacancyIngestOutcome.UNCHANGED
        assert again.vacancy.content_hash == digest
        assert again.vacancy.status == VacancyStatus.SHORTLISTED


def test_archived_source_state_does_not_change_user_status() -> None:
    database = create_test_database()
    with database.session() as session:
        created = ingest_vacancy(session, _ingest_payload())
        update_vacancy_status(session, created.vacancy.id, VacancyStatus.REVIEWING)
        archived = ingest_vacancy(session, _ingest_payload(archived=True))
        assert archived.outcome == VacancyIngestOutcome.UPDATED
        assert archived.vacancy.archived is True
        assert archived.vacancy.status == VacancyStatus.REVIEWING


def test_company_name_refresh_with_stable_employer_id() -> None:
    database = create_test_database()
    with database.session() as session:
        ingest_vacancy(session, _ingest_payload(company_name="Acme"))
        second = ingest_vacancy(session, _ingest_payload(company_name="Acme Renamed"))
        assert second.outcome == VacancyIngestOutcome.UNCHANGED
        assert second.vacancy.company.name == "Acme Renamed"
        assert second.vacancy.company.external_id == "42"
