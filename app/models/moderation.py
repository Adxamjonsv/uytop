"""Moderation history and administrator audit trail."""

from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ModerationLog(TimestampMixin, Base):
    __tablename__ = "moderation_logs"
    __table_args__ = (CheckConstraint("action IN ('approved', 'rejected', 'hidden', 'restored')", name="ck_moderation_logs_action"), Index("ix_moderation_logs_listing_created", "listing_id", "created_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="RESTRICT"), nullable=False)
    moderator_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


class AdminAuditLog(TimestampMixin, Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (Index("ix_admin_audit_logs_admin_created", "admin_id", "created_at"), Index("ix_admin_audit_logs_entity", "entity_type", "entity_id"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    ip_address: Mapped[str | None] = mapped_column(String(45))
