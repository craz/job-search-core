"""FastAPI application factory and infrastructure health contracts.

This scaffold exposes only liveness, readiness and component metadata. Domain
resources and PostgreSQL readiness are intentionally deferred to the first Core
vertical slice. Keeping an application factory makes tests independent and avoids
global configuration or database side effects during import.
"""

from typing import Final

from fastapi import FastAPI
from pydantic import BaseModel

from job_search_core import __version__

COMPONENT_NAME: Final = "job-search-core"


class HealthResponse(BaseModel):
    """Stable machine-readable health response shared by probes and operators."""

    status: str
    component: str
    version: str


def component_info() -> HealthResponse:
    """Return immutable process metadata without performing external I/O."""
    return HealthResponse(status="ok", component=COMPONENT_NAME, version=__version__)


def create_app() -> FastAPI:
    """Build an isolated ASGI application with versioned platform endpoints.

    Liveness proves the Python process can serve requests. Readiness currently has
    the same result because the scaffold owns no external dependency. Once Core
    owns PostgreSQL, readiness must verify database connectivity while liveness
    must remain independent of the database to avoid destructive restart loops.
    """
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

    @application.get("/health/ready", response_model=HealthResponse, tags=["health"])
    def readiness() -> HealthResponse:
        """Report readiness; dependency checks enter with PostgreSQL ownership."""
        return component_info()

    return application


app = create_app()
