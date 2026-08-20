"""Transactional Daily Metric service with replay-safe partial snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_search_core.models import DailyMetric, DailyMetricRequest
from job_search_core.schemas import DailyMetricUpdate


class MetricIdempotencyConflictError(Exception):
    """Signal reuse of one metric write key for materially different input."""


class DailyMetricNotFoundError(Exception):
    """Signal that no snapshot exists for the requested calendar date."""


class EmptyDailyMetricUpdateError(Exception):
    """Signal a partial update that specifies no metric field."""


@dataclass(frozen=True)
class SetDailyMetricResult:
    """Persisted snapshot plus whether the date itself was created."""

    metric: DailyMetric
    created: bool


def metric_fingerprint(metric_date: date, request: DailyMetricUpdate) -> str:
    """Hash the date and explicitly supplied fields for retry comparison."""
    canonical = {
        "metric_date": metric_date.isoformat(),
        "values": request.model_dump(mode="json", exclude_unset=True),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def set_daily_metric(
    session: Session, metric_date: date, request: DailyMetricUpdate, idempotency_key: str
) -> SetDailyMetricResult:
    """Apply supplied fields once, while later retries of the same key become reads."""
    values = request.model_dump(exclude_unset=True)
    if not values:
        raise EmptyDailyMetricUpdateError
    fingerprint = metric_fingerprint(metric_date, request)
    processed = session.scalar(
        select(DailyMetricRequest).where(DailyMetricRequest.idempotency_key == idempotency_key)
    )
    if processed is not None:
        if processed.request_fingerprint != fingerprint:
            raise MetricIdempotencyConflictError
        metric = session.get(DailyMetric, processed.metric_date)
        if metric is None:  # Database constraints make this an internal invariant.
            raise RuntimeError("processed metric request has no metric")
        return SetDailyMetricResult(metric=metric, created=False)

    metric = session.get(DailyMetric, metric_date)
    created = metric is None
    if metric is None:
        metric = DailyMetric(metric_date=metric_date)
        session.add(metric)
    for field, value in values.items():
        setattr(metric, field, value)
    session.add(
        DailyMetricRequest(
            metric_date=metric_date,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
    )
    session.flush()
    return SetDailyMetricResult(metric=metric, created=created)


def get_daily_metric(session: Session, metric_date: date) -> DailyMetric:
    """Return one date snapshot or a stable domain-level absence signal."""
    metric = session.get(DailyMetric, metric_date)
    if metric is None:
        raise DailyMetricNotFoundError
    return metric


def list_daily_metrics(
    session: Session, *, since: date | None = None, limit: int = 60
) -> list[DailyMetric]:
    """Return bounded snapshots newest first, optionally filtered by start date."""
    statement = select(DailyMetric)
    if since is not None:
        statement = statement.where(DailyMetric.metric_date >= since)
    return list(session.scalars(statement.order_by(DailyMetric.metric_date.desc()).limit(limit)))
