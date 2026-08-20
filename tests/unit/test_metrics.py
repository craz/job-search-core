"""Unit coverage for replay-safe Daily Metric snapshots."""

from datetime import date

import pytest
from tests.support import create_test_database

from job_search_core.metrics import (
    DailyMetricNotFoundError,
    EmptyDailyMetricUpdateError,
    MetricIdempotencyConflictError,
    get_daily_metric,
    list_daily_metrics,
    set_daily_metric,
)
from job_search_core.schemas import DailyMetricUpdate


def test_partial_updates_and_old_replay_preserve_newer_state() -> None:
    """A delayed retry is recognized but cannot undo a later partial update."""
    database = create_test_database()
    metric_date = date(2026, 8, 20)
    first = DailyMetricUpdate(applications=2, views_new=5)
    later = DailyMetricUpdate(applications=3)
    with database.session() as session:
        created = set_daily_metric(session, metric_date, first, "metric-first")
        updated = set_daily_metric(session, metric_date, later, "metric-later")
        replay = set_daily_metric(session, metric_date, first, "metric-first")

        assert created.created is True
        assert updated.created is False
        assert replay.metric.applications == 3
        assert replay.metric.views_new == 5


def test_metric_conflict_empty_update_and_missing_date_are_explicit() -> None:
    """Invalid retries and absent data use domain signals, not persistence errors."""
    database = create_test_database()
    metric_date = date(2026, 8, 20)
    with database.session() as session:
        set_daily_metric(session, metric_date, DailyMetricUpdate(replies=1), "metric-key")
        with pytest.raises(MetricIdempotencyConflictError):
            set_daily_metric(session, metric_date, DailyMetricUpdate(replies=2), "metric-key")
        with pytest.raises(EmptyDailyMetricUpdateError):
            set_daily_metric(session, metric_date, DailyMetricUpdate(), "empty-key")
        with pytest.raises(DailyMetricNotFoundError):
            get_daily_metric(session, date(2026, 8, 19))


def test_metric_list_is_bounded_filtered_and_newest_first() -> None:
    """History consumers receive deterministic date ordering and filtering."""
    database = create_test_database()
    with database.session() as session:
        for day in (18, 19, 20):
            set_daily_metric(
                session,
                date(2026, 8, day),
                DailyMetricUpdate(applications=day),
                f"metric-{day}",
            )
        items = list_daily_metrics(session, since=date(2026, 8, 19), limit=1)

    assert [item.metric_date.isoformat() for item in items] == ["2026-08-20"]
