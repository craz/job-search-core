"""SearchRun acquisition_kind + nullable profile + source_total.

Revision ID: 20260827_12
Revises: 20260827_11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_12"
down_revision: str | None = "20260827_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow resume_suitable runs without SearchProfile; record HH source_total."""
    op.add_column(
        "search_runs",
        sa.Column(
            "acquisition_kind",
            sa.String(length=32),
            nullable=False,
            server_default="profile_search",
        ),
    )
    op.add_column("search_runs", sa.Column("source_total", sa.Integer(), nullable=True))
    with op.batch_alter_table("search_runs") as batch:
        batch.alter_column(
            "search_profile_id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=True,
        )
        batch.create_check_constraint(
            "ck_search_runs_acquisition_profile",
            "(acquisition_kind = 'profile_search' AND search_profile_id IS NOT NULL) OR "
            "(acquisition_kind = 'resume_suitable' AND search_profile_id IS NULL)",
        )


def downgrade() -> None:
    """Restore required SearchProfile FK; drop acquisition metadata."""
    op.execute(
        "UPDATE search_runs SET search_profile_id = ("
        "SELECT id FROM search_profiles ORDER BY created_at DESC LIMIT 1"
        ") WHERE search_profile_id IS NULL"
    )
    with op.batch_alter_table("search_runs") as batch:
        batch.drop_constraint("ck_search_runs_acquisition_profile", type_="check")
        batch.alter_column(
            "search_profile_id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=False,
        )
    op.drop_column("search_runs", "source_total")
    op.drop_column("search_runs", "acquisition_kind")
