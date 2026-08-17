"""FastAPI factory for health and the versioned Vacancy HTTP contract.

Liveness has no dependencies. Readiness performs a database query and returns
503 when PostgreSQL is unavailable. Vacancy writes use an explicit idempotency
header and one transaction per request; consumers never receive database access.
"""

from __future__ import annotations

import uuid
from typing import Final

from fastapi import FastAPI, Header, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from job_search_core import __version__
from job_search_core.config import Settings
from job_search_core.database import Database
from job_search_core.schemas import ErrorDetail, VacancyCreate, VacancyList, VacancyRead
from job_search_core.vacancies import (
    IdempotencyConflictError,
    VacancyAlreadyExistsError,
    create_vacancy,
    list_vacancies,
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

    @application.get("/api/v1/vacancies", response_model=VacancyList, tags=["vacancies"])
    def get_vacancies() -> VacancyList:
        """List persisted vacancies without exposing storage implementation details."""
        with persistence.session() as session:
            items = [VacancyRead.model_validate(item) for item in list_vacancies(session)]
        return VacancyList(items=items, total=len(items))

    return application


app = create_app()
