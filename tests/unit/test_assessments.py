"""Unit coverage for normalized Assessment invariants."""

import pytest
from tests.support import (
    ApiClient,
    assessment_payload,
    create_fixture_vacancy,
)

from job_search_core.assessments import (
    AssessmentIdempotencyConflictError,
    create_assessment,
    list_assessments,
)
from job_search_core.schemas import AssessmentCreate


def test_create_replay_and_filter_normalized_result() -> None:
    """Identical input stores one result and conflicting retry is rejected."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    request = AssessmentCreate.model_validate(assessment_payload(vacancy["id"]))
    with client.database.session() as session:
        first = create_assessment(session, request, "assessment-key")
        replay = create_assessment(session, request, "assessment-key")
        assert first.created is True and replay.created is False
        assert len(list_assessments(session, request.vacancy_id)) == 1
        with pytest.raises(AssessmentIdempotencyConflictError):
            create_assessment(
                session, request.model_copy(update={"relevance_score": 50}), "assessment-key"
            )
