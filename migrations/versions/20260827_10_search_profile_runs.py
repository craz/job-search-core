"""Create SearchProfile, SearchRun, and SearchRunItem for R2.2.1.

Revision ID: 20260827_10
Revises: 20260827_09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_10"
down_revision: str | None = "20260827_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist minimal SearchProfile + SearchRun + SearchRunItem tables."""
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "search_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=True),
        sa.Column("salary", json_type, nullable=True),
        sa.Column("experience", sa.String(length=64), nullable=True),
        sa.Column("employment", sa.String(length=64), nullable=True),
        sa.Column("schedule", sa.String(length=64), nullable=True),
        sa.Column("search_field", sa.String(length=64), nullable=True),
        sa.Column("only_with_salary", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "search_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_profile_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("criteria_snapshot", json_type, nullable=False),
        sa.Column("execution_snapshot", json_type, nullable=False),
        sa.Column("candidate_context_snapshot", json_type, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("found_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("recovery_hint", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["search_profile_id"], ["search_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_search_runs_search_profile_id"),
        "search_runs",
        ["search_profile_id"],
    )
    op.create_table(
        "search_run_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_external_id", sa.String(length=255), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "outcome = 'error' OR vacancy_id IS NOT NULL",
            name="ck_search_run_items_vacancy_required",
        ),
        sa.ForeignKeyConstraint(["search_run_id"], ["search_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "search_run_id",
            "source_external_id",
            name="uq_search_run_items_run_external",
        ),
    )
    op.create_index(
        op.f("ix_search_run_items_search_run_id"),
        "search_run_items",
        ["search_run_id"],
    )
    op.create_index(
        op.f("ix_search_run_items_vacancy_id"),
        "search_run_items",
        ["vacancy_id"],
    )


def downgrade() -> None:
    """Drop SearchRunItem, SearchRun, SearchProfile tables."""
    op.drop_index(op.f("ix_search_run_items_vacancy_id"), table_name="search_run_items")
    op.drop_index(op.f("ix_search_run_items_search_run_id"), table_name="search_run_items")
    op.drop_table("search_run_items")
    op.drop_index(op.f("ix_search_runs_search_profile_id"), table_name="search_runs")
    op.drop_table("search_runs")
    op.drop_table("search_profiles")
