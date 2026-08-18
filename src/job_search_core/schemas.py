"""Versioned HTTP request and response schemas for the Vacancy slice."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from job_search_core.models import VacancyStatus


class VacancyCreate(BaseModel):
    """Validated normalized vacancy accepted from trusted service consumers."""

    company_name: str = Field(min_length=1, max_length=255)
    company_external_id: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    description: str | None = None


class CompanyRead(BaseModel):
    """Public company fields embedded in a vacancy response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source: str
    external_id: str


class VacancyRead(BaseModel):
    """Public persisted vacancy representation returned by API and CLI."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    title: str
    url: str
    description: str | None
    status: VacancyStatus
    created_at: datetime
    updated_at: datetime
    company: CompanyRead


class VacancyList(BaseModel):
    """Stable collection envelope with an explicit total count."""

    items: list[VacancyRead]
    total: int


class VacancyStatusUpdate(BaseModel):
    """Controlled status transition requested by an API consumer."""

    status: VacancyStatus


class ErrorDetail(BaseModel):
    """Machine-readable error body shared by expected API failures."""

    code: str
    message: str
    trace_id: str
