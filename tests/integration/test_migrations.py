"""Integration checks for the executable Alembic migration chain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import bindparam, create_engine, inspect, text
from sqlalchemy.types import Uuid as UuidType
from tests.support import (
    ApiClient,
    assessment_payload,
    assessment_v1_payload,
    create_fixture_vacancy,
)

from job_search_core.assessments import create_assessment
from job_search_core.database import Database
from job_search_core.schemas import AssessmentCreate, AssessmentRead

LEGACY_COMPANY_ID = uuid.UUID("cccccccc-ccc1-4cc1-8cc1-ccccccccccc1")
LEGACY_VACANCY_ID = uuid.UUID("bbbbbbbb-bbb1-4bb1-8bb1-bbbbbbbbbbb1")
LEGACY_ASSESSMENT_ID = uuid.UUID("aaaaaaaa-aaa1-4aa1-8aa1-aaaaaaaaaaa1")
LEGACY_TIMESTAMP = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
LEGACY_TIMESTAMP_TEXT = LEGACY_TIMESTAMP.isoformat()


def test_migration_upgrades_an_empty_database(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """A clean database receives all Core-owned tables through Alembic only."""
    database_path = tmp_path / "core.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("JOB_SEARCH_CORE_DATABASE_URL", database_url)
    configuration = Config("alembic.ini")

    command.upgrade(configuration, "head")

    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert {
        "alembic_version",
        "companies",
        "vacancies",
        "applications",
        "daily_metrics",
        "daily_metric_requests",
        "people",
        "hypotheses",
        "assessments",
        "candidate_profiles",
        "profile_versions",
        "active_hh_resume_links",
        "resume_versions",
        "search_profiles",
        "search_runs",
        "search_run_items",
    } <= tables


def test_migration_preserves_legacy_assessment_and_enables_v1(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Upgrade from 20260828_13 with populated legacy rows, then enable v1 identity."""
    database_path = tmp_path / "legacy_core.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("JOB_SEARCH_CORE_DATABASE_URL", database_url)
    configuration = Config("alembic.ini")

    command.upgrade(configuration, "20260828_13")

    engine = create_engine(database_url)
    company_insert = text(
        """
        INSERT INTO companies (id, name, source, external_id, created_at)
        VALUES (:id, :name, :source, :external_id, :created_at)
        """
    ).bindparams(bindparam("id", type_=UuidType(as_uuid=True)))
    vacancy_insert = text(
        """
        INSERT INTO vacancies (
            id, company_id, source, external_id, title, url, description,
            status, created_at, updated_at, first_seen_at, last_seen_at
        ) VALUES (
            :id, :company_id, :source, :external_id, :title, :url, :description,
            :status, :created_at, :updated_at, :first_seen_at, :last_seen_at
        )
        """
    ).bindparams(
        bindparam("id", type_=UuidType(as_uuid=True)),
        bindparam("company_id", type_=UuidType(as_uuid=True)),
    )
    assessment_insert = text(
        """
        INSERT INTO assessments (
            id, vacancy_id, source, external_id, relevance_score, verdict,
            reason, risk, action, model, prompt_version, assessed_at,
            idempotency_key, request_fingerprint, created_at
        ) VALUES (
            :id, :vacancy_id, :source, :external_id, :relevance_score, :verdict,
            :reason, :risk, :action, :model, :prompt_version, :assessed_at,
            :idempotency_key, :request_fingerprint, :created_at
        )
        """
    ).bindparams(
        bindparam("id", type_=UuidType(as_uuid=True)),
        bindparam("vacancy_id", type_=UuidType(as_uuid=True)),
    )
    with engine.begin() as connection:
        connection.execute(
            company_insert,
            {
                "id": LEGACY_COMPANY_ID,
                "name": "Legacy Labs",
                "source": "fixture",
                "external_id": "company-legacy",
                "created_at": LEGACY_TIMESTAMP_TEXT,
            },
        )
        connection.execute(
            vacancy_insert,
            {
                "id": LEGACY_VACANCY_ID,
                "company_id": LEGACY_COMPANY_ID,
                "source": "fixture",
                "external_id": "vacancy-legacy",
                "title": "Legacy Backend Role",
                "url": "https://example.com/vacancies/legacy",
                "description": "Pre-R2.3.1 vacancy fixture",
                "status": "new",
                "created_at": LEGACY_TIMESTAMP_TEXT,
                "updated_at": LEGACY_TIMESTAMP_TEXT,
                "first_seen_at": LEGACY_TIMESTAMP_TEXT,
                "last_seen_at": LEGACY_TIMESTAMP_TEXT,
            },
        )
        connection.execute(
            assessment_insert,
            {
                "id": LEGACY_ASSESSMENT_ID,
                "vacancy_id": LEGACY_VACANCY_ID,
                "source": "fixture",
                "external_id": "assessment-legacy",
                "relevance_score": 77,
                "verdict": "apply",
                "reason": "Legacy strong match",
                "risk": "Limited context",
                "action": "Apply with tailored CV",
                "model": "legacy-model",
                "prompt_version": "legacy-v0",
                "assessed_at": LEGACY_TIMESTAMP_TEXT,
                "idempotency_key": "legacy-assessment-key",
                "request_fingerprint": "legacy-fingerprint",
                "created_at": LEGACY_TIMESTAMP_TEXT,
            },
        )

    command.upgrade(configuration, "head")

    with engine.connect() as connection:
        legacy = connection.execute(
            text(
                """
                SELECT reason, action, schema_version, scoring_identity_hash,
                       vacancy_content_hash, candidate_context_hash, detail
                FROM assessments
                WHERE source = :source AND external_id = :external_id
                """
            ),
            {"source": "fixture", "external_id": "assessment-legacy"},
        ).one()
        assert legacy.reason == "Legacy strong match"
        assert legacy.action == "Apply with tailored CV"
        assert legacy.schema_version is None
        assert legacy.scoring_identity_hash is None
        assert legacy.vacancy_content_hash is None
        assert legacy.candidate_context_hash is None
        assert legacy.detail is None

    database = Database(database_url, engine=engine)
    client = ApiClient(database=database)
    vacancy = create_fixture_vacancy(client, key="migration-v1-vacancy")

    v1_payload = assessment_v1_payload(vacancy["id"])
    v1_request = AssessmentCreate.model_validate(v1_payload)
    with database.session() as session:
        created = create_assessment(session, v1_request, "v1-after-migration")
        assert created.created is True
        replay = create_assessment(
            session,
            v1_request.model_copy(update={"external_id": "assessment-v1-replay"}),
            "v1-replay-key",
        )
        assert replay.created is False
        assert replay.assessment.id == created.assessment.id

        legacy_b = AssessmentCreate.model_validate(
            assessment_payload(vacancy["id"], external_id="assessment-legacy-b")
        )
        create_assessment(session, legacy_b, "legacy-b-key")

        validated = AssessmentRead.model_validate(created.assessment)
        assert validated.schema_version == 1
        assert validated.detail is not None
        assert validated.reason == validated.detail.reason
        assert validated.action == validated.detail.action

    with engine.connect() as connection:
        total = connection.execute(text("SELECT COUNT(*) FROM assessments")).scalar_one()
        null_identity_count = connection.execute(
            text("SELECT COUNT(*) FROM assessments WHERE scoring_identity_hash IS NULL")
        ).scalar_one()
        assert total == 3
        assert null_identity_count == 2
