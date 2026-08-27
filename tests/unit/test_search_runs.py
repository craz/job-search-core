"""Unit tests for SearchProfile / SearchRun invariants (R2.2.1)."""

from __future__ import annotations

import pytest
from tests.support import create_test_database

from job_search_core.models import SearchRunItemOutcome, SearchRunStatus
from job_search_core.schemas import (
    SearchExecutionSettings,
    SearchProfileCreate,
    SearchProfileUpdate,
    SearchRunCreate,
    SearchRunFinalize,
    SearchRunItemCreate,
    VacancyCreate,
)
from job_search_core.search_runs import (
    SearchRunItemValidationError,
    add_search_run_item,
    create_search_profile,
    criteria_snapshot_from_profile,
    finalize_search_run,
    start_search_run,
    update_search_profile,
)
from job_search_core.vacancies import create_vacancy


def test_criteria_snapshot_excludes_execution_knobs() -> None:
    database = create_test_database()
    with database.session() as session:
        profile = create_search_profile(
            session,
            SearchProfileCreate(text="project manager", area_id="1", experience="between3And6"),
        )
        snap = criteria_snapshot_from_profile(profile)
        assert snap["text"] == "project manager"
        assert "page_size" not in snap
        assert "max_pages" not in snap
        assert "order" not in snap


def test_profile_mutation_does_not_change_existing_run_snapshot() -> None:
    database = create_test_database()
    with database.session() as session:
        profile = create_search_profile(session, SearchProfileCreate(text="python"))
        run = start_search_run(
            session,
            SearchRunCreate(
                search_profile_id=profile.id,
                execution=SearchExecutionSettings(order="relevance", page_size=10, max_pages=2),
            ),
        )
        frozen = dict(run.criteria_snapshot)
        update_search_profile(session, profile.id, SearchProfileUpdate(text="golang"))
        session.refresh(run)
        assert run.criteria_snapshot == frozen
        assert run.criteria_snapshot["text"] == "python"
        assert run.execution_snapshot["page_size"] == 10
        assert run.status == SearchRunStatus.RUNNING
        assert run.finished_at is None


def test_non_error_item_requires_vacancy_id() -> None:
    database = create_test_database()
    with database.session() as session:
        profile = create_search_profile(session, SearchProfileCreate(text="pm"))
        run = start_search_run(session, SearchRunCreate(search_profile_id=profile.id))
        with pytest.raises(SearchRunItemValidationError, match="vacancy_id_required"):
            add_search_run_item(
                session,
                run.id,
                SearchRunItemCreate(
                    source_external_id="hh-1",
                    outcome=SearchRunItemOutcome.CREATED,
                    vacancy_id=None,
                ),
            )


def test_error_item_without_vacancy_and_counters() -> None:
    database = create_test_database()
    with database.session() as session:
        profile = create_search_profile(session, SearchProfileCreate(text="pm"))
        run = start_search_run(session, SearchRunCreate(search_profile_id=profile.id))
        vacancy = create_vacancy(
            session,
            VacancyCreate(
                company_name="Labs",
                company_external_id="c1",
                source="hh",
                external_id="v-ok",
                title="PM",
                url="https://example.com/v/1",
            ),
            "key-v1",
        ).vacancy
        add_search_run_item(
            session,
            run.id,
            SearchRunItemCreate(
                source_external_id="v-ok",
                outcome=SearchRunItemOutcome.CREATED,
                vacancy_id=vacancy.id,
            ),
        )
        add_search_run_item(
            session,
            run.id,
            SearchRunItemCreate(
                source_external_id="v-bad",
                outcome=SearchRunItemOutcome.ERROR,
                vacancy_id=None,
                error_code="normalize_failed",
                error_detail="incomplete",
            ),
        )
        finalized = finalize_search_run(
            session, run.id, SearchRunFinalize(status=SearchRunStatus.PARTIAL)
        )
        assert finalized.status == SearchRunStatus.PARTIAL
        assert finalized.finished_at is not None
        assert finalized.found_count == 2
        assert finalized.created_count == 1
        assert finalized.error_count == 1
        assert finalized.updated_count == 0
        assert finalized.unchanged_count == 0
