"""Store each source photo message ID for channel album removal.

Revision ID: 20261019_0005
Revises: 20261019_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0005"
down_revision = "20261019_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listing_photos", sa.Column("telegram_source_message_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrades are disabled. Apply a reviewed forward migration instead.")
