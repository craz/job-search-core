"""Create CandidateProfile / ProfileVersion / ActiveHhResumeLink (R1.5).

Revision ID: 20260826_08
Revises: 20260820_07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_08"
down_revision: str | None = "20260820_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add minimal local candidate context tables for HH resume linkage."""
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("singleton_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key", name="uq_candidate_profiles_singleton_key"),
    )
    op.create_table(
        "profile_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_profile_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_profile_id"], ["candidate_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_profile_id",
            "label",
            name="uq_profile_versions_profile_label",
        ),
    )
    op.create_index(
        op.f("ix_profile_versions_candidate_profile_id"),
        "profile_versions",
        ["candidate_profile_id"],
    )
    op.create_table(
        "active_hh_resume_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_version_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_resume_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "cleared",
                "stale",
                name="hh_resume_link_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_version_id"], ["profile_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_version_id", name="uq_active_hh_resume_links_profile_version"),
    )
    op.create_index(
        op.f("ix_active_hh_resume_links_profile_version_id"),
        "active_hh_resume_links",
        ["profile_version_id"],
    )


def downgrade() -> None:
    """Remove R1.5 candidate linkage tables."""
    op.drop_index(
        op.f("ix_active_hh_resume_links_profile_version_id"),
        table_name="active_hh_resume_links",
    )
    op.drop_table("active_hh_resume_links")
    op.drop_index(op.f("ix_profile_versions_candidate_profile_id"), table_name="profile_versions")
    op.drop_table("profile_versions")
    op.drop_table("candidate_profiles")
