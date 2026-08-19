"""Create normalized Application persistence.

Revision ID: 20260819_02
Revises: 20260817_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_02"
down_revision: str | None = "20260817_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Application rows with external identity and idempotency constraints."""
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resume_version", sa.String(length=255), nullable=True),
        sa.Column("cover_letter_version", sa.String(length=255), nullable=True),
        sa.Column("cover_letter_text", sa.Text(), nullable=True),
        sa.Column(
            "result",
            sa.Enum(
                "REPLY",
                "INTERVIEW",
                "REJECTED",
                "OFFER",
                name="application_result",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("next_action", sa.String(length=500), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_applications_idempotency_key"),
        sa.UniqueConstraint("source", "external_id", name="uq_applications_source_external_id"),
    )
    op.create_index(
        op.f("ix_applications_vacancy_id"), "applications", ["vacancy_id"], unique=False
    )


def downgrade() -> None:
    """Remove Application persistence without changing Vacancy or Company."""
    op.drop_index(op.f("ix_applications_vacancy_id"), table_name="applications")
    op.drop_table("applications")
