"""Add Vacancy source-owned fields + content_hash; nullable manual idempotency cols.

Revision ID: 20260827_11
Revises: 20260827_10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_11"
down_revision: str | None = "20260827_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Extend vacancies for provider ingest without breaking historical rows."""
    op.add_column("vacancies", sa.Column("salary_text", sa.String(length=500), nullable=True))
    op.add_column("vacancies", sa.Column("area_text", sa.String(length=500), nullable=True))
    op.add_column(
        "vacancies", sa.Column("employment_text", sa.String(length=255), nullable=True)
    )
    op.add_column("vacancies", sa.Column("schedule_text", sa.String(length=255), nullable=True))
    op.add_column(
        "vacancies", sa.Column("work_format_text", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "vacancies", sa.Column("experience_text", sa.String(length=255), nullable=True)
    )
    op.add_column("vacancies", sa.Column("published_text", sa.String(length=255), nullable=True))
    op.add_column("vacancies", sa.Column("archived", sa.Boolean(), nullable=True))
    op.add_column("vacancies", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_vacancies_content_hash"), "vacancies", ["content_hash"])
    with op.batch_alter_table("vacancies") as batch:
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=255),
            nullable=True,
        )
        batch.alter_column(
            "request_fingerprint",
            existing_type=sa.String(length=64),
            nullable=True,
        )


def downgrade() -> None:
    """Drop ingest columns; restore non-null manual metadata where possible."""
    with op.batch_alter_table("vacancies") as batch:
        batch.alter_column(
            "request_fingerprint",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=255),
            nullable=False,
        )
    op.drop_index(op.f("ix_vacancies_content_hash"), table_name="vacancies")
    op.drop_column("vacancies", "content_hash")
    op.drop_column("vacancies", "archived")
    op.drop_column("vacancies", "published_text")
    op.drop_column("vacancies", "experience_text")
    op.drop_column("vacancies", "work_format_text")
    op.drop_column("vacancies", "schedule_text")
    op.drop_column("vacancies", "employment_text")
    op.drop_column("vacancies", "area_text")
    op.drop_column("vacancies", "salary_text")
