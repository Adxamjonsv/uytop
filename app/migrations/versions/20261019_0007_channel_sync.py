"""Add bidirectional Telegram channel synchronization metadata.

Revision ID: 20261019_0007
Revises: 20261019_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0007"
down_revision = "20261019_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("source", sa.String(length=16), nullable=False, server_default="bot"))
    op.add_column("listings", sa.Column("channel_chat_id", sa.String(length=80), nullable=True))
    op.add_column("listings", sa.Column("channel_message_id", sa.BigInteger(), nullable=True))
    op.add_column("listings", sa.Column("media_group_id", sa.String(length=64), nullable=True))
    op.add_column("listings", sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("listings", sa.Column("contact_username", sa.String(length=64), nullable=True))
    op.add_column("listings", sa.Column("channel_overrides", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.create_check_constraint("ck_listings_source", "listings", "source IN ('bot', 'channel')")
    op.create_index("ix_listings_source_channel_message", "listings", ["source", "channel_chat_id", "channel_message_id"])

    op.create_table(
        "channel_posts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chat_id", sa.String(length=80), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("is_album_part", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="collecting"),
        sa.Column("media_group_id", sa.String(length=64), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("file_id", sa.String(length=255), nullable=True),
        sa.Column("is_bot_post", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_control_post", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("chat_id", "message_id", name="uq_channel_posts_chat_message"),
    )
    op.create_index("ix_channel_posts_listing_status", "channel_posts", ["listing_id", "status"])
    op.create_index("ix_channel_posts_media_group", "channel_posts", ["chat_id", "media_group_id"])

    # Preserve known posts from the previous single-message synchronization columns.
    op.execute("""
        INSERT INTO channel_posts
            (listing_id, chat_id, message_id, is_album_part, posted_at, status, is_bot_post, is_control_post, created_at, updated_at)
        SELECT id, telegram_channel_id, telegram_channel_message_id, telegram_channel_media,
               now(), 'published', true, false, now(), now()
        FROM listings
        WHERE telegram_channel_id IS NOT NULL AND telegram_channel_message_id IS NOT NULL
        ON CONFLICT (chat_id, message_id) DO NOTHING
    """)
    op.execute("""
        UPDATE listings
        SET channel_chat_id = telegram_channel_id,
            channel_message_id = telegram_channel_message_id,
            media_group_id = telegram_media_group_id
        WHERE telegram_channel_id IS NOT NULL AND telegram_channel_message_id IS NOT NULL
    """)
    op.execute("""
        UPDATE listings AS listing
        SET source = 'channel', imported_at = now()
        WHERE listing.telegram_channel_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM users AS owner WHERE owner.id = listing.owner_id AND owner.telegram_id < 0)
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrades are disabled. Apply a reviewed forward migration instead.")
