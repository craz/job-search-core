"""Relational persistence models owned exclusively by Job Search Core."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
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
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(VacancyStatus, name="vacancy_status", native_enum=False),
        default=VacancyStatus.NEW,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
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
