"""Telegram user accounts."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('tenant', 'owner', 'admin')", name="ck_users_role"), CheckConstraint("status IN ('active', 'blocked')", name="ck_users_status"), Index("ix_users_status_created_at", "status", "created_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    phone_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="tenant")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
