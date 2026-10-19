"""Track Telegram channel message IDs on listings.

Revision ID: 20261019_0003
Revises: 20261019_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0003"
down_revision = "20261019_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("telegram_channel_id", sa.String(length=80), nullable=True))
    op.add_column("listings", sa.Column("telegram_channel_message_id", sa.BigInteger(), nullable=True))
    op.create_index(
        "ix_listings_telegram_channel_message",
        "listings",
        ["telegram_channel_id", "telegram_channel_message_id"],
        unique=True,
    )


def downgrade() -> None:
    raise RuntimeError("Destructive downgrades are disabled. Apply a reviewed forward migration instead.")
