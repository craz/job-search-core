"""Assessment v1 scoring identity and hybrid detail (R2.3.1).

Revision ID: 20260828_14
Revises: 20260828_13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_14"
down_revision: str | None = "20260828_13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("vacancy_content_hash", sa.String(64), nullable=True))
    op.add_column("assessments", sa.Column("profile_version_id", sa.Uuid(), nullable=True))
    op.add_column("assessments", sa.Column("resume_version_id", sa.Uuid(), nullable=True))
    op.add_column("assessments", sa.Column("candidate_context_hash", sa.String(64), nullable=True))
    op.add_column(
        "assessments",
        sa.Column(
            "scoring_mode",
            sa.Enum("fast", "detailed", name="assessment_scoring_mode", native_enum=False),
            nullable=True,
        ),
    )
    op.add_column("assessments", sa.Column("policy_id", sa.String(64), nullable=True))
    op.add_column("assessments", sa.Column("policy_version", sa.Integer(), nullable=True))
    op.add_column("assessments", sa.Column("policy_hash", sa.String(64), nullable=True))
    op.add_column("assessments", sa.Column("model_fingerprint", sa.String(64), nullable=True))
    op.add_column("assessments", sa.Column("scoring_identity_hash", sa.String(64), nullable=True))
    op.add_column("assessments", sa.Column("schema_version", sa.Integer(), nullable=True))
    op.add_column(
        "assessments",
        sa.Column("detail", sa.JSON(), nullable=True),
    )
    with op.batch_alter_table("assessments") as batch_op:
        batch_op.alter_column("reason", existing_type=sa.Text(), nullable=True)
        batch_op.alter_column("action", existing_type=sa.String(1000), nullable=True)
    op.create_index(
        "uq_assessments_scoring_identity_hash",
        "assessments",
        ["scoring_identity_hash"],
        unique=True,
        postgresql_where=sa.text("scoring_identity_hash IS NOT NULL"),
        sqlite_where=sa.text("scoring_identity_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_assessments_scoring_identity_hash",
        table_name="assessments",
        postgresql_where=sa.text("scoring_identity_hash IS NOT NULL"),
        sqlite_where=sa.text("scoring_identity_hash IS NOT NULL"),
    )
    with op.batch_alter_table("assessments") as batch_op:
        batch_op.alter_column("action", existing_type=sa.String(1000), nullable=False)
        batch_op.alter_column("reason", existing_type=sa.Text(), nullable=False)
    op.drop_column("assessments", "detail")
    op.drop_column("assessments", "schema_version")
    op.drop_column("assessments", "scoring_identity_hash")
    op.drop_column("assessments", "model_fingerprint")
    op.drop_column("assessments", "policy_hash")
    op.drop_column("assessments", "policy_version")
    op.drop_column("assessments", "policy_id")
    op.drop_column("assessments", "scoring_mode")
    op.drop_column("assessments", "candidate_context_hash")
    op.drop_column("assessments", "resume_version_id")
    op.drop_column("assessments", "profile_version_id")
    op.drop_column("assessments", "vacancy_content_hash")
    op.execute("DROP TYPE IF EXISTS assessment_scoring_mode")
