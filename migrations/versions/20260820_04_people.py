"""Create confirmed Person persistence.

Revision ID: 20260820_04
Revises: 20260820_03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_04"
down_revision: str | None = "20260820_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create confirmed contacts with controlled workflow and ownership links."""
    op.create_table(
        "people",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "HIRING_MANAGER",
                "RECRUITER",
                "REFERRAL",
                "PEER",
                name="person_role",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "RESEARCHING",
                "CONTACTED",
                "REPLIED",
                "DROPPED",
                name="person_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_people_confidence",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_people_idempotency_key"),
        sa.UniqueConstraint("source", "external_id", name="uq_people_source_external_id"),
    )
    op.create_index(op.f("ix_people_company_id"), "people", ["company_id"], unique=False)
    op.create_index(op.f("ix_people_vacancy_id"), "people", ["vacancy_id"], unique=False)


def downgrade() -> None:
    """Remove confirmed contacts without changing Company or Vacancy."""
    op.drop_index(op.f("ix_people_vacancy_id"), table_name="people")
    op.drop_index(op.f("ix_people_company_id"), table_name="people")
    op.drop_table("people")
