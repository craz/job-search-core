"""Relational persistence models owned exclusively by Job Search Core."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, Uuid
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
