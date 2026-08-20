"""Versioned HTTP request and response schemas for the Vacancy slice."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from job_search_core.models import ApplicationResult, VacancyStatus


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


class ApplicationCreate(BaseModel):
    """Validated normalized application accepted from service consumers."""

    vacancy_id: uuid.UUID
    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    applied_at: datetime | None = None
    resume_version: str | None = Field(default=None, max_length=255)
    cover_letter_version: str | None = Field(default=None, max_length=255)
    cover_letter_text: str | None = None
    result: ApplicationResult | None = None
    next_action: str | None = Field(default=None, max_length=500)
    next_action_at: datetime | None = None


class ApplicationVacancyRead(BaseModel):
    """Minimal stable vacancy identity embedded in Application responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: VacancyStatus


class ApplicationRead(BaseModel):
    """Public persisted Application representation returned by API and CLI."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    applied_at: datetime
    resume_version: str | None
    cover_letter_version: str | None
    cover_letter_text: str | None
    result: ApplicationResult | None
    next_action: str | None
    next_action_at: datetime | None
    created_at: datetime
    updated_at: datetime
    vacancy: ApplicationVacancyRead


class ApplicationList(BaseModel):
    """Stable Application collection envelope with explicit total count."""

    items: list[ApplicationRead]
    total: int


class DailyMetricUpdate(BaseModel):
    """Validated partial daily snapshot accepted from trusted consumers."""

    views_total: int | None = Field(default=None, ge=0)
    views_new: int | None = Field(default=None, ge=0)
    applications: int | None = Field(default=None, ge=0)
    replies: int | None = Field(default=None, ge=0)
    invitations: int | None = Field(default=None, ge=0)
    rejections: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)


class DailyMetricRead(BaseModel):
    """Public persisted daily metric snapshot."""

    model_config = ConfigDict(from_attributes=True)

    metric_date: date
    views_total: int | None
    views_new: int | None
    applications: int | None
    replies: int | None
    invitations: int | None
    rejections: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DailyMetricList(BaseModel):
    """Stable metric collection envelope ordered newest first."""

    items: list[DailyMetricRead]
    total: int


class ErrorDetail(BaseModel):
    """Machine-readable error body shared by expected API failures."""

    code: str
    message: str
    trace_id: str
