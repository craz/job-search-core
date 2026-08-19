"""Synthetic database and ASGI helpers shared by Core test layers."""

from __future__ import annotations

import anyio
import httpx
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from job_search_core.app import create_app
from job_search_core.database import Database
from job_search_core.models import Base


def create_test_database() -> Database:
    """Create one in-memory SQLite database for contract-fast isolated tests."""
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Database("sqlite+pysqlite://", engine=engine)


class ApiClient:
    """Run each HTTP request against one isolated Core app through AnyIO."""

    def __init__(self, database: Database | None = None) -> None:
        """Bind subsequent requests to one persistent synthetic database."""
        self.database = database or create_test_database()

    def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        """Send one request through HTTPX's maintained asynchronous transport."""

        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=create_app(database=self.database))
            async with httpx.AsyncClient(
                transport=transport, base_url="http://core.test"
            ) as client:
                return await client.request(method, path, **kwargs)

        return anyio.run(send)

    def get(self, path: str) -> httpx.Response:
        """Send a GET request."""
        return self.request("GET", path)

    def post(
        self, path: str, *, json: dict[str, object], headers: dict[str, str]
    ) -> httpx.Response:
        """Send a JSON POST request with explicit headers."""
        return self.request("POST", path, json=json, headers=headers)

    def patch(self, path: str, *, json: dict[str, object]) -> httpx.Response:
        """Send a JSON PATCH request."""
        return self.request("PATCH", path, json=json)


def vacancy_payload(*, title: str = "Backend Engineer") -> dict[str, object]:
    """Return a public synthetic vacancy with no personal or provider credentials."""
    return {
        "company_name": "Example Labs",
        "company_external_id": "company-42",
        "source": "fixture",
        "external_id": "vacancy-100",
        "title": title,
        "url": "https://example.com/vacancies/100",
        "description": "Build a synthetic API fixture.",
    }


def create_fixture_vacancy(client: ApiClient, *, key: str = "fixture-vacancy") -> dict[str, object]:
    """Persist and return one synthetic Vacancy for related-resource tests."""
    response = client.post(
        "/api/v1/vacancies", json=vacancy_payload(), headers={"Idempotency-Key": key}
    )
    assert response.status_code == 201
    return response.json()


def application_payload(vacancy_id: object) -> dict[str, object]:
    """Return a normalized synthetic Application linked to a fixture Vacancy."""
    return {
        "vacancy_id": str(vacancy_id),
        "source": "fixture",
        "external_id": "application-100",
        "applied_at": "2026-08-19T09:30:00Z",
        "resume_version": "synthetic-v1",
        "cover_letter_version": "fixture-cover-v1",
        "cover_letter_text": "Synthetic application fixture.",
        "next_action": "Review synthetic reply",
        "next_action_at": "2026-08-20T09:30:00Z",
    }
