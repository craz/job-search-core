"""Versioned HTTP request and response schemas for the Vacancy slice."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from job_search_core.models import (
    ApplicationResult,
    AssessmentVerdict,
    HhResumeLinkStatus,
    HypothesisStatus,
    PersonRole,
    PersonStatus,
    VacancyStatus,
)


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
    website_url: str | None


class CompanyWebsiteUpdate(BaseModel):
    """Confirmed normalized official website supplied by a trusted integration."""

    website_url: HttpUrl


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


class PersonCreate(BaseModel):
    """Validated confirmed contact accepted from trusted consumers."""

    company_id: uuid.UUID
    vacancy_id: uuid.UUID | None = None
    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: PersonRole
    title: str | None = Field(default=None, max_length=500)
    url: HttpUrl | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = Field(default=None, max_length=4000)


class PersonStatusUpdate(BaseModel):
    """Controlled contact workflow transition requested by a consumer."""

    status: PersonStatus


class PersonRead(BaseModel):
    """Public confirmed contact with stable Company and Vacancy identity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    full_name: str
    role: PersonRole
    title: str | None
    url: str | None
    confidence: float | None
    status: PersonStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    company: CompanyRead
    vacancy: ApplicationVacancyRead | None


class PersonList(BaseModel):
    """Stable confirmed-contact collection envelope."""

    items: list[PersonRead]
    total: int


class HypothesisCreate(BaseModel):
    """Validated measurable experiment accepted from trusted consumers."""

    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    test_size: int | None = Field(default=None, gt=0)
    metric: str | None = Field(default=None, max_length=500)


class HypothesisClose(BaseModel):
    """Explicit observed result required to close an active experiment."""

    result: str = Field(min_length=1, max_length=4000)


class HypothesisRead(BaseModel):
    """Public persisted experiment and its lifecycle state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    title: str
    description: str | None
    test_size: int | None
    metric: str | None
    status: HypothesisStatus
    result: str | None
    created_at: datetime
    updated_at: datetime


class HypothesisList(BaseModel):
    """Stable experiment collection envelope."""

    items: list[HypothesisRead]
    total: int


class AssessmentCreate(BaseModel):
    """Validated normalized result accepted from a scoring producer."""

    vacancy_id: uuid.UUID
    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    relevance_score: int = Field(ge=0, le=100)
    verdict: AssessmentVerdict
    reason: str = Field(min_length=1, max_length=4000)
    risk: str | None = Field(default=None, max_length=4000)
    action: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=255)
    prompt_version: str = Field(min_length=1, max_length=255)
    assessed_at: datetime


class AssessmentRead(BaseModel):
    """Public normalized result with stable Vacancy identity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    relevance_score: int
    verdict: AssessmentVerdict
    reason: str
    risk: str | None
    action: str
    model: str
    prompt_version: str
    assessed_at: datetime
    created_at: datetime
    vacancy: ApplicationVacancyRead


class AssessmentList(BaseModel):
    """Stable normalized Assessment collection envelope."""

    items: list[AssessmentRead]
    total: int


class HhResumeLinkUpdate(BaseModel):
    """Set or clear the local HH resume link on the operator ProfileVersion."""

    external_resume_id: str | None
    title: str | None = None
    status: HhResumeLinkStatus | None = None


class CandidateProfileRead(BaseModel):
    """Public single-operator CandidateProfile identity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class ProfileVersionRead(BaseModel):
    """Public ProfileVersion used as HH linkage target."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    created_at: datetime


class HhResumeLinkRead(BaseModel):
    """Public ActiveHhResumeLink (source=hh)."""

    model_config = ConfigDict(from_attributes=True)

    source: str
    external_resume_id: str | None
    title: str | None
    selected_at: datetime | None
    status: HhResumeLinkStatus
    updated_at: datetime


class ResumeContentMetaRead(BaseModel):
    """ResumeVersion metadata only (no CV body) for candidate-context."""

    content_state: str
    resume_version_id: uuid.UUID | None = None
    external_resume_id: str | None = None
    captured_at: datetime | None = None
    source: str | None = None
    schema_version: int | None = None


class CandidateContextRead(BaseModel):
    """Operator candidate context: profile, version, HH link, resume content meta."""

    candidate_profile: CandidateProfileRead | None
    profile_version: ProfileVersionRead | None
    hh_resume_link: HhResumeLinkRead | None
    resume_content: ResumeContentMetaRead | None = None


class ResumeVersionIngest(BaseModel):
    """Fixture / HH-sync ingest of one resume content snapshot."""

    source: str = "hh"
    external_resume_id: str
    content: dict[str, object]
    transport: str = "fixture"
    extractor_version: str | None = None
    captured_at: datetime | None = None


class ResumeVersionMetaRead(BaseModel):
    """Public ResumeVersion identity and provenance without body."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_resume_id: str
    schema_version: int
    content_hash: str
    captured_at: datetime
    transport: str
    extractor_version: str | None


class ResumeVersionRead(ResumeVersionMetaRead):
    """Full ResumeVersion including normalized JSON content."""

    content: dict[str, object]


class ResumeVersionIngestResultRead(BaseModel):
    """Ingest response: whether a new immutable row was created."""

    created: bool
    resume_version: ResumeVersionMetaRead
    candidate_context: CandidateContextRead


class ErrorDetail(BaseModel):
    """Machine-readable error body shared by expected API failures."""

    code: str
    message: str
    trace_id: str
