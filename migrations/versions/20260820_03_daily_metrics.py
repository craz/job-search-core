"""Create normalized Daily Metric persistence.

Revision ID: 20260820_03
Revises: 20260819_02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_03"
down_revision: str | None = "20260819_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create dated snapshots and an idempotency operation journal."""
    op.create_table(
        "daily_metrics",
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("views_total", sa.Integer(), nullable=True),
        sa.Column("views_new", sa.Integer(), nullable=True),
        sa.Column("applications", sa.Integer(), nullable=True),
        sa.Column("replies", sa.Integer(), nullable=True),
        sa.Column("invitations", sa.Integer(), nullable=True),
        sa.Column("rejections", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "views_total IS NULL OR views_total >= 0", name="ck_metrics_views_total"
        ),
        sa.CheckConstraint("views_new IS NULL OR views_new >= 0", name="ck_metrics_views_new"),
        sa.CheckConstraint(
            "applications IS NULL OR applications >= 0", name="ck_metrics_applications"
        ),
        sa.CheckConstraint("replies IS NULL OR replies >= 0", name="ck_metrics_replies"),
        sa.CheckConstraint(
            "invitations IS NULL OR invitations >= 0", name="ck_metrics_invitations"
        ),
        sa.CheckConstraint("rejections IS NULL OR rejections >= 0", name="ck_metrics_rejections"),
        sa.PrimaryKeyConstraint("metric_date"),
    )
    op.create_table(
        "daily_metric_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["metric_date"], ["daily_metrics.metric_date"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_metric_requests_idempotency_key"),
    )
    op.create_index(
        op.f("ix_daily_metric_requests_metric_date"),
        "daily_metric_requests",
        ["metric_date"],
        unique=False,
    )


def downgrade() -> None:
    """Remove metric operation history before its referenced snapshots."""
    op.drop_index(op.f("ix_daily_metric_requests_metric_date"), table_name="daily_metric_requests")
    op.drop_table("daily_metric_requests")
    op.drop_table("daily_metrics")
