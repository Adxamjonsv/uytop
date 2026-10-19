"""Property listings, Telegram-hosted photos, and resumable drafts."""

from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Listing(TimestampMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("deal_type IN ('rent', 'sale', 'daily')", name="ck_listings_deal_type"),
        CheckConstraint("property_type IN ('apartment', 'household', 'house', 'dormitory')", name="ck_listings_property_type"),
        CheckConstraint("status IN ('draft', 'pending', 'active', 'rejected', 'rented', 'archived')", name="ck_listings_status"),
        CheckConstraint("price > 0", name="ck_listings_price_positive"),
        CheckConstraint("rooms IS NULL OR rooms >= 0", name="ck_listings_rooms_nonnegative"),
        CheckConstraint("area_m2 IS NULL OR area_m2 > 0", name="ck_listings_area_positive"),
        CheckConstraint("floor IS NULL OR floor >= 0", name="ck_listings_floor_nonnegative"),
        CheckConstraint("contact_method IN ('telegram', 'phone', 'both')", name="ck_listings_contact_method"),
        Index("ix_listings_status_district_created_at", "status", "district", "created_at"),
        Index("ix_listings_status_price", "status", "price"),
        Index("ix_listings_owner_status", "owner_id", "status"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    deal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    property_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="UZS")
    region: Mapped[str] = mapped_column(String(80), nullable=False, server_default="Toshkent")
    district: Mapped[str] = mapped_column(String(80), nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(240))
    address_is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    rooms: Mapped[int | None] = mapped_column(Integer)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    floor: Mapped[int | None] = mapped_column(Integer)
    total_floors: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    amenities: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default=text("'[]'"))
    contact_method: Mapped[str] = mapped_column(String(16), nullable=False, server_default="telegram")
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    phone_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    telegram_channel_id: Mapped[str | None] = mapped_column(String(80))
    telegram_channel_message_id: Mapped[int | None] = mapped_column(BigInteger)
    moderated_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))


class ListingPhoto(TimestampMixin, Base):
    __tablename__ = "listing_photos"
    __table_args__ = (CheckConstraint("sort_order >= 0", name="ck_listing_photos_sort_order"), Index("ix_listing_photos_listing_order", "listing_id", "sort_order"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class ListingDraft(TimestampMixin, Base):
    __tablename__ = "listing_drafts"
    __table_args__ = (CheckConstraint("current_step >= 1 AND current_step <= 7", name="ck_listing_drafts_current_step"), CheckConstraint("source IN ('bot', 'mini_app')", name="ck_listing_drafts_source"), UniqueConstraint("user_id", "source", name="uq_listing_drafts_user_source"), Index("ix_listing_drafts_user_updated", "user_id", "updated_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="bot")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
