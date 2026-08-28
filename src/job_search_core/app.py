"""FastAPI factory for health and the versioned Vacancy HTTP contract.

Liveness has no dependencies. Readiness performs a database query and returns
503 when PostgreSQL is unavailable. Vacancy writes use an explicit idempotency
header and one transaction per request; consumers never receive database access.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Annotated, Final

from fastapi import FastAPI, File, Header, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from job_search_core import __version__
from job_search_core.applications import (
    ApplicationAlreadyExistsError,
    ApplicationIdempotencyConflictError,
    ApplicationVacancyNotFoundError,
    create_application,
    list_applications,
)
from job_search_core.assessments import (
    AssessmentAlreadyExistsError,
    AssessmentIdempotencyConflictError,
    AssessmentVacancyNotFoundError,
    create_assessment,
    list_assessments,
)
from job_search_core.candidate_context import (
    HhResumeLinkValidationError,
    get_candidate_context,
    set_hh_resume_link,
)
from job_search_core.companies import CompanyNotFoundError, set_company_website
from job_search_core.config import Settings
from job_search_core.database import Database
from job_search_core.hypotheses import (
    HypothesisAlreadyClosedError,
    HypothesisAlreadyExistsError,
    HypothesisIdempotencyConflictError,
    HypothesisNotFoundError,
    close_hypothesis,
    create_hypothesis,
    list_hypotheses,
)
from job_search_core.metrics import (
    DailyMetricNotFoundError,
    EmptyDailyMetricUpdateError,
    MetricIdempotencyConflictError,
    get_daily_metric,
    list_daily_metrics,
    set_daily_metric,
)
from job_search_core.models import HypothesisStatus
from job_search_core.people import (
    PersonAlreadyExistsError,
    PersonCompanyMismatchError,
    PersonCompanyNotFoundError,
    PersonIdempotencyConflictError,
    PersonNotFoundError,
    PersonVacancyNotFoundError,
    create_person,
    list_people,
    update_person_status,
)
from job_search_core.resume_artifacts import (
    ResumeArtifactValidationError,
    content_disposition_attachment,
    get_resume_artifact,
    ingest_resume_artifact,
    load_resume_artifact_bytes,
    resume_file_meta,
)
from job_search_core.resume_versions import (
    ResumeVersionValidationError,
    get_resume_version,
    ingest_resume_version,
    resume_content_meta,
)
from job_search_core.schemas import (
    ApplicationCreate,
    ApplicationList,
    ApplicationRead,
    AssessmentCreate,
    AssessmentList,
    AssessmentRead,
    CandidateContextRead,
    CandidateProfileRead,
    CompanyRead,
    CompanyWebsiteUpdate,
    DailyMetricList,
    DailyMetricRead,
    DailyMetricUpdate,
    ErrorDetail,
    HhResumeLinkRead,
    HhResumeLinkUpdate,
    HypothesisClose,
    HypothesisCreate,
    HypothesisList,
    HypothesisRead,
    PersonCreate,
    PersonList,
    PersonRead,
    PersonStatusUpdate,
    ProfileVersionRead,
    ResumeArtifactIngestResultRead,
    ResumeArtifactRead,
    ResumeContentMetaRead,
    ResumeFileMetaRead,
    ResumeVersionIngest,
    ResumeVersionIngestResultRead,
    ResumeVersionMetaRead,
    ResumeVersionRead,
    SearchProfileCreate,
    SearchProfileList,
    SearchProfileRead,
    SearchProfileUpdate,
    SearchRunCreate,
    SearchRunFinalize,
    SearchRunItemCreate,
    SearchRunItemList,
    SearchRunItemRead,
    SearchRunList,
    SearchRunRead,
    VacancyCreate,
    VacancyIngest,
    VacancyIngestResult,
    VacancyList,
    VacancyRead,
    VacancyStatusUpdate,
)
from job_search_core.search_runs import (
    SearchProfileNotFoundError,
    SearchRunItemConflictError,
    SearchRunItemValidationError,
    SearchRunNotFoundError,
    SearchRunNotRunningError,
    SearchValidationError,
    VacancyNotFoundForItemError,
    add_search_run_item,
    create_search_profile,
    finalize_search_run,
    get_search_profile,
    get_search_run,
    list_search_profiles,
    list_search_run_items,
    list_search_runs,
    start_search_run,
    update_search_profile,
)
from job_search_core.vacancies import (
    IdempotencyConflictError,
    VacancyAlreadyExistsError,
    VacancyIngestValidationError,
    VacancyNotFoundError,
    create_vacancy,
    ingest_vacancy,
    list_vacancies,
    update_vacancy_status,
)

COMPONENT_NAME: Final = "job-search-core"


class HealthResponse(BaseModel):
    """Stable machine-readable health response shared by probes and operators."""

    status: str
    component: str
    version: str


def component_info() -> HealthResponse:
    """Return immutable process metadata without performing external I/O."""
    return HealthResponse(status="ok", component=COMPONENT_NAME, version=__version__)


def error_response(code: str, message: str, http_status: int) -> JSONResponse:
    """Build a stable expected-error response with a correlation identifier."""
    detail = ErrorDetail(code=code, message=message, trace_id=str(uuid.uuid4()))
    return JSONResponse(status_code=http_status, content=detail.model_dump(mode="json"))


def create_app(*, settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    """Build an isolated ASGI application around one configured database.

    Supplying ``database`` is the supported test seam. Schema creation remains an
    Alembic/deployment responsibility and is never performed as an import or
    application startup side effect.
    """
    runtime_settings = settings or Settings()
    persistence = database or Database(runtime_settings.database_url)
    artifact_root = Path(runtime_settings.artifact_dir)

    def ensure_artifact_root() -> Path:
        artifact_root.mkdir(parents=True, exist_ok=True)
        return artifact_root

    application = FastAPI(
        title="Job Search Core API",
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    @application.get("/health/live", response_model=HealthResponse, tags=["health"])
    def liveness() -> HealthResponse:
        """Report that the API process is alive without checking dependencies."""
        return component_info()

    @application.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorDetail}},
        tags=["health"],
    )
    def readiness() -> HealthResponse | JSONResponse:
        """Report readiness only when the Core-owned database accepts a query."""
        try:
            persistence.ping()
        except SQLAlchemyError:
            return error_response("database_unavailable", "Core database is unavailable", 503)
        return component_info()

    @application.post(
        "/api/v1/vacancies",
        response_model=VacancyRead,
        status_code=status.HTTP_201_CREATED,
        responses={409: {"model": ErrorDetail}},
        tags=["vacancies"],
    )
    def post_vacancy(
        request: VacancyCreate,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=255, alias="Idempotency-Key"),
    ) -> VacancyRead | JSONResponse:
        """Persist a vacancy once and replay an identical idempotency key safely."""
        try:
            with persistence.session() as session:
                result = create_vacancy(session, request, idempotency_key)
                payload = VacancyRead.model_validate(result.vacancy)
        except IdempotencyConflictError:
            return error_response(
                "idempotency_conflict",
                "Idempotency-Key was already used for a different request",
                409,
            )
        except VacancyAlreadyExistsError:
            return error_response(
                "vacancy_exists",
                "A vacancy with this source identity already exists",
                409,
            )
        response.status_code = 201 if result.created else 200
        return payload

    @application.post(
        "/api/v1/vacancies/ingest",
        response_model=VacancyIngestResult,
        status_code=status.HTTP_200_OK,
        responses={400: {"model": ErrorDetail}},
        tags=["vacancies"],
    )
    def post_vacancy_ingest(request: VacancyIngest) -> VacancyIngestResult | JSONResponse:
        """Identity-safe source upsert: created | updated | unchanged (no Idempotency-Key)."""
        try:
            with persistence.session() as session:
                result = ingest_vacancy(session, request)
                return VacancyIngestResult(
                    outcome=result.outcome,
                    vacancy=VacancyRead.model_validate(result.vacancy),
                )
        except VacancyIngestValidationError as error:
            return error_response("invalid_vacancy_ingest", str(error), 400)

    @application.get("/api/v1/vacancies", response_model=VacancyList, tags=["vacancies"])
    def get_vacancies() -> VacancyList:
        """List persisted vacancies without exposing storage implementation details."""
        with persistence.session() as session:
            items = [VacancyRead.model_validate(item) for item in list_vacancies(session)]
        return VacancyList(items=items, total=len(items))

    @application.put(
        "/api/v1/companies/{company_id}/website",
        response_model=CompanyRead,
        responses={404: {"model": ErrorDetail}},
        tags=["companies"],
    )
    def put_company_website(
        company_id: uuid.UUID, request: CompanyWebsiteUpdate
    ) -> CompanyRead | JSONResponse:
        """Store only an explicitly confirmed normalized official website URL."""
        try:
            with persistence.session() as session:
                company = set_company_website(session, company_id, request)
                return CompanyRead.model_validate(company)
        except CompanyNotFoundError:
            return error_response("company_not_found", "Company does not exist", 404)

    @application.patch(
        "/api/v1/vacancies/{vacancy_id}",
        response_model=VacancyRead,
        responses={404: {"model": ErrorDetail}},
        tags=["vacancies"],
    )
    def patch_vacancy_status(
        vacancy_id: uuid.UUID, request: VacancyStatusUpdate
    ) -> VacancyRead | JSONResponse:
        """Change a vacancy funnel status through the public Core contract."""
        try:
            with persistence.session() as session:
                vacancy = update_vacancy_status(session, vacancy_id, request.status)
                return VacancyRead.model_validate(vacancy)
        except VacancyNotFoundError:
            return error_response("vacancy_not_found", "Vacancy does not exist", 404)

    @application.post(
        "/api/v1/applications",
        response_model=ApplicationRead,
        status_code=status.HTTP_201_CREATED,
        responses={404: {"model": ErrorDetail}, 409: {"model": ErrorDetail}},
        tags=["applications"],
    )
    def post_application(
        request: ApplicationCreate,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=255, alias="Idempotency-Key"),
    ) -> ApplicationRead | JSONResponse:
        """Persist one normalized Application or safely replay an identical request."""
        try:
            with persistence.session() as session:
                result = create_application(session, request, idempotency_key)
                payload = ApplicationRead.model_validate(result.application)
        except ApplicationIdempotencyConflictError:
            return error_response(
                "idempotency_conflict",
                "Idempotency-Key was already used for a different request",
                409,
            )
        except ApplicationAlreadyExistsError:
            return error_response(
                "application_exists",
                "An application with this source identity already exists",
                409,
            )
        except ApplicationVacancyNotFoundError:
            return error_response("vacancy_not_found", "Vacancy does not exist", 404)
        response.status_code = 201 if result.created else 200
        return payload

    @application.get("/api/v1/applications", response_model=ApplicationList, tags=["applications"])
    def get_applications() -> ApplicationList:
        """List normalized Applications without exposing Core persistence."""
        with persistence.session() as session:
            items = [ApplicationRead.model_validate(item) for item in list_applications(session)]
        return ApplicationList(items=items, total=len(items))

    @application.put(
        "/api/v1/metrics/{metric_date}",
        response_model=DailyMetricRead,
        status_code=status.HTTP_201_CREATED,
        responses={400: {"model": ErrorDetail}, 409: {"model": ErrorDetail}},
        tags=["metrics"],
    )
    def put_daily_metric(
        metric_date: date,
        request: DailyMetricUpdate,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=255, alias="Idempotency-Key"),
    ) -> DailyMetricRead | JSONResponse:
        """Apply a partial dated snapshot once under an explicit retry key."""
        try:
            with persistence.session() as session:
                result = set_daily_metric(session, metric_date, request, idempotency_key)
                payload = DailyMetricRead.model_validate(result.metric)
        except EmptyDailyMetricUpdateError:
            return error_response(
                "empty_metric_update", "At least one metric field is required", 400
            )
        except MetricIdempotencyConflictError:
            return error_response(
                "idempotency_conflict",
                "Idempotency-Key was already used for a different request",
                409,
            )
        response.status_code = 201 if result.created else 200
        return payload

    @application.get(
        "/api/v1/metrics/{metric_date}",
        response_model=DailyMetricRead,
        responses={404: {"model": ErrorDetail}},
        tags=["metrics"],
    )
    def get_metric(metric_date: date) -> DailyMetricRead | JSONResponse:
        """Return one daily snapshot by its calendar date."""
        try:
            with persistence.session() as session:
                return DailyMetricRead.model_validate(get_daily_metric(session, metric_date))
        except DailyMetricNotFoundError:
            return error_response("metric_not_found", "Daily metric does not exist", 404)

    @application.get("/api/v1/metrics", response_model=DailyMetricList, tags=["metrics"])
    def get_metrics(
        since: date | None = None, limit: int = Query(default=60, ge=1, le=366)
    ) -> DailyMetricList:
        """List bounded daily snapshots newest first."""
        with persistence.session() as session:
            items = [
                DailyMetricRead.model_validate(item)
                for item in list_daily_metrics(session, since=since, limit=limit)
            ]
        return DailyMetricList(items=items, total=len(items))

    @application.post(
        "/api/v1/people",
        response_model=PersonRead,
        status_code=status.HTTP_201_CREATED,
        responses={404: {"model": ErrorDetail}, 409: {"model": ErrorDetail}},
        tags=["people"],
    )
    def post_person(
        request: PersonCreate,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=255, alias="Idempotency-Key"),
    ) -> PersonRead | JSONResponse:
        """Persist one confirmed contact without running OSINT or messaging."""
        try:
            with persistence.session() as session:
                result = create_person(session, request, idempotency_key)
                payload = PersonRead.model_validate(result.person)
        except PersonIdempotencyConflictError:
            return error_response(
                "idempotency_conflict",
                "Idempotency-Key was already used for a different request",
                409,
            )
        except PersonAlreadyExistsError:
            return error_response("person_exists", "A Person with this identity exists", 409)
        except PersonCompanyNotFoundError:
            return error_response("company_not_found", "Company does not exist", 404)
        except PersonVacancyNotFoundError:
            return error_response("vacancy_not_found", "Vacancy does not exist", 404)
        except PersonCompanyMismatchError:
            return error_response(
                "person_company_mismatch", "Vacancy belongs to another Company", 409
            )
        response.status_code = 201 if result.created else 200
        return payload

    @application.get("/api/v1/people", response_model=PersonList, tags=["people"])
    def get_people() -> PersonList:
        """List confirmed contacts without exposing raw OSINT provider data."""
        with persistence.session() as session:
            items = [PersonRead.model_validate(item) for item in list_people(session)]
        return PersonList(items=items, total=len(items))

    @application.patch(
        "/api/v1/people/{person_id}",
        response_model=PersonRead,
        responses={404: {"model": ErrorDetail}},
        tags=["people"],
    )
    def patch_person_status(
        person_id: uuid.UUID, request: PersonStatusUpdate
    ) -> PersonRead | JSONResponse:
        """Change local contact workflow state without sending any message."""
        try:
            with persistence.session() as session:
                return PersonRead.model_validate(
                    update_person_status(session, person_id, request.status)
                )
        except PersonNotFoundError:
            return error_response("person_not_found", "Person does not exist", 404)

    @application.post(
        "/api/v1/hypotheses",
        response_model=HypothesisRead,
        status_code=status.HTTP_201_CREATED,
        responses={409: {"model": ErrorDetail}},
        tags=["hypotheses"],
    )
    def post_hypothesis(
        request: HypothesisCreate,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=255, alias="Idempotency-Key"),
    ) -> HypothesisRead | JSONResponse:
        """Persist one measurable active experiment under explicit retry metadata."""
        try:
            with persistence.session() as session:
                result = create_hypothesis(session, request, idempotency_key)
                payload = HypothesisRead.model_validate(result.hypothesis)
        except HypothesisIdempotencyConflictError:
            return error_response(
                "idempotency_conflict",
                "Idempotency-Key was already used for a different request",
                409,
            )
        except HypothesisAlreadyExistsError:
            return error_response(
                "hypothesis_exists", "A Hypothesis with this identity exists", 409
            )
        response.status_code = 201 if result.created else 200
        return payload

    @application.get("/api/v1/hypotheses", response_model=HypothesisList, tags=["hypotheses"])
    def get_hypotheses(
        status_filter: Annotated[HypothesisStatus | None, Query(alias="status")] = None,
    ) -> HypothesisList:
        """List experiments newest first with an optional lifecycle filter."""
        with persistence.session() as session:
            items = [
                HypothesisRead.model_validate(item)
                for item in list_hypotheses(session, status_filter)
            ]
        return HypothesisList(items=items, total=len(items))

    @application.post(
        "/api/v1/hypotheses/{hypothesis_id}/close",
        response_model=HypothesisRead,
        responses={404: {"model": ErrorDetail}, 409: {"model": ErrorDetail}},
        tags=["hypotheses"],
    )
    def post_hypothesis_close(
        hypothesis_id: uuid.UUID, request: HypothesisClose
    ) -> HypothesisRead | JSONResponse:
        """Close an active experiment with its first observed result."""
        try:
            with persistence.session() as session:
                return HypothesisRead.model_validate(
                    close_hypothesis(session, hypothesis_id, request.result)
                )
        except HypothesisNotFoundError:
            return error_response("hypothesis_not_found", "Hypothesis does not exist", 404)
        except HypothesisAlreadyClosedError:
            return error_response(
                "hypothesis_already_closed",
                "Closed Hypothesis result cannot be replaced",
                409,
            )

    @application.post(
        "/api/v1/assessments",
        response_model=AssessmentRead,
        status_code=status.HTTP_201_CREATED,
        responses={404: {"model": ErrorDetail}, 409: {"model": ErrorDetail}},
        tags=["assessments"],
    )
    def post_assessment(
        request: AssessmentCreate,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=255, alias="Idempotency-Key"),
    ) -> AssessmentRead | JSONResponse:
        """Persist one normalized scoring result without raw model output."""
        try:
            with persistence.session() as session:
                result = create_assessment(session, request, idempotency_key)
                payload = AssessmentRead.model_validate(result.assessment)
        except AssessmentIdempotencyConflictError:
            return error_response(
                "idempotency_conflict",
                "Idempotency-Key was already used for a different request",
                409,
            )
        except AssessmentAlreadyExistsError:
            return error_response(
                "assessment_exists", "An Assessment with this identity exists", 409
            )
        except AssessmentVacancyNotFoundError:
            return error_response("vacancy_not_found", "Vacancy does not exist", 404)
        response.status_code = 201 if result.created else 200
        return payload

    @application.get("/api/v1/assessments", response_model=AssessmentList, tags=["assessments"])
    def get_assessments(vacancy_id: uuid.UUID | None = None) -> AssessmentList:
        """List normalized results newest first, optionally for one Vacancy."""
        with persistence.session() as session:
            items = [
                AssessmentRead.model_validate(item)
                for item in list_assessments(session, vacancy_id)
            ]
        return AssessmentList(items=items, total=len(items))

    def _candidate_context_payload(session: object, context: object) -> CandidateContextRead:
        profile = getattr(context, "candidate_profile", None)
        version = getattr(context, "profile_version", None)
        link = getattr(context, "hh_resume_link", None)
        meta = resume_content_meta(session, context)  # type: ignore[arg-type]
        file_meta = resume_file_meta(
            session,  # type: ignore[arg-type]
            meta.resume_version_id if meta is not None else None,
        )
        return CandidateContextRead(
            candidate_profile=(
                CandidateProfileRead.model_validate(profile) if profile is not None else None
            ),
            profile_version=(
                ProfileVersionRead.model_validate(version) if version is not None else None
            ),
            hh_resume_link=(HhResumeLinkRead.model_validate(link) if link is not None else None),
            resume_content=(
                ResumeContentMetaRead(
                    content_state=meta.content_state,
                    resume_version_id=meta.resume_version_id,
                    external_resume_id=meta.external_resume_id,
                    captured_at=meta.captured_at,
                    source=meta.source,
                    schema_version=meta.schema_version,
                )
                if meta is not None
                else None
            ),
            resume_file=(
                ResumeFileMetaRead(
                    artifact_id=file_meta.artifact_id,
                    mime_type=file_meta.mime_type,
                    original_filename=file_meta.original_filename,
                    size_bytes=file_meta.size_bytes,
                    captured_at=file_meta.captured_at,
                    format_label=file_meta.format_label,
                )
                if file_meta is not None
                else None
            ),
        )

    @application.get(
        "/api/v1/candidate-context",
        response_model=CandidateContextRead,
        tags=["candidate-context"],
    )
    def get_candidate_context_route() -> CandidateContextRead:
        """Return operator CandidateProfile / ProfileVersion / HH link (or empty)."""
        with persistence.session() as session:
            return _candidate_context_payload(session, get_candidate_context(session))

    @application.put(
        "/api/v1/candidate-context/hh-resume-link",
        response_model=CandidateContextRead,
        responses={400: {"model": ErrorDetail}},
        tags=["candidate-context"],
    )
    def put_hh_resume_link(request: HhResumeLinkUpdate) -> CandidateContextRead | JSONResponse:
        """Create/update/clear ActiveHhResumeLink without deleting Core history."""
        try:
            with persistence.session() as session:
                context = set_hh_resume_link(session, request)
                return _candidate_context_payload(session, context)
        except HhResumeLinkValidationError:
            return error_response(
                "invalid_hh_resume_link",
                "external_resume_id must be a non-empty string or null with a valid status",
                400,
            )

    @application.post(
        "/api/v1/resume-versions",
        response_model=ResumeVersionIngestResultRead,
        responses={400: {"model": ErrorDetail}},
        tags=["resume-versions"],
    )
    def post_resume_version(
        request: ResumeVersionIngest,
    ) -> ResumeVersionIngestResultRead | JSONResponse:
        """Ingest fixture/HH snapshot: create immutable row or reuse identical hash."""
        try:
            with persistence.session() as session:
                result = ingest_resume_version(session, request)
                return ResumeVersionIngestResultRead(
                    created=result.created,
                    resume_version=ResumeVersionMetaRead.model_validate(result.resume_version),
                    candidate_context=_candidate_context_payload(session, result.candidate_context),
                )
        except ResumeVersionValidationError as error:
            return error_response("invalid_resume_version", str(error), 400)

    @application.get(
        "/api/v1/resume-versions/{resume_version_id}",
        response_model=ResumeVersionRead,
        responses={404: {"model": ErrorDetail}},
        tags=["resume-versions"],
    )
    def get_resume_version_route(
        resume_version_id: uuid.UUID,
    ) -> ResumeVersionRead | JSONResponse:
        """Return full normalized snapshot body for one ResumeVersion."""
        with persistence.session() as session:
            row = get_resume_version(session, resume_version_id)
            if row is None:
                return error_response(
                    "resume_version_not_found",
                    "ResumeVersion not found",
                    404,
                )
            return ResumeVersionRead.model_validate(row)

    @application.post(
        "/api/v1/resume-versions/{resume_version_id}/artifacts",
        response_model=ResumeArtifactIngestResultRead,
        responses={400: {"model": ErrorDetail}, 404: {"model": ErrorDetail}},
        tags=["resume-artifacts"],
    )
    async def post_resume_artifact(
        resume_version_id: uuid.UUID,
        file: UploadFile = File(...),
        captured_at: Annotated[str | None, Query()] = None,
    ) -> ResumeArtifactIngestResultRead | JSONResponse:
        """Store auxiliary HH resume file bytes linked to an existing ResumeVersion."""
        from datetime import datetime

        data = await file.read()
        mime_type = (file.content_type or "application/octet-stream").strip()
        filename = (file.filename or "resume").strip()
        captured: datetime | None = None
        if captured_at:
            captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        try:
            with persistence.session() as session:
                result = ingest_resume_artifact(
                    session,
                    artifact_root=ensure_artifact_root(),
                    resume_version_id=resume_version_id,
                    data=data,
                    mime_type=mime_type,
                    original_filename=filename,
                    captured_at=captured,
                )
                context = get_candidate_context(session)
                return ResumeArtifactIngestResultRead(
                    created=result.created,
                    blob_created=result.blob_created,
                    artifact=ResumeArtifactRead.model_validate(result.artifact),
                    candidate_context=_candidate_context_payload(session, context),
                )
        except ResumeArtifactValidationError as error:
            message = str(error)
            code = (
                "resume_version_not_found"
                if message == "resume_version not found"
                else "invalid_resume_artifact"
            )
            status_code = 404 if code == "resume_version_not_found" else 400
            return error_response(code, message, status_code)

    @application.get(
        "/api/v1/resume-artifacts/{artifact_id}",
        response_model=ResumeArtifactRead,
        responses={404: {"model": ErrorDetail}},
        tags=["resume-artifacts"],
    )
    def get_resume_artifact_route(artifact_id: uuid.UUID) -> ResumeArtifactRead | JSONResponse:
        """Return auxiliary resume file metadata."""
        with persistence.session() as session:
            row = get_resume_artifact(session, artifact_id)
            if row is None:
                return error_response("resume_artifact_not_found", "Resume artifact not found", 404)
            return ResumeArtifactRead.model_validate(row)

    @application.get(
        "/api/v1/resume-artifacts/{artifact_id}/download",
        response_model=None,
        responses={404: {"model": ErrorDetail}},
        tags=["resume-artifacts"],
    )
    def download_resume_artifact_route(artifact_id: uuid.UUID) -> Response | JSONResponse:
        """Stream exact stored resume file bytes."""
        with persistence.session() as session:
            row = get_resume_artifact(session, artifact_id)
            if row is None:
                return error_response("resume_artifact_not_found", "Resume artifact not found", 404)
            try:
                payload = load_resume_artifact_bytes(artifact_root, row)
            except ResumeArtifactValidationError:
                return error_response("resume_artifact_missing", "Resume artifact blob missing", 404)
        headers = {
            "Content-Disposition": content_disposition_attachment(row.original_filename),
        }
        return Response(content=payload, media_type=row.mime_type, headers=headers)

    @application.post(
        "/api/v1/search-profiles",
        response_model=SearchProfileRead,
        status_code=201,
        responses={400: {"model": ErrorDetail}},
        tags=["search-profiles"],
    )
    def post_search_profile(
        request: SearchProfileCreate,
    ) -> SearchProfileRead | JSONResponse:
        """Create one mutable SearchProfile with semantic criteria only."""
        try:
            with persistence.session() as session:
                profile = create_search_profile(session, request)
                return SearchProfileRead.model_validate(profile)
        except SearchValidationError as error:
            return error_response("invalid_search_profile", str(error), 400)

    @application.get(
        "/api/v1/search-profiles",
        response_model=SearchProfileList,
        tags=["search-profiles"],
    )
    def get_search_profiles() -> SearchProfileList:
        """List SearchProfiles newest first."""
        with persistence.session() as session:
            items = [
                SearchProfileRead.model_validate(item) for item in list_search_profiles(session)
            ]
        return SearchProfileList(items=items, total=len(items))

    @application.get(
        "/api/v1/search-profiles/{profile_id}",
        response_model=SearchProfileRead,
        responses={404: {"model": ErrorDetail}},
        tags=["search-profiles"],
    )
    def get_search_profile_route(profile_id: uuid.UUID) -> SearchProfileRead | JSONResponse:
        """Read one SearchProfile."""
        with persistence.session() as session:
            profile = get_search_profile(session, profile_id)
            if profile is None:
                return error_response("search_profile_not_found", "SearchProfile not found", 404)
            return SearchProfileRead.model_validate(profile)

    @application.patch(
        "/api/v1/search-profiles/{profile_id}",
        response_model=SearchProfileRead,
        responses={400: {"model": ErrorDetail}, 404: {"model": ErrorDetail}},
        tags=["search-profiles"],
    )
    def patch_search_profile(
        profile_id: uuid.UUID, request: SearchProfileUpdate
    ) -> SearchProfileRead | JSONResponse:
        """Update semantic SearchProfile fields without touching past SearchRun snapshots."""
        try:
            with persistence.session() as session:
                profile = update_search_profile(session, profile_id, request)
                return SearchProfileRead.model_validate(profile)
        except SearchProfileNotFoundError:
            return error_response("search_profile_not_found", "SearchProfile not found", 404)
        except SearchValidationError as error:
            return error_response("invalid_search_profile", str(error), 400)

    @application.post(
        "/api/v1/search-runs",
        response_model=SearchRunRead,
        status_code=201,
        responses={400: {"model": ErrorDetail}, 404: {"model": ErrorDetail}},
        tags=["search-runs"],
    )
    def post_search_run(request: SearchRunCreate) -> SearchRunRead | JSONResponse:
        """Start a running SearchRun with frozen criteria and execution snapshots."""
        try:
            with persistence.session() as session:
                run = start_search_run(session, request)
                return SearchRunRead.model_validate(run)
        except SearchProfileNotFoundError:
            return error_response("search_profile_not_found", "SearchProfile not found", 404)
        except SearchValidationError as error:
            return error_response("invalid_search_run", str(error), 400)

    @application.get(
        "/api/v1/search-runs",
        response_model=SearchRunList,
        tags=["search-runs"],
    )
    def get_search_runs(
        search_profile_id: uuid.UUID | None = None,
    ) -> SearchRunList:
        """List SearchRuns newest first."""
        with persistence.session() as session:
            items = [
                SearchRunRead.model_validate(item)
                for item in list_search_runs(session, search_profile_id=search_profile_id)
            ]
        return SearchRunList(items=items, total=len(items))

    @application.get(
        "/api/v1/search-runs/{run_id}",
        response_model=SearchRunRead,
        responses={404: {"model": ErrorDetail}},
        tags=["search-runs"],
    )
    def get_search_run_route(run_id: uuid.UUID) -> SearchRunRead | JSONResponse:
        """Read one SearchRun including snapshots and counters."""
        with persistence.session() as session:
            run = get_search_run(session, run_id)
            if run is None:
                return error_response("search_run_not_found", "SearchRun not found", 404)
            return SearchRunRead.model_validate(run)

    @application.post(
        "/api/v1/search-runs/{run_id}/items",
        response_model=SearchRunItemRead,
        status_code=201,
        responses={
            400: {"model": ErrorDetail},
            404: {"model": ErrorDetail},
            409: {"model": ErrorDetail},
        },
        tags=["search-runs"],
    )
    def post_search_run_item(
        run_id: uuid.UUID, request: SearchRunItemCreate
    ) -> SearchRunItemRead | JSONResponse:
        """Record one SearchRunItem outcome while the run is still running."""
        try:
            with persistence.session() as session:
                item = add_search_run_item(session, run_id, request)
                return SearchRunItemRead.model_validate(item)
        except SearchRunNotFoundError:
            return error_response("search_run_not_found", "SearchRun not found", 404)
        except SearchRunNotRunningError:
            return error_response(
                "search_run_not_running",
                "SearchRun is not running",
                409,
            )
        except VacancyNotFoundForItemError:
            return error_response("vacancy_not_found", "Vacancy does not exist", 404)
        except SearchRunItemConflictError:
            return error_response(
                "search_run_item_exists",
                "SearchRunItem for this source_external_id already exists",
                409,
            )
        except SearchRunItemValidationError as error:
            return error_response("invalid_search_run_item", str(error), 400)

    @application.get(
        "/api/v1/search-runs/{run_id}/items",
        response_model=SearchRunItemList,
        responses={404: {"model": ErrorDetail}},
        tags=["search-runs"],
    )
    def get_search_run_items(run_id: uuid.UUID) -> SearchRunItemList | JSONResponse:
        """List SearchRunItems for one SearchRun."""
        try:
            with persistence.session() as session:
                items = [
                    SearchRunItemRead.model_validate(item)
                    for item in list_search_run_items(session, run_id)
                ]
            return SearchRunItemList(items=items, total=len(items))
        except SearchRunNotFoundError:
            return error_response("search_run_not_found", "SearchRun not found", 404)

    @application.post(
        "/api/v1/search-runs/{run_id}/finalize",
        response_model=SearchRunRead,
        responses={
            400: {"model": ErrorDetail},
            404: {"model": ErrorDetail},
            409: {"model": ErrorDetail},
        },
        tags=["search-runs"],
    )
    def post_search_run_finalize(
        run_id: uuid.UUID, request: SearchRunFinalize
    ) -> SearchRunRead | JSONResponse:
        """Finalize a running SearchRun and recompute aggregate counters from items."""
        try:
            with persistence.session() as session:
                run = finalize_search_run(session, run_id, request)
                return SearchRunRead.model_validate(run)
        except SearchRunNotFoundError:
            return error_response("search_run_not_found", "SearchRun not found", 404)
        except SearchRunNotRunningError:
            return error_response(
                "search_run_not_running",
                "SearchRun is not running",
                409,
            )
        except SearchValidationError as error:
            return error_response("invalid_search_run_finalize", str(error), 400)

    return application


app = create_app()
