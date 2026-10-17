"""Favorites, inquiries, saved searches, reports, and notifications."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Favorite(TimestampMixin, Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_favorites_user_listing"), Index("ix_favorites_listing", "listing_id"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)


class ListingView(Base):
    __tablename__ = "listing_views"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_listing_views_user_listing"), Index("ix_listing_views_user_viewed", "user_id", "viewed_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Inquiry(TimestampMixin, Base):
    __tablename__ = "inquiries"
    __table_args__ = (CheckConstraint("channel IN ('telegram', 'phone')", name="ck_inquiries_channel"), CheckConstraint("status IN ('new', 'contacted', 'closed')", name="ck_inquiries_status"), Index("ix_inquiries_owner_created", "owner_id", "created_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="RESTRICT"), nullable=False)
    renter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="new")


class SavedSearch(TimestampMixin, Base):
    __tablename__ = "saved_searches"
    __table_args__ = (Index("ix_saved_searches_user", "user_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Report(TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (CheckConstraint("status IN ('open', 'reviewing', 'resolved', 'dismissed')", name="ck_reports_status"), Index("ix_reports_status_created_at", "status", "created_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (CheckConstraint("delivery_status IN ('queued', 'sent', 'failed', 'read')", name="ck_notifications_delivery_status"), Index("ix_notifications_user_status_created", "user_id", "delivery_status", "created_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    delivery_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="queued")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
