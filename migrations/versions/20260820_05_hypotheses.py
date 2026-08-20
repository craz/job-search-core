"""Create measurable Hypothesis persistence.

Revision ID: 20260820_05
Revises: 20260820_04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_05"
down_revision: str | None = "20260820_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create replay-safe experiments with controlled lifecycle state."""
    op.create_table(
        "hypotheses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("test_size", sa.Integer(), nullable=True),
        sa.Column("metric", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "DONE", name="hypothesis_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("test_size IS NULL OR test_size > 0", name="ck_hypotheses_test_size"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_hypotheses_idempotency_key"),
        sa.UniqueConstraint("source", "external_id", name="uq_hypotheses_source_external_id"),
    )


def downgrade() -> None:
    """Remove experiment persistence without changing other Core resources."""
    op.drop_table("hypotheses")
