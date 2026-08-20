"""Create normalized Assessment persistence.

Revision ID: 20260820_06
Revises: 20260820_05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_06"
down_revision: str | None = "20260820_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create normalized scoring results linked to Core Vacancies."""
    op.create_table(
        "assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum("APPLY", "MAYBE", "SKIP", name="assessment_verdict", native_enum=False),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk", sa.Text(), nullable=True),
        sa.Column("action", sa.String(1000), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("prompt_version", sa.String(255), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100", name="ck_assessments_relevance_score"
        ),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_assessments_idempotency_key"),
        sa.UniqueConstraint("source", "external_id", name="uq_assessments_source_external_id"),
    )
    op.create_index(op.f("ix_assessments_vacancy_id"), "assessments", ["vacancy_id"])


def downgrade() -> None:
    """Remove normalized results without changing their Vacancies."""
    op.drop_index(op.f("ix_assessments_vacancy_id"), table_name="assessments")
    op.drop_table("assessments")
