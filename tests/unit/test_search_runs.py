"""Unit tests for SearchProfile / SearchRun invariants (R2.2.1)."""

from __future__ import annotations

import pytest
from tests.support import create_test_database

from job_search_core.models import SearchRunAcquisitionKind, SearchRunItemOutcome, SearchRunStatus
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
    SearchRunNotRunningError,
    SearchValidationError,
    add_search_run_item,
    create_search_profile,
    criteria_snapshot_from_profile,
    finalize_search_run,
    start_search_run,
    update_search_profile,
)
from job_search_core.vacancies import create_vacancy


def test_resume_suitable_requires_null_profile_and_resume_context() -> None:
    database = create_test_database()
    with database.session() as session:
        with pytest.raises(SearchValidationError, match="hh_resume_external_id_required"):
            start_search_run(
                session,
                SearchRunCreate(acquisition_kind=SearchRunAcquisitionKind.RESUME_SUITABLE),
            )
        profile = create_search_profile(session, SearchProfileCreate(text="python"))
        with pytest.raises(SearchValidationError, match="search_profile_id_forbidden"):
            start_search_run(
                session,
                SearchRunCreate(
                    acquisition_kind=SearchRunAcquisitionKind.RESUME_SUITABLE,
                    search_profile_id=profile.id,
                    candidate_context_snapshot={
                        "hh_resume_external_id": "abc",
                        "hh_resume_title": "PM",
                    },
                ),
            )
        run = start_search_run(
            session,
            SearchRunCreate(
                acquisition_kind=SearchRunAcquisitionKind.RESUME_SUITABLE,
                candidate_context_snapshot={
                    "hh_resume_external_id": "f3e5e5f7ff0f50d3e50039ed1f4436664d7338",
                    "hh_resume_title": "Project Manager / Руководитель IT-проектов",
                },
                execution=SearchExecutionSettings(order="publication_time", max_pages=1),
            ),
        )
        assert run.search_profile_id is None
        assert run.acquisition_kind == SearchRunAcquisitionKind.RESUME_SUITABLE
        assert run.criteria_snapshot == {}
        assert run.candidate_context_snapshot["hh_resume_external_id"].startswith("f3e5")
        assert run.execution_snapshot["order"] == "publication_time"


def test_profile_search_still_requires_search_profile() -> None:
    database = create_test_database()
    with (
        database.session() as session,
        pytest.raises(SearchValidationError, match="search_profile_id_required"),
    ):
        start_search_run(
            session,
            SearchRunCreate(acquisition_kind=SearchRunAcquisitionKind.PROFILE_SEARCH),
        )


def test_finalize_stores_source_total() -> None:
    database = create_test_database()
    with database.session() as session:
        profile = create_search_profile(session, SearchProfileCreate(text="python"))
        run = start_search_run(session, SearchRunCreate(search_profile_id=profile.id))
        finalized = finalize_search_run(
            session,
            run.id,
            SearchRunFinalize(status=SearchRunStatus.SUCCESS, source_total=2272),
        )
        assert finalized.source_total == 2272
        assert finalized.found_count == 0
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


def test_terminal_run_rejects_items_and_re_finalize() -> None:
    database = create_test_database()
    with database.session() as session:
        profile = create_search_profile(session, SearchProfileCreate(text="pm"))
        run = start_search_run(session, SearchRunCreate(search_profile_id=profile.id))
        vacancy = create_vacancy(
            session,
            VacancyCreate(
                company_name="Labs",
                company_external_id="c2",
                source="hh",
                external_id="v-term",
                title="PM",
                url="https://example.com/v/2",
            ),
            "key-v2",
        ).vacancy
        add_search_run_item(
            session,
            run.id,
            SearchRunItemCreate(
                source_external_id="v-term",
                outcome=SearchRunItemOutcome.CREATED,
                vacancy_id=vacancy.id,
            ),
        )
        finalize_search_run(session, run.id, SearchRunFinalize(status=SearchRunStatus.SUCCESS))
        with pytest.raises(SearchRunNotRunningError):
            add_search_run_item(
                session,
                run.id,
                SearchRunItemCreate(
                    source_external_id="late",
                    outcome=SearchRunItemOutcome.UNCHANGED,
                    vacancy_id=vacancy.id,
                ),
            )
        with pytest.raises(SearchRunNotRunningError):
            finalize_search_run(session, run.id, SearchRunFinalize(status=SearchRunStatus.SUCCESS))
        with pytest.raises(SearchRunNotRunningError):
            finalize_search_run(session, run.id, SearchRunFinalize(status=SearchRunStatus.FAILED))
        session.refresh(run)
        assert run.status == SearchRunStatus.SUCCESS
        assert run.found_count == 1
        assert run.created_count == 1
