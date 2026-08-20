"""Add confirmed normalized Company website.

Revision ID: 20260820_07
Revises: 20260820_06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_07"
down_revision: str | None = "20260820_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the confirmed website field without importing OSINT evidence."""
    op.add_column("companies", sa.Column("website_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    """Remove the optional confirmed website field."""
    op.drop_column("companies", "website_url")
