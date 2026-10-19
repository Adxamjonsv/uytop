"""Publish active listings to the configured Telegram channel and withdraw inactive posts."""

import logging
import re

from aiogram import Bot
from sqlalchemy import select

from app.db import SessionFactory
from app.models import Listing, ListingPhoto, User

logger = logging.getLogger(__name__)
_DEAL_LABELS = {"rent": "Ijara", "sale": "Sotuv", "daily": "Kunlik ijara"}


_DESCRIPTION_FIELDS = {
    "metro": {"metro", "метро", "станция метро"},
    "building": {"dom turi", "bino turi", "uy turi", "тип дома", "дом"},
    "repair": {"ta'mir darajasi", "tamir darajasi", "ta’mir darajasi", "ремонт", "уровень ремонта"},
    "audience": {"kimlarga", "кому", "для кого"},
    "payment": {"to'lov turi", "tolov turi", "тўлов тури", "тип оплаты", "оплата"},
    "description": {"tavsif", "izoh", "description", "описание"},
    "amenities": {"mebel va texnika", "mebel", "qulayliklar", "мебель и техника", "удобства"},
    "floor": {"qavat", "этаж"},
}


def _description_fields(description: str) -> tuple[dict[str, str], str]:
    values: dict[str, str] = {}
    remaining: list[str] = []
    for line in description.splitlines():
        cleaned = re.sub(r"^[^\wА-Яа-яЁё]+", "", line).strip()
        match = re.match(r"^([^:—-]{2,48})\s*[:—-]\s*(.*)$", cleaned)
        if not match:
            remaining.append(line)
            continue
        label = match.group(1).strip().casefold().replace("’", "'").replace("ʻ", "'")
        field = next((name for name, aliases in _DESCRIPTION_FIELDS.items() if label in {alias.casefold().replace("’", "'").replace("ʻ", "'") for alias in aliases}), None)
        if field is None:
            remaining.append(line)
        else:
            values[field] = match.group(2).strip()
    return values, "\n".join(remaining).strip()


def channel_target(value: str) -> str:
    value = value.strip()
    if value and not value.lstrip("-").isdigit() and not value.startswith("@"):
        return "@" + value
    return value


async def sync_listing_to_channel(bot: Bot, listing_id: int, channel_setting: str) -> None:
    """Publish once, reformat imported channel posts in place, and remove withdrawn listings."""
    target = channel_target(channel_setting)
    async with SessionFactory() as session:
        listing = await session.get(Listing, listing_id)
        if listing is None:
            return

        if listing.status != "active":
            if listing.telegram_channel_id and listing.telegram_channel_message_id:
                source_ids = list((await session.scalars(
                    select(ListingPhoto.telegram_source_message_id).where(
                        ListingPhoto.listing_id == listing.id,
                        ListingPhoto.telegram_source_message_id.is_not(None),
                    )
                )).all())
                message_ids = dict.fromkeys([listing.telegram_channel_message_id, *source_ids])
                for message_id in message_ids:
                    try:
                        await bot.delete_message(listing.telegram_channel_id, message_id)
                    except Exception as exc:
                        if "message to delete not found" not in str(exc).lower():
                            logger.warning("UyTop kanal postini olib tashlab bo‘lmadi (%s)", type(exc).__name__)
                            return
                photos = list((await session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id == listing.id))).all())
                for photo_item in photos:
                    photo_item.telegram_source_message_id = None
                listing.telegram_channel_id = None
                listing.telegram_channel_message_id = None
                listing.telegram_channel_media = False
                listing.telegram_media_group_id = None
                await session.commit()
            return

        destination = listing.telegram_channel_id or target
        if not destination:
            return

        owner = await session.get(User, listing.owner_id)
        photo = await session.scalar(
            select(ListingPhoto.file_id)
            .where(ListingPhoto.listing_id == listing.id)
            .order_by(ListingPhoto.sort_order)
            .limit(1)
        )
        details, description = _description_fields(listing.description or "")
        property_labels = {"apartment": "Kvartira", "household": "Xonadon", "house": "Uy", "dormitory": "Yotoqxona"}
        period = " / oy" if listing.deal_type == "rent" else " / kun" if listing.deal_type == "daily" else ""
        price = f"{listing.price:,.0f} {listing.currency}{period}"
        floor = details.get("floor") or (
            f"{listing.floor} / {listing.total_floors}" if listing.floor is not None and listing.total_floors is not None
            else str(listing.floor) if listing.floor is not None else "—"
        )
        amenities = list(listing.amenities or [])
        if not amenities and details.get("amenities"):
            amenities = [item.strip(" •·-") for item in re.split(r"[,;\n]", details["amenities"]) if item.strip(" •·-")]
        lines = [
            f"🏠 {listing.title}",
            f"💰 {price}",
            "🛡 Maklersiz · Uy egasidan",
            f"📍 Shahar: {listing.region or 'Toshkent'}",
            f"🏙 Tuman: {listing.district}",
            f"🚇 Metro: {details.get('metro', '—')}",
            f"🏢 Uy turi: {details.get('building', property_labels.get(listing.property_type, listing.property_type))}",
            f"↗️ Qavat: {floor}",
            f"📐 Maydon: {f'{listing.area_m2:g}' if listing.area_m2 is not None else '—'} m²",
            f"🛏 Xonalar soni: {listing.rooms if listing.rooms is not None else '—'} xona",
            f"🛠 Ta’mir darajasi: {details.get('repair', '—')}",
            f"👥 Kimlarga: {details.get('audience', '—')}",
            f"💳 To‘lov turi: {details.get('payment', '—')}",
            "",
            "📝 Tavsif:",
            description[:350] if description else "—",
            "",
            "🛋 Mebel va texnika:",
            ", ".join(amenities[:20]) if amenities else "—",
        ]
        if listing.phone_consent and listing.contact_phone:
            lines.append(f"☎️ Telefon: {listing.contact_phone}")
        if owner and owner.username:
            lines.append(f"✈️ Telegram: @{owner.username}")
        lines.append(f"🆔 UyTop e’loni #{listing.id}")
        body = "\n".join(lines)[:1000]

        keyboard = None
        if owner and owner.username:
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✉️ Uy egasiga yozish", url=f"https://t.me/{owner.username}")
            ]])

        try:
            if listing.telegram_channel_message_id:
                if listing.telegram_channel_media:
                    await bot.edit_message_caption(
                        chat_id=destination,
                        message_id=listing.telegram_channel_message_id,
                        caption=body,
                        reply_markup=keyboard,
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=destination,
                        message_id=listing.telegram_channel_message_id,
                        text=body,
                        reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                return

            if photo:
                sent = await bot.send_photo(chat_id=destination, photo=photo, caption=body, reply_markup=keyboard)
                listing.telegram_channel_media = True
            else:
                sent = await bot.send_message(
                    chat_id=destination,
                    text=body,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                listing.telegram_channel_media = False
            listing.telegram_channel_id = str(sent.chat.id)
            listing.telegram_channel_message_id = sent.message_id
            await session.commit()
        except Exception as exc:
            if "message is not modified" in str(exc).lower():
                return
            logger.error("UyTop e’loni kanal bilan sinxronlanmadi (%s)", type(exc).__name__)
