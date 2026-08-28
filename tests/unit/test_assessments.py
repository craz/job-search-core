"""Unit coverage for normalized Assessment invariants and v1 scoring identity."""

from __future__ import annotations

import pytest
from tests.support import (
    ApiClient,
    assessment_payload,
    assessment_v1_payload,
    create_fixture_vacancy,
)

from job_search_core.assessments import (
    AssessmentAlreadyExistsError,
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


def test_legacy_assessment_allows_null_v1_fields() -> None:
    """Historical-style writes do not require v1 provenance columns."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    request = AssessmentCreate.model_validate(assessment_payload(vacancy["id"]))
    with client.database.session() as session:
        result = create_assessment(session, request, "legacy-key")
        row = result.assessment
        assert row.schema_version is None
        assert row.scoring_identity_hash is None
        assert row.detail is not None


def test_v1_assessment_requires_complete_identity() -> None:
    """schema_version=1 rejects incomplete provenance."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = assessment_v1_payload(vacancy["id"])
    payload.pop("scoring_identity_hash")
    with pytest.raises(ValueError, match="schema_version=1 requires"):
        AssessmentCreate.model_validate(payload)


def test_v1_identity_reuse_prevents_duplicate() -> None:
    """Same scoring_identity_hash reuses the canonical Assessment."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    request = AssessmentCreate.model_validate(assessment_v1_payload(vacancy["id"]))
    with client.database.session() as session:
        first = create_assessment(session, request, "identity-key-a")
        second = create_assessment(
            session,
            request.model_copy(update={"external_id": "assessment-other"}),
            "identity-key-b",
        )
        assert first.created is True
        assert second.created is False
        assert second.assessment.id == first.assessment.id
        assert len(list_assessments(session, request.vacancy_id)) == 1


def test_multiple_null_identities_can_coexist() -> None:
    """Legacy rows without scoring_identity_hash are not uniqueness-blocked."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    with client.database.session() as session:
        first = AssessmentCreate.model_validate(assessment_payload(vacancy["id"]))
        second = AssessmentCreate.model_validate(
            assessment_payload(vacancy["id"], external_id="assessment-200")
        )
        create_assessment(session, first, "legacy-a")
        create_assessment(session, second, "legacy-b")
        assert len(list_assessments(session, first.vacancy_id)) == 2


def test_duplicate_external_id_still_conflicts_for_legacy() -> None:
    """source+external_id uniqueness remains for integration identity."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    request = AssessmentCreate.model_validate(assessment_payload(vacancy["id"]))
    with client.database.session() as session:
        create_assessment(session, request, "dup-a")
        with pytest.raises(AssessmentAlreadyExistsError):
            create_assessment(session, request, "dup-b")


def test_v1_detail_round_trip_columns() -> None:
    """JSONB detail mirrors reason/risk/action on v1 writes."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    request = AssessmentCreate.model_validate(assessment_v1_payload(vacancy["id"]))
    with client.database.session() as session:
        result = create_assessment(session, request, "detail-key")
        row = result.assessment
        assert row.schema_version == 1
        assert row.detail is not None
        assert row.detail["reason"] == request.detail.reason  # type: ignore[union-attr]
        assert row.reason == request.detail.reason  # type: ignore[union-attr]
        assert row.action == request.detail.action  # type: ignore[union-attr]
        assert row.risk == request.detail.risk  # type: ignore[union-attr]
        assert row.candidate_context_hash is not None
        assert row.policy_hash is not None


def test_v1_detail_is_canonical_explanation_source() -> None:
    """schema_version=1 derives mirrored reason/action from detail, not vice versa."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = assessment_v1_payload(vacancy["id"])
    payload.pop("reason", None)
    payload.pop("action", None)
    payload.pop("risk", None)
    request = AssessmentCreate.model_validate(payload)
    with client.database.session() as session:
        result = create_assessment(session, request, "canonical-detail")
        row = result.assessment
        assert row.detail is not None
        assert row.reason == row.detail["reason"]
        assert row.action == row.detail["action"]


def test_v1_rejects_conflicting_top_level_reason() -> None:
    """Top-level reason/action cannot diverge from canonical detail on v1 writes."""
    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    payload = assessment_v1_payload(vacancy["id"])
    payload["reason"] = "Conflicting legacy reason"
    with pytest.raises(ValueError, match="top-level reason must match detail"):
        AssessmentCreate.model_validate(payload)


def test_partial_unique_scoring_identity_hash_enforced() -> None:
    """Database rejects duplicate non-null scoring_identity_hash values."""
    from sqlalchemy.exc import IntegrityError

    from job_search_core.models import Assessment, AssessmentVerdict

    client = ApiClient()
    vacancy = create_fixture_vacancy(client)
    request = AssessmentCreate.model_validate(assessment_v1_payload(vacancy["id"]))
    with client.database.session() as session:
        create_assessment(session, request, "unique-a")
        duplicate = Assessment(
            vacancy_id=request.vacancy_id,
            source="fixture",
            external_id="assessment-force-dup",
            relevance_score=50,
            verdict=AssessmentVerdict.SKIP,
            reason="dup",
            action="skip",
            model="fixture",
            prompt_version="v1",
            assessed_at=request.assessed_at,
            idempotency_key="unique-b",
            request_fingerprint="deadbeef",
            scoring_identity_hash=request.scoring_identity_hash,
            schema_version=1,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
