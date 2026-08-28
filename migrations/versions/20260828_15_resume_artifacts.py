"""Auxiliary local resume file artifacts (R2.1-CORR-01).

Revision ID: 20260828_15
Revises: 20260828_14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_15"
down_revision: str | None = "20260828_14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resume_version_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["resume_version_id"], ["resume_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resume_version_id",
            "sha256",
            name="uq_resume_artifacts_version_sha256",
        ),
        sa.UniqueConstraint("storage_key", name="uq_resume_artifacts_storage_key"),
    )
    op.create_index(
        op.f("ix_resume_artifacts_resume_version_id"),
        "resume_artifacts",
        ["resume_version_id"],
    )
    op.create_index(
        "ix_resume_artifacts_version_captured",
        "resume_artifacts",
        ["resume_version_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_artifacts_version_captured", table_name="resume_artifacts")
    op.drop_index(op.f("ix_resume_artifacts_resume_version_id"), table_name="resume_artifacts")
    op.drop_table("resume_artifacts")
