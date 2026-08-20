"""Integration checks for the executable Alembic migration chain."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import create_engine, inspect


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
    } <= tables
