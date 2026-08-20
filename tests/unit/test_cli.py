"""Unit tests for versioned machine-facing Core resource commands."""

import json

from pytest import CaptureFixture
from tests.support import create_test_database

from job_search_core.cli import main
from job_search_core.models import Company, Vacancy


def test_vacancy_create_and_list_emit_one_versioned_json_document(
    capsys: CaptureFixture[str],
) -> None:
    """CLI automation can create and retrieve a vacancy without parsing prose."""
    database = create_test_database()
    create_args = [
        "vacancy",
        "create",
        "--idempotency-key",
        "cli-key",
        "--source",
        "fixture",
        "--external-id",
        "vacancy-cli",
        "--company-name",
        "Example Labs",
        "--company-external-id",
        "company-cli",
        "--title",
        "CLI Engineer",
        "--url",
        "https://example.com/vacancies/cli",
    ]

    assert main(create_args, database=database) == 0
    create_output = capsys.readouterr().out
    assert main(["vacancy", "list"], database=database) == 0
    list_output = capsys.readouterr().out

    created = json.loads(create_output)
    listing = json.loads(list_output)
    assert created["contract_version"] == "1.0"
    assert created["command"] == "vacancy.create"
    assert created["data"]["created"] is True
    assert listing["data"]["total"] == 1


def test_application_create_and_list_emit_versioned_json(
    capsys: CaptureFixture[str],
) -> None:
    """CLI automation can record and retrieve an Application without prose."""
    database = create_test_database()
    with database.session() as session:
        company = Company(name="CLI Labs", source="fixture", external_id="cli-company")
        vacancy = Vacancy(
            company=company,
            source="fixture",
            external_id="cli-vacancy",
            title="CLI Application Engineer",
            url="https://example.com/cli-vacancy",
            idempotency_key="cli-vacancy-key",
            request_fingerprint="fixture",
        )
        session.add(vacancy)
        session.flush()
        vacancy_id = str(vacancy.id)

    create_args = [
        "application",
        "create",
        "--idempotency-key",
        "cli-application-key",
        "--vacancy-id",
        vacancy_id,
        "--source",
        "fixture",
        "--external-id",
        "cli-application",
        "--applied-at",
        "2026-08-19T10:00:00Z",
    ]
    assert main(create_args, database=database) == 0
    created = json.loads(capsys.readouterr().out)
    assert main(["application", "list"], database=database) == 0
    listing = json.loads(capsys.readouterr().out)

    assert created["command"] == "application.create"
    assert created["data"]["created"] is True
    assert listing["data"]["total"] == 1


def test_metric_set_show_and_list_emit_versioned_json(capsys: CaptureFixture[str]) -> None:
    """CLI automation can apply and retrieve a dated snapshot without prose."""
    database = create_test_database()
    set_args = [
        "metric",
        "set",
        "--idempotency-key",
        "cli-metric-key",
        "--date",
        "2026-08-20",
        "--applications",
        "3",
        "--views-new",
        "7",
    ]

    assert main(set_args, database=database) == 0
    created = json.loads(capsys.readouterr().out)
    assert main(["metric", "show", "--date", "2026-08-20"], database=database) == 0
    shown = json.loads(capsys.readouterr().out)
    assert main(["metric", "list", "--since", "2026-08-20"], database=database) == 0
    listing = json.loads(capsys.readouterr().out)

    assert created["command"] == "metric.set"
    assert created["data"]["created"] is True
    assert shown["data"]["applications"] == 3
    assert listing["data"]["total"] == 1


def test_person_create_list_and_status_emit_versioned_json(
    capsys: CaptureFixture[str],
) -> None:
    """CLI manages one confirmed contact using only JSON contracts."""
    database = create_test_database()
    with database.session() as session:
        company = Company(name="People Labs", source="fixture", external_id="people-company")
        session.add(company)
        session.flush()
        company_id = str(company.id)
    create_args = [
        "person",
        "create",
        "--idempotency-key",
        "cli-person-key",
        "--company-id",
        company_id,
        "--source",
        "fixture",
        "--external-id",
        "cli-person",
        "--full-name",
        "Alex Example",
        "--role",
        "referral",
    ]

    assert main(create_args, database=database) == 0
    created = json.loads(capsys.readouterr().out)
    assert main(["person", "list"], database=database) == 0
    listing = json.loads(capsys.readouterr().out)
    assert (
        main(
            [
                "person",
                "set-status",
                "--person-id",
                created["data"]["id"],
                "--status",
                "contacted",
            ],
            database=database,
        )
        == 0
    )
    updated = json.loads(capsys.readouterr().out)

    assert created["command"] == "person.create"
    assert listing["data"]["total"] == 1
    assert updated["data"]["status"] == "contacted"
