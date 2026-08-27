"""Transactional SearchProfile / SearchRun / SearchRunItem services (R2.2.1)."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from job_search_core.models import (
    SearchProfile,
    SearchRun,
    SearchRunItem,
    SearchRunItemOutcome,
    SearchRunStatus,
    Vacancy,
    utc_now,
)
from job_search_core.schemas import (
    SearchProfileCreate,
    SearchProfileUpdate,
    SearchRunCreate,
    SearchRunFinalize,
    SearchRunItemCreate,
)

DEFAULT_EXECUTION: dict[str, object] = {
    "order": "publication_time",
    "page_size": 20,
    "max_pages": 5,
}

TERMINAL_STATUSES = frozenset(
    {SearchRunStatus.SUCCESS, SearchRunStatus.PARTIAL, SearchRunStatus.FAILED}
)


class SearchProfileNotFoundError(Exception):
    """Unknown SearchProfile id."""


class SearchRunNotFoundError(Exception):
    """Unknown SearchRun id."""


class SearchRunNotRunningError(Exception):
    """Mutating a SearchRun that is already terminal."""


class SearchRunItemValidationError(Exception):
    """Invalid SearchRunItem payload or invariant violation."""


class SearchValidationError(Exception):
    """Invalid SearchProfile or SearchRun request."""


class SearchRunItemConflictError(Exception):
    """Duplicate (search_run_id, source_external_id) inside one run."""


class VacancyNotFoundForItemError(Exception):
    """Referenced Vacancy does not exist for a non-error outcome."""


def criteria_snapshot_from_profile(profile: SearchProfile) -> dict[str, Any]:
    """Freeze semantic SearchProfile criteria only (no execution knobs)."""
    return {
        "text": profile.text,
        "area_id": profile.area_id,
        "salary": deepcopy(profile.salary) if profile.salary is not None else None,
        "experience": profile.experience,
        "employment": profile.employment,
        "schedule": profile.schedule,
        "search_field": profile.search_field,
        "only_with_salary": profile.only_with_salary,
    }


def normalize_execution_snapshot(raw: dict[str, object] | None) -> dict[str, object]:
    """Build immutable execution settings for one SearchRun."""
    base = dict(DEFAULT_EXECUTION)
    if raw:
        for key, value in raw.items():
            if key in {"order", "page_size", "max_pages"} or isinstance(
                value, (str, int, float, bool, type(None))
            ):
                base[key] = value
            elif isinstance(value, dict):
                base[key] = dict(value)
            else:
                base[key] = value
    order = str(base.get("order") or "").strip()
    if not order:
        raise SearchValidationError("execution.order_required")
    raw_page_size = base.get("page_size")
    raw_max_pages = base.get("max_pages")
    if not isinstance(raw_page_size, (int, str)) or not isinstance(raw_max_pages, (int, str)):
        raise SearchValidationError("execution.page_bounds_invalid")
    try:
        page_size = int(raw_page_size)
        max_pages = int(raw_max_pages)
    except (TypeError, ValueError) as error:
        raise SearchValidationError("execution.page_bounds_invalid") from error
    if page_size < 1 or page_size > 100:
        raise SearchValidationError("execution.page_size_out_of_range")
    if max_pages < 1 or max_pages > 100:
        raise SearchValidationError("execution.max_pages_out_of_range")
    base["order"] = order
    base["page_size"] = page_size
    base["max_pages"] = max_pages
    return base


def create_search_profile(session: Session, request: SearchProfileCreate) -> SearchProfile:
    """Persist one mutable SearchProfile with semantic criteria only."""
    text = request.text.strip()
    if not text:
        raise SearchValidationError("search_profile.text_required")
    profile = SearchProfile(
        label=request.label.strip() if request.label else None,
        text=text,
        area_id=request.area_id,
        salary=request.salary.model_dump(by_alias=True, exclude_none=True)
        if request.salary
        else None,
        experience=request.experience,
        employment=request.employment,
        schedule=request.schedule,
        search_field=request.search_field,
        only_with_salary=request.only_with_salary,
    )
    session.add(profile)
    session.flush()
    return profile


def get_search_profile(session: Session, profile_id: uuid.UUID) -> SearchProfile | None:
    """Return one SearchProfile by id."""
    return session.get(SearchProfile, profile_id)


def list_search_profiles(session: Session) -> list[SearchProfile]:
    """Return SearchProfiles newest first."""
    return list(session.scalars(select(SearchProfile).order_by(SearchProfile.created_at.desc())))


def update_search_profile(
    session: Session, profile_id: uuid.UUID, request: SearchProfileUpdate
) -> SearchProfile:
    """Patch mutable semantic fields; never writes execution knobs."""
    profile = session.get(SearchProfile, profile_id)
    if profile is None:
        raise SearchProfileNotFoundError
    data = request.model_dump(exclude_unset=True, by_alias=True)
    if "text" in data:
        text = str(data["text"] or "").strip()
        if not text:
            raise SearchValidationError("search_profile.text_required")
        profile.text = text
    if "label" in data:
        label = data["label"]
        profile.label = label.strip() if isinstance(label, str) and label.strip() else None
    for field in (
        "area_id",
        "experience",
        "employment",
        "schedule",
        "search_field",
        "only_with_salary",
    ):
        if field in data:
            setattr(profile, field, data[field])
    if "salary" in data:
        salary = data["salary"]
        if salary is None:
            profile.salary = None
        else:
            profile.salary = salary
    profile.updated_at = utc_now()
    session.flush()
    return profile


def start_search_run(session: Session, request: SearchRunCreate) -> SearchRun:
    """Create a running SearchRun with frozen criteria and execution snapshots."""
    profile = session.get(SearchProfile, request.search_profile_id)
    if profile is None:
        raise SearchProfileNotFoundError
    try:
        execution = normalize_execution_snapshot(
            request.execution.model_dump(exclude_none=True) if request.execution else None
        )
    except SearchValidationError:
        raise
    run = SearchRun(
        search_profile_id=profile.id,
        source="hh",
        criteria_snapshot=criteria_snapshot_from_profile(profile),
        execution_snapshot=execution,
        candidate_context_snapshot=request.candidate_context_snapshot,
        status=SearchRunStatus.RUNNING,
        started_at=utc_now(),
        finished_at=None,
    )
    session.add(run)
    session.flush()
    return run


def get_search_run(session: Session, run_id: uuid.UUID) -> SearchRun | None:
    """Load one SearchRun."""
    return session.get(SearchRun, run_id)


def list_search_runs(
    session: Session, *, search_profile_id: uuid.UUID | None = None
) -> list[SearchRun]:
    """Return SearchRuns newest first, optionally filtered by profile."""
    statement = select(SearchRun)
    if search_profile_id is not None:
        statement = statement.where(SearchRun.search_profile_id == search_profile_id)
    return list(session.scalars(statement.order_by(SearchRun.started_at.desc())))


def add_search_run_item(
    session: Session, run_id: uuid.UUID, request: SearchRunItemCreate
) -> SearchRunItem:
    """Attach one provenance item to a running SearchRun."""
    run = session.get(SearchRun, run_id)
    if run is None:
        raise SearchRunNotFoundError
    if run.status != SearchRunStatus.RUNNING:
        raise SearchRunNotRunningError
    external_id = request.source_external_id.strip()
    if not external_id:
        raise SearchRunItemValidationError("source_external_id_required")
    outcome = request.outcome
    if outcome != SearchRunItemOutcome.ERROR and request.vacancy_id is None:
        raise SearchRunItemValidationError("vacancy_id_required_for_non_error")
    if request.vacancy_id is not None:
        vacancy = session.get(Vacancy, request.vacancy_id)
        if vacancy is None:
            raise VacancyNotFoundForItemError
    duplicate = session.scalar(
        select(SearchRunItem).where(
            SearchRunItem.search_run_id == run_id,
            SearchRunItem.source_external_id == external_id,
        )
    )
    if duplicate is not None:
        raise SearchRunItemConflictError
    item = SearchRunItem(
        search_run_id=run_id,
        source_external_id=external_id,
        vacancy_id=request.vacancy_id,
        outcome=outcome,
        discovered_at=request.discovered_at or utc_now(),
        page=request.page,
        error_code=request.error_code,
        error_detail=request.error_detail,
    )
    session.add(item)
    try:
        session.flush()
    except IntegrityError as error:
        raise SearchRunItemConflictError from error
    return item


def list_search_run_items(session: Session, run_id: uuid.UUID) -> list[SearchRunItem]:
    """Return items for one SearchRun ordered by discovery time."""
    run = session.get(SearchRun, run_id)
    if run is None:
        raise SearchRunNotFoundError
    return list(
        session.scalars(
            select(SearchRunItem)
            .options(joinedload(SearchRunItem.vacancy))
            .where(SearchRunItem.search_run_id == run_id)
            .order_by(SearchRunItem.discovered_at.asc(), SearchRunItem.id.asc())
        )
    )


def recompute_run_counters(session: Session, run: SearchRun) -> None:
    """Align denormalized SearchRun counters with persisted SearchRunItem rows."""
    items = list(
        session.scalars(select(SearchRunItem).where(SearchRunItem.search_run_id == run.id))
    )
    created = sum(1 for item in items if item.outcome == SearchRunItemOutcome.CREATED)
    updated = sum(1 for item in items if item.outcome == SearchRunItemOutcome.UPDATED)
    unchanged = sum(1 for item in items if item.outcome == SearchRunItemOutcome.UNCHANGED)
    errors = sum(1 for item in items if item.outcome == SearchRunItemOutcome.ERROR)
    run.created_count = created
    run.updated_count = updated
    run.unchanged_count = unchanged
    run.error_count = errors
    run.found_count = created + updated + unchanged + errors


def finalize_search_run(
    session: Session, run_id: uuid.UUID, request: SearchRunFinalize
) -> SearchRun:
    """Move a running SearchRun to a terminal status and stamp finished_at.

    Terminal runs are immutable: repeated finalize and terminal→terminal
    transitions are rejected.
    """
    run = session.get(SearchRun, run_id)
    if run is None:
        raise SearchRunNotFoundError
    if run.status != SearchRunStatus.RUNNING:
        raise SearchRunNotRunningError
    if request.status not in TERMINAL_STATUSES:
        raise SearchValidationError("finalize_status_must_be_terminal")
    recompute_run_counters(session, run)
    run.status = request.status
    run.finished_at = utc_now()
    run.error_code = request.error_code
    run.recovery_hint = request.recovery_hint
    session.flush()
    return run
