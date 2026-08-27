"""Create immutable resume_versions for R2.1.1 ResumeVersion snapshots.

Revision ID: 20260827_09
Revises: 20260826_08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_09"
down_revision: str | None = "20260826_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add immutable resume_versions table (content snapshot history)."""
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_version_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_resume_id", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "content",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transport", sa.String(length=64), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_version_id"], ["profile_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resume_versions_profile_version_id"),
        "resume_versions",
        ["profile_version_id"],
    )
    op.create_index(
        "ix_resume_versions_lookup",
        "resume_versions",
        ["profile_version_id", "source", "external_resume_id", "captured_at"],
    )
    op.create_index(
        "ix_resume_versions_hash_lookup",
        "resume_versions",
        ["profile_version_id", "source", "external_resume_id", "content_hash"],
    )


def downgrade() -> None:
    """Remove resume_versions table."""
    op.drop_index("ix_resume_versions_hash_lookup", table_name="resume_versions")
    op.drop_index("ix_resume_versions_lookup", table_name="resume_versions")
    op.drop_index(op.f("ix_resume_versions_profile_version_id"), table_name="resume_versions")
    op.drop_table("resume_versions")
