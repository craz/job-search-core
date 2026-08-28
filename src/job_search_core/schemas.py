"""Versioned HTTP request and response schemas for the Vacancy slice."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from job_search_core.models import (
    ApplicationResult,
    AssessmentScoringMode,
    AssessmentVerdict,
    HhResumeLinkStatus,
    HypothesisStatus,
    PersonRole,
    PersonStatus,
    SearchRunAcquisitionKind,
    SearchRunItemOutcome,
    SearchRunStatus,
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


class VacancyIngest(BaseModel):
    """Provider-neutral source vacancy for identity-safe Core upsert (R2.2.3)."""

    company_name: str = Field(min_length=1, max_length=255)
    company_external_id: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    description: str | None = None
    salary_text: str | None = Field(default=None, max_length=500)
    area_text: str | None = Field(default=None, max_length=500)
    employment_text: str | None = Field(default=None, max_length=255)
    schedule_text: str | None = Field(default=None, max_length=255)
    work_format_text: str | None = Field(default=None, max_length=255)
    experience_text: str | None = Field(default=None, max_length=255)
    published_text: str | None = Field(default=None, max_length=255)
    archived: bool | None = None
    source_published_at: datetime | None = None


class VacancyIngestOutcome(StrEnum):
    """Ingestion outcome for one (source, external_id) upsert."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


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
    salary_text: str | None = None
    area_text: str | None = None
    employment_text: str | None = None
    schedule_text: str | None = None
    work_format_text: str | None = None
    experience_text: str | None = None
    published_text: str | None = None
    archived: bool | None = None
    source_published_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    content_hash: str | None = None
    status: VacancyStatus
    created_at: datetime
    updated_at: datetime
    company: CompanyRead


class VacancyIngestResult(BaseModel):
    """Upsert response: outcome + persisted vacancy (same UUID across updates)."""

    outcome: VacancyIngestOutcome
    vacancy: VacancyRead


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


class AssessmentDetail(BaseModel):
    """Structured v1 explanation stored in Assessment.detail JSONB."""

    reason: str = Field(min_length=1, max_length=4000)
    risk: str | None = Field(default=None, max_length=4000)
    action: str = Field(min_length=1, max_length=1000)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    deterministic_signals: list[str] = Field(default_factory=list)


class AssessmentCreate(BaseModel):
    """Validated normalized result accepted from a scoring producer."""

    vacancy_id: uuid.UUID
    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    relevance_score: int = Field(ge=0, le=100)
    verdict: AssessmentVerdict
    reason: str | None = Field(default=None, min_length=1, max_length=4000)
    risk: str | None = Field(default=None, max_length=4000)
    action: str | None = Field(default=None, min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=255)
    prompt_version: str = Field(min_length=1, max_length=255)
    assessed_at: datetime
    schema_version: int | None = None
    detail: AssessmentDetail | None = None
    vacancy_content_hash: str | None = Field(default=None, min_length=64, max_length=64)
    profile_version_id: uuid.UUID | None = None
    resume_version_id: uuid.UUID | None = None
    candidate_context_hash: str | None = Field(default=None, min_length=64, max_length=64)
    scoring_mode: AssessmentScoringMode | None = None
    policy_id: str | None = Field(default=None, min_length=1, max_length=64)
    policy_version: int | None = Field(default=None, ge=1)
    policy_hash: str | None = Field(default=None, min_length=64, max_length=64)
    model_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    scoring_identity_hash: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_scoring_contract(self) -> AssessmentCreate:
        if self.schema_version == 1:
            required: list[tuple[str, object | None]] = [
                ("vacancy_content_hash", self.vacancy_content_hash),
                ("profile_version_id", self.profile_version_id),
                ("resume_version_id", self.resume_version_id),
                ("candidate_context_hash", self.candidate_context_hash),
                ("scoring_mode", self.scoring_mode),
                ("policy_id", self.policy_id),
                ("policy_version", self.policy_version),
                ("policy_hash", self.policy_hash),
                ("model_fingerprint", self.model_fingerprint),
                ("scoring_identity_hash", self.scoring_identity_hash),
                ("detail", self.detail),
            ]
            missing = [name for name, value in required if value is None]
            if missing:
                message = f"schema_version=1 requires: {', '.join(missing)}"
                raise ValueError(message)
            if self.detail is not None:
                if self.reason is not None and self.reason.strip() != self.detail.reason.strip():
                    raise ValueError("schema_version=1: top-level reason must match detail")
                if self.action is not None and self.action.strip() != self.detail.action.strip():
                    raise ValueError("schema_version=1: top-level action must match detail")
                if self.risk is not None and self.risk != self.detail.risk:
                    raise ValueError("schema_version=1: top-level risk must match detail")
            return self
        if not self.reason or not self.action:
            raise ValueError("legacy Assessment requires reason and action")
        return self


class AssessmentRead(BaseModel):
    """Public normalized result with stable Vacancy identity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    relevance_score: int
    verdict: AssessmentVerdict
    reason: str | None
    risk: str | None
    action: str | None
    model: str
    prompt_version: str
    assessed_at: datetime
    created_at: datetime
    schema_version: int | None = None
    detail: AssessmentDetail | None = None
    vacancy_content_hash: str | None = None
    profile_version_id: uuid.UUID | None = None
    resume_version_id: uuid.UUID | None = None
    candidate_context_hash: str | None = None
    scoring_mode: AssessmentScoringMode | None = None
    policy_id: str | None = None
    policy_version: int | None = None
    policy_hash: str | None = None
    model_fingerprint: str | None = None
    scoring_identity_hash: str | None = None
    vacancy: ApplicationVacancyRead

    @field_validator("detail", mode="before")
    @classmethod
    def parse_detail(cls, value: object) -> AssessmentDetail | None:
        if value is None:
            return None
        if isinstance(value, AssessmentDetail):
            return value
        if isinstance(value, dict):
            return AssessmentDetail.model_validate(value)
        raise TypeError("detail must be an object or mapping")


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


class SearchSalaryCriteria(BaseModel):
    """Optional salary bounds inside SearchProfile semantic criteria."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_amount: int | None = Field(default=None, alias="from", ge=0)
    to_amount: int | None = Field(default=None, alias="to", ge=0)
    currency: str | None = Field(default=None, min_length=1, max_length=16)


class SearchProfileCreate(BaseModel):
    """Create a mutable SearchProfile with semantic criteria only."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, max_length=255)
    text: str = Field(min_length=1, max_length=1000)
    area_id: str | None = Field(default=None, max_length=64)
    salary: SearchSalaryCriteria | None = None
    experience: str | None = Field(default=None, max_length=64)
    employment: str | None = Field(default=None, max_length=64)
    schedule: str | None = Field(default=None, max_length=64)
    search_field: str | None = Field(default=None, max_length=64)
    only_with_salary: bool | None = None


class SearchProfileUpdate(BaseModel):
    """Partial update of SearchProfile semantic criteria."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, max_length=255)
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    area_id: str | None = Field(default=None, max_length=64)
    salary: SearchSalaryCriteria | None = None
    experience: str | None = Field(default=None, max_length=64)
    employment: str | None = Field(default=None, max_length=64)
    schedule: str | None = Field(default=None, max_length=64)
    search_field: str | None = Field(default=None, max_length=64)
    only_with_salary: bool | None = None


class SearchProfileRead(BaseModel):
    """Public SearchProfile representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str | None
    text: str
    area_id: str | None
    salary: dict[str, object] | None
    experience: str | None
    employment: str | None
    schedule: str | None
    search_field: str | None
    only_with_salary: bool | None
    created_at: datetime
    updated_at: datetime


class SearchProfileList(BaseModel):
    """Collection envelope for SearchProfile."""

    items: list[SearchProfileRead]
    total: int


class SearchExecutionSettings(BaseModel):
    """Runtime acquisition knobs stored only on SearchRun.execution_snapshot."""

    model_config = ConfigDict(extra="allow")

    order: str = Field(default="publication_time", min_length=1, max_length=64)
    page_size: int | None = Field(default=None, ge=1, le=100)
    max_pages: int = Field(default=5, ge=1, le=100)


class SearchRunCreate(BaseModel):
    """Start a SearchRun with explicit acquisition kind and execution settings."""

    model_config = ConfigDict(extra="forbid")

    acquisition_kind: SearchRunAcquisitionKind = SearchRunAcquisitionKind.PROFILE_SEARCH
    search_profile_id: uuid.UUID | None = None
    execution: SearchExecutionSettings | None = None
    candidate_context_snapshot: dict[str, object] | None = None


class SearchRunRead(BaseModel):
    """Public SearchRun including immutable snapshots and aggregate counters."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    search_profile_id: uuid.UUID | None
    acquisition_kind: SearchRunAcquisitionKind
    source: str
    criteria_snapshot: dict[str, object]
    execution_snapshot: dict[str, object]
    candidate_context_snapshot: dict[str, object] | None
    status: SearchRunStatus
    started_at: datetime
    finished_at: datetime | None
    found_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    error_count: int
    source_total: int | None = None
    error_code: str | None
    recovery_hint: str | None


class SearchRunList(BaseModel):
    """Collection envelope for SearchRun."""

    items: list[SearchRunRead]
    total: int


class SearchRunItemCreate(BaseModel):
    """Record one discovered source vacancy outcome inside a running SearchRun."""

    model_config = ConfigDict(extra="forbid")

    source_external_id: str = Field(min_length=1, max_length=255)
    outcome: SearchRunItemOutcome
    vacancy_id: uuid.UUID | None = None
    discovered_at: datetime | None = None
    page: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, max_length=128)
    error_detail: str | None = Field(default=None, max_length=1000)


class SearchRunItemRead(BaseModel):
    """Public SearchRunItem provenance row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    search_run_id: uuid.UUID
    source_external_id: str
    vacancy_id: uuid.UUID | None
    outcome: SearchRunItemOutcome
    discovered_at: datetime | None
    page: int | None
    error_code: str | None
    error_detail: str | None


class SearchRunItemList(BaseModel):
    """Collection envelope for SearchRunItem."""

    items: list[SearchRunItemRead]
    total: int


class SearchRunFinalize(BaseModel):
    """Move a running SearchRun into a terminal status."""

    model_config = ConfigDict(extra="forbid")

    status: SearchRunStatus
    error_code: str | None = Field(default=None, max_length=128)
    recovery_hint: str | None = Field(default=None, max_length=500)
    source_total: int | None = Field(default=None, ge=0)


class ErrorDetail(BaseModel):
    """Machine-readable error body shared by expected API failures."""

    code: str
    message: str
    trace_id: str
