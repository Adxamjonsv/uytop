"""Create the initial UyTop database schema.

Revision ID: 20261017_0001
Revises:
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20261017_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create missing platform tables without touching existing data."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(64)),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("phone_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("role", sa.String(16), nullable=False, server_default="tenant"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('tenant', 'owner', 'admin')", name="ck_users_role"),
        sa.CheckConstraint("status IN ('active', 'blocked')", name="ck_users_status"),
    )
    op.create_index("ix_users_status_created_at", "users", ["status", "created_at"])

    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="moderator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('superadmin', 'moderator')", name="ck_admins_role"),
    )
    op.create_index("ix_admins_active_role", "admins", ["is_active", "role"])

    op.create_table(
        "listings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("deal_type", sa.String(16), nullable=False),
        sa.Column("property_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="UZS"),
        sa.Column("region", sa.String(80), nullable=False, server_default="Toshkent"),
        sa.Column("district", sa.String(80), nullable=False),
        sa.Column("neighborhood", sa.String(120)),
        sa.Column("address", sa.String(240)),
        sa.Column("address_is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rooms", sa.Integer()),
        sa.Column("area_m2", sa.Numeric(8, 2)),
        sa.Column("floor", sa.Integer()),
        sa.Column("total_floors", sa.Integer()),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("amenities", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("contact_method", sa.String(16), nullable=False, server_default="telegram"),
        sa.Column("contact_phone", sa.String(32)),
        sa.Column("phone_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("moderated_by", sa.Integer(), sa.ForeignKey("admins.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("deal_type IN ('rent', 'sale', 'daily')", name="ck_listings_deal_type"),
        sa.CheckConstraint("property_type IN ('apartment', 'household', 'house', 'dormitory')", name="ck_listings_property_type"),
        sa.CheckConstraint("status IN ('draft', 'pending', 'active', 'rejected', 'rented', 'archived')", name="ck_listings_status"),
        sa.CheckConstraint("price > 0", name="ck_listings_price_positive"),
        sa.CheckConstraint("rooms IS NULL OR rooms >= 0", name="ck_listings_rooms_nonnegative"),
        sa.CheckConstraint("area_m2 IS NULL OR area_m2 > 0", name="ck_listings_area_positive"),
        sa.CheckConstraint("floor IS NULL OR floor >= 0", name="ck_listings_floor_nonnegative"),
        sa.CheckConstraint("contact_method IN ('telegram', 'phone', 'both')", name="ck_listings_contact_method"),
    )
    op.create_index("ix_listings_status_district_created_at", "listings", ["status", "district", "created_at"])
    op.create_index("ix_listings_status_price", "listings", ["status", "price"])
    op.create_index("ix_listings_owner_status", "listings", ["owner_id", "status"])

    op.create_table(
        "listing_photos",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("sort_order >= 0", name="ck_listing_photos_sort_order"),
    )
    op.create_index("ix_listing_photos_listing_order", "listing_photos", ["listing_id", "sort_order"])

    op.create_table(
        "listing_drafts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="bot"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("current_step >= 1 AND current_step <= 7", name="ck_listing_drafts_current_step"),
        sa.CheckConstraint("source IN ('bot', 'mini_app')", name="ck_listing_drafts_source"),
        sa.UniqueConstraint("user_id", "source", name="uq_listing_drafts_user_source"),
    )
    op.create_index("ix_listing_drafts_user_updated", "listing_drafts", ["user_id", "updated_at"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "listing_id", name="uq_favorites_user_listing"),
    )
    op.create_index("ix_favorites_listing", "favorites", ["listing_id"])

    op.create_table(
        "listing_views",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "listing_id", name="uq_listing_views_user_listing"),
    )
    op.create_index("ix_listing_views_user_viewed", "listing_views", ["user_id", "viewed_at"])

    op.create_table(
        "inquiries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("renter_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("channel IN ('telegram', 'phone')", name="ck_inquiries_channel"),
        sa.CheckConstraint("status IN ('new', 'contacted', 'closed')", name="ck_inquiries_status"),
    )
    op.create_index("ix_inquiries_owner_created", "inquiries", ["owner_id", "created_at"])

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saved_searches_user", "saved_searches", ["user_id"])

    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("reporter_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("admins.id", ondelete="SET NULL")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open', 'reviewing', 'resolved', 'dismissed')", name="ck_reports_status"),
    )
    op.create_index("ix_reports_status_created_at", "reports", ["status", "created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(48), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("delivery_status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("delivery_status IN ('queued', 'sent', 'failed', 'read')", name="ck_notifications_delivery_status"),
    )
    op.create_index("ix_notifications_user_status_created", "notifications", ["user_id", "delivery_status", "created_at"])

    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("moderator_id", sa.Integer(), sa.ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('approved', 'rejected', 'hidden', 'restored')", name="ck_moderation_logs_action"),
    )
    op.create_index("ix_moderation_logs_listing_created", "moderation_logs", ["listing_id", "created_at"])

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(80)),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_audit_logs_admin_created", "admin_audit_logs", ["admin_id", "created_at"])
    op.create_index("ix_admin_audit_logs_entity", "admin_audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Refuse destructive rollback; preserve production rows and tables."""
    raise RuntimeError("Destructive downgrades are disabled. Apply a reviewed forward migration instead.")
