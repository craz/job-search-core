"""Vacancy acquisition provenance timestamps (R2.2.5 temporal).

Revision ID: 20260828_13
Revises: 20260827_12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_13"
down_revision: str | None = "20260827_12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add first_seen_at / last_seen_at with approximate backfill; nullable source_published_at."""
    op.add_column(
        "vacancies",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "vacancies",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "vacancies",
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE vacancies
        SET first_seen_at = created_at,
            last_seen_at = COALESCE(updated_at, created_at)
        WHERE first_seen_at IS NULL
        """
    )
    with op.batch_alter_table("vacancies") as batch:
        batch.alter_column("first_seen_at", nullable=False)
        batch.alter_column("last_seen_at", nullable=False)


def downgrade() -> None:
    """Drop acquisition provenance timestamps."""
    op.drop_column("vacancies", "source_published_at")
    op.drop_column("vacancies", "last_seen_at")
    op.drop_column("vacancies", "first_seen_at")
