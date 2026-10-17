"""Database-backed location and property type catalogs."""

from sqlalchemy import select

from app.bot.keyboards import DISTRICTS, PROPERTY_TYPES
from app.db import SessionFactory
from app.models import PlatformSetting

DEFAULT_PROPERTY_TYPES = [{"code": code, "label": label} for label, code in PROPERTY_TYPES]


async def get_catalogs() -> dict:
    async with SessionFactory() as session:
        rows = (await session.scalars(select(PlatformSetting))).all()
        saved = {row.key: row.value for row in rows}
    districts = saved.get("districts", DISTRICTS)
    property_types = saved.get("property_types", DEFAULT_PROPERTY_TYPES)
    return {"districts": districts, "property_types": property_types}

