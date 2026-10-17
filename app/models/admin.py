"""Web administrator accounts and roles."""

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Admin(TimestampMixin, Base):
    __tablename__ = "admins"
    __table_args__ = (CheckConstraint("role IN ('superadmin', 'moderator')", name="ck_admins_role"), Index("ix_admins_active_role", "is_active", "role"))
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="moderator")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
