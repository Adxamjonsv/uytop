"""Add a persistent user language preference.

Revision ID: 20261019_0002
Revises: 20261017_0001
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = "20261019_0002"
down_revision = "20261017_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language_code", sa.String(length=2), nullable=False, server_default="uz"))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrades are disabled. Apply a reviewed forward migration instead.")
