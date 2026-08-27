"""Relational persistence models owned exclusively by Job Search Core."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return an aware UTC timestamp for machine events."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative metadata root for Core-owned tables and Alembic."""


class VacancyStatus(StrEnum):
    """Controlled first-slice states for a vacancy in the job-search funnel."""

    NEW = "new"
    REVIEWING = "reviewing"
    REJECTED = "rejected"
    SHORTLISTED = "shortlisted"


class ApplicationResult(StrEnum):
    """Controlled observed outcomes for a submitted job application."""

    REPLY = "reply"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"


class PersonRole(StrEnum):
    """Controlled professional relationship roles for confirmed contacts."""

    HIRING_MANAGER = "hiring_manager"
    RECRUITER = "recruiter"
    REFERRAL = "referral"
    PEER = "peer"


class PersonStatus(StrEnum):
    """Controlled contact-workflow states without implying external delivery."""

    NEW = "new"
    RESEARCHING = "researching"
    CONTACTED = "contacted"
    REPLIED = "replied"
    DROPPED = "dropped"


class HypothesisStatus(StrEnum):
    """Controlled lifecycle states for a job-search experiment."""

    ACTIVE = "active"
    DONE = "done"


class AssessmentVerdict(StrEnum):
    """Controlled recommended actions produced by a scoring result."""

    APPLY = "apply"
    MAYBE = "maybe"
    SKIP = "skip"


class Company(Base):
    """Normalized employer identity referenced by vacancies."""

    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_companies_source_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    vacancies: Mapped[list[Vacancy]] = relationship(back_populates="company")
    people: Mapped[list[Person]] = relationship(back_populates="company")


class Vacancy(Base):
    """Normalized vacancy with source identity and idempotent creation metadata."""

    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_vacancies_source_external_id"),
        UniqueConstraint("idempotency_key", name="uq_vacancies_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    salary_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    area_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    employment_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schedule_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_format_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archived: Mapped[bool | None] = mapped_column(Boolean(), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(VacancyStatus, name="vacancy_status", native_enum=False),
        default=VacancyStatus.NEW,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    company: Mapped[Company] = relationship(back_populates="vacancies")
    applications: Mapped[list[Application]] = relationship(back_populates="vacancy")
    people: Mapped[list[Person]] = relationship(back_populates="vacancy")
    assessments: Mapped[list[Assessment]] = relationship(back_populates="vacancy")


class Application(Base):
    """Normalized application event linked to one Core-owned vacancy."""

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_applications_source_external_id"),
        UniqueConstraint("idempotency_key", name="uq_applications_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vacancies.id", ondelete="RESTRICT"), index=True
    )
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resume_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_letter_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_letter_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result: Mapped[ApplicationResult | None] = mapped_column(
        Enum(ApplicationResult, name="application_result", native_enum=False), nullable=True
    )
    next_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    vacancy: Mapped[Vacancy] = relationship(back_populates="applications")


class DailyMetric(Base):
    """One normalized job-search activity snapshot for a calendar date."""

    __tablename__ = "daily_metrics"
    __table_args__ = (
        CheckConstraint("views_total IS NULL OR views_total >= 0", name="ck_metrics_views_total"),
        CheckConstraint("views_new IS NULL OR views_new >= 0", name="ck_metrics_views_new"),
        CheckConstraint(
            "applications IS NULL OR applications >= 0", name="ck_metrics_applications"
        ),
        CheckConstraint("replies IS NULL OR replies >= 0", name="ck_metrics_replies"),
        CheckConstraint("invitations IS NULL OR invitations >= 0", name="ck_metrics_invitations"),
        CheckConstraint("rejections IS NULL OR rejections >= 0", name="ck_metrics_rejections"),
    )

    metric_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    views_total: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    views_new: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    applications: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    replies: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    invitations: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    rejections: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DailyMetricRequest(Base):
    """Processed metric write key preventing delayed retries from reapplying updates."""

    __tablename__ = "daily_metric_requests"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_metric_requests_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_date: Mapped[date] = mapped_column(
        Date(), ForeignKey("daily_metrics.metric_date", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Person(Base):
    """Confirmed professional contact linked to a Core Company and optional Vacancy."""

    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_people_source_external_id"),
        UniqueConstraint("idempotency_key", name="uq_people_idempotency_key"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_people_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[PersonRole] = mapped_column(
        Enum(PersonRole, name="person_role", native_enum=False)
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[PersonStatus] = mapped_column(
        Enum(PersonStatus, name="person_status", native_enum=False), default=PersonStatus.NEW
    )
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    company: Mapped[Company] = relationship(back_populates="people")
    vacancy: Mapped[Vacancy | None] = relationship(back_populates="people")


class Hypothesis(Base):
    """Measurable job-search experiment with an explicit closing result."""

    __tablename__ = "hypotheses"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_hypotheses_source_external_id"),
        UniqueConstraint("idempotency_key", name="uq_hypotheses_idempotency_key"),
        CheckConstraint("test_size IS NULL OR test_size > 0", name="ck_hypotheses_test_size"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    test_size: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    metric: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[HypothesisStatus] = mapped_column(
        Enum(HypothesisStatus, name="hypothesis_status", native_enum=False),
        default=HypothesisStatus.ACTIVE,
    )
    result: Mapped[str | None] = mapped_column(Text(), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Assessment(Base):
    """Normalized scoring result linked to one Core-owned Vacancy."""

    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_assessments_source_external_id"),
        UniqueConstraint("idempotency_key", name="uq_assessments_idempotency_key"),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100",
            name="ck_assessments_relevance_score",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vacancies.id", ondelete="RESTRICT"), index=True
    )
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    relevance_score: Mapped[int] = mapped_column(Integer())
    verdict: Mapped[AssessmentVerdict] = mapped_column(
        Enum(AssessmentVerdict, name="assessment_verdict", native_enum=False)
    )
    reason: Mapped[str] = mapped_column(Text())
    risk: Mapped[str | None] = mapped_column(Text(), nullable=True)
    action: Mapped[str] = mapped_column(String(1000))
    model: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(255))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    vacancy: Mapped[Vacancy] = relationship(back_populates="assessments")


class HhResumeLinkStatus(StrEnum):
    """Lifecycle of the local link from ProfileVersion to an HH resume id."""

    ACTIVE = "active"
    CLEARED = "cleared"
    STALE = "stale"


class CandidateProfile(Base):
    """Single-operator local candidate identity (not Person / OSINT contact)."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        UniqueConstraint("singleton_key", name="uq_candidate_profiles_singleton_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_key: Mapped[str] = mapped_column(String(64), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    versions: Mapped[list[ProfileVersion]] = relationship(back_populates="candidate_profile")


class ProfileVersion(Base):
    """Versioned local candidate context used as HH resume linkage target (R1.5)."""

    __tablename__ = "profile_versions"
    __table_args__ = (
        UniqueConstraint(
            "candidate_profile_id",
            "label",
            name="uq_profile_versions_profile_label",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidate_profiles.id", ondelete="RESTRICT"),
        index=True,
    )
    label: Mapped[str] = mapped_column(String(255), default="r1-default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="versions")
    hh_resume_link: Mapped[ActiveHhResumeLink | None] = relationship(
        back_populates="profile_version", uselist=False
    )
    resume_versions: Mapped[list[ResumeVersion]] = relationship(back_populates="profile_version")


class ActiveHhResumeLink(Base):
    """Local link of one ProfileVersion to an HH external resume id."""

    __tablename__ = "active_hh_resume_links"
    __table_args__ = (
        UniqueConstraint("profile_version_id", name="uq_active_hh_resume_links_profile_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profile_versions.id", ondelete="RESTRICT"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64), default="hh")
    external_resume_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[HhResumeLinkStatus] = mapped_column(
        Enum(HhResumeLinkStatus, name="hh_resume_link_status", native_enum=False),
        default=HhResumeLinkStatus.CLEARED,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    profile_version: Mapped[ProfileVersion] = relationship(back_populates="hh_resume_link")


class ResumeVersion(Base):
    """Immutable local resume content snapshot (R2.1.1). Never update ``content``."""

    __tablename__ = "resume_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profile_versions.id", ondelete="RESTRICT"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64), default="hh")
    external_resume_id: Mapped[str] = mapped_column(String(255))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    transport: Mapped[str] = mapped_column(String(64), default="browser_readonly")
    extractor_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_version: Mapped[ProfileVersion] = relationship(back_populates="resume_versions")


class SearchRunStatus(StrEnum):
    """Lifecycle of one SearchRun execution."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SearchRunAcquisitionKind(StrEnum):
    """How vacancies were discovered for one SearchRun."""

    PROFILE_SEARCH = "profile_search"
    RESUME_SUITABLE = "resume_suitable"


class SearchRunItemOutcome(StrEnum):
    """Ingestion outcome for one source vacancy inside a SearchRun."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    ERROR = "error"


class SearchProfile(Base):
    """Mutable semantic search intent (R2.2.1). No execution/runtime knobs."""

    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(String(1000))
    area_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salary: Mapped[dict[str, object] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    experience: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    search_field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    only_with_salary: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    runs: Mapped[list[SearchRun]] = relationship(back_populates="search_profile")


class SearchRun(Base):
    """One search execution with immutable criteria and execution snapshots."""

    __tablename__ = "search_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("search_profiles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    acquisition_kind: Mapped[SearchRunAcquisitionKind] = mapped_column(
        Enum(
            SearchRunAcquisitionKind,
            name="search_run_acquisition_kind",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=SearchRunAcquisitionKind.PROFILE_SEARCH,
    )
    source: Mapped[str] = mapped_column(String(64), default="hh")
    criteria_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    execution_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    candidate_context_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    status: Mapped[SearchRunStatus] = mapped_column(
        Enum(
            SearchRunStatus,
            name="search_run_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=SearchRunStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    source_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recovery_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    search_profile: Mapped[SearchProfile | None] = relationship(back_populates="runs")
    items: Mapped[list[SearchRunItem]] = relationship(back_populates="search_run")


class SearchRunItem(Base):
    """Per-source-vacancy provenance row for one SearchRun."""

    __tablename__ = "search_run_items"
    __table_args__ = (
        UniqueConstraint(
            "search_run_id",
            "source_external_id",
            name="uq_search_run_items_run_external",
        ),
        CheckConstraint(
            "outcome = 'error' OR vacancy_id IS NOT NULL",
            name="ck_search_run_items_vacancy_required",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        index=True,
    )
    source_external_id: Mapped[str] = mapped_column(String(255))
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    outcome: Mapped[SearchRunItemOutcome] = mapped_column(
        Enum(
            SearchRunItemOutcome,
            name="search_run_item_outcome",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    search_run: Mapped[SearchRun] = relationship(back_populates="items")
    vacancy: Mapped[Vacancy | None] = relationship()
