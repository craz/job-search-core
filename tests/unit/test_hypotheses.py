"""Unit coverage for measurable Hypothesis lifecycle invariants."""

import uuid

import pytest
from tests.support import create_test_database

from job_search_core.hypotheses import (
    HypothesisAlreadyClosedError,
    HypothesisIdempotencyConflictError,
    HypothesisNotFoundError,
    close_hypothesis,
    create_hypothesis,
    list_hypotheses,
)
from job_search_core.models import HypothesisStatus
from job_search_core.schemas import HypothesisCreate


def request() -> HypothesisCreate:
    """Build one synthetic measurable experiment."""
    return HypothesisCreate(
        source="fixture",
        external_id="hypothesis-100",
        title="Referral outreach improves replies",
        description="Compare a bounded synthetic cohort.",
        test_size=10,
        metric="reply_rate",
    )


def test_create_replay_filter_and_close_preserve_result() -> None:
    """Identical create/close retries are safe and the first result is immutable."""
    database = create_test_database()
    with database.session() as session:
        first = create_hypothesis(session, request(), "hypothesis-key")
        replay = create_hypothesis(session, request(), "hypothesis-key")
        closed = close_hypothesis(session, first.hypothesis.id, "Reply rate improved")
        same = close_hypothesis(session, first.hypothesis.id, "Reply rate improved")

        assert first.created is True and replay.created is False
        assert closed.status == HypothesisStatus.DONE
        assert same.result == "Reply rate improved"
        assert len(list_hypotheses(session, HypothesisStatus.DONE)) == 1
        with pytest.raises(HypothesisAlreadyClosedError):
            close_hypothesis(session, first.hypothesis.id, "Different result")
        with pytest.raises(HypothesisIdempotencyConflictError):
            create_hypothesis(
                session, request().model_copy(update={"title": "Changed"}), "hypothesis-key"
            )


def test_unknown_hypothesis_is_explicit() -> None:
    """Closing a missing experiment exposes a stable domain signal."""
    database = create_test_database()
    with database.session() as session, pytest.raises(HypothesisNotFoundError):
        close_hypothesis(session, uuid.uuid4(), "No observation")
