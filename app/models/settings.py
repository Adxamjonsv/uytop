"""Database-backed, auditable platform catalogs."""

from typing import Any

from sqlalchemy import JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PlatformSetting(TimestampMixin, Base):
    __tablename__ = "platform_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
