"""Database-backed settings for bidirectional channel synchronization."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlatformSetting


DEFAULT_CHANNEL_SETTINGS = {
    "channel_sync_enabled": True,
    "channel_import_enabled": True,
    "channel_import_mode": "review",
    "channel_rented_action": "mark",
    "channel_rented_keywords": ["band", "сдано", "сдан", "✅ band", "✅ банд"],
}


async def get_channel_settings(session: AsyncSession) -> dict:
    result = dict(DEFAULT_CHANNEL_SETTINGS)
    for key in DEFAULT_CHANNEL_SETTINGS:
        row = await session.get(PlatformSetting, key)
        if row is not None:
            result[key] = row.value
    if result.get("channel_import_mode") not in {"review", "auto"}:
        result["channel_import_mode"] = "review"
    if result.get("channel_rented_action") not in {"mark", "delete"}:
        result["channel_rented_action"] = "mark"
    if not isinstance(result.get("channel_rented_keywords"), list):
        result["channel_rented_keywords"] = list(DEFAULT_CHANNEL_SETTINGS["channel_rented_keywords"])
    return result


async def save_channel_settings(session: AsyncSession, values: dict) -> dict:
    current = await get_channel_settings(session)
    for key in DEFAULT_CHANNEL_SETTINGS:
        if key not in values:
            continue
        value = values[key]
        if key in {"channel_sync_enabled", "channel_import_enabled"}:
            value = bool(value)
        elif key == "channel_import_mode":
            if value not in {"review", "auto"}:
                raise ValueError("Import rejimi review yoki auto bo‘lishi kerak.")
        elif key == "channel_rented_action":
            if value not in {"mark", "delete"}:
                raise ValueError("Band e’lon amali mark yoki delete bo‘lishi kerak.")
        elif key == "channel_rented_keywords":
            value = list(dict.fromkeys(str(item).strip().casefold()[:40] for item in value if str(item).strip()))[:30]
        row = await session.get(PlatformSetting, key)
        if row is None:
            session.add(PlatformSetting(key=key, value=value))
        else:
            row.value = value
        current[key] = value
    return current
