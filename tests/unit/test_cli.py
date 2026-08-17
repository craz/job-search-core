"""Unit tests for the versioned machine-facing Vacancy CLI."""

import json

from pytest import CaptureFixture
from tests.support import create_test_database

from job_search_core.cli import main


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
