"""Store media-group identity for imported channel listings.

Revision ID: 20261019_0004
Revises: 20261019_0003
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0004"
down_revision = "20261019_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("telegram_channel_media", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("listings", sa.Column("telegram_media_group_id", sa.String(length=64), nullable=True))
    op.create_index("ix_listings_telegram_media_group", "listings", ["telegram_channel_id", "telegram_media_group_id"])


def downgrade() -> None:
    raise RuntimeError("Destructive downgrades are disabled. Apply a reviewed forward migration instead.")
