"""Publish approved listings to the configured Telegram channel and remove withdrawn posts."""

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from app.db import SessionFactory
from app.models import Listing, ListingPhoto, User

logger = logging.getLogger(__name__)

_DEAL_LABELS = {"rent": "Ijara", "sale": "Sotuv", "daily": "Kunlik ijara"}


def _channel_target(value: str) -> str:
    value = value.strip()
    if value and not value.lstrip("-").isdigit() and not value.startswith("@"):
        return "@" + value
    return value


async def sync_listing_to_channel(bot: Bot, listing_id: int, channel_setting: str) -> None:
    """Publish active listings once; delete their channel post when they are no longer active."""
    target = _channel_target(channel_setting)
    async with SessionFactory() as session:
        listing = await session.get(Listing, listing_id)
        if listing is None:
            return

        if listing.status != "active":
            if listing.telegram_channel_id and listing.telegram_channel_message_id:
                try:
                    await bot.delete_message(
                        chat_id=listing.telegram_channel_id,
                        message_id=listing.telegram_channel_message_id,
                    )
                except Exception as exc:
                    logger.warning("UyTop kanal postini olib tashlab bo‘lmadi (%s)", type(exc).__name__)
                    return
                listing.telegram_channel_id = None
                listing.telegram_channel_message_id = None
                await session.commit()
            return

        if not target or listing.telegram_channel_message_id:
            return

        owner = await session.get(User, listing.owner_id)
        photo = await session.scalar(
            select(ListingPhoto.file_id)
            .where(ListingPhoto.listing_id == listing.id)
            .order_by(ListingPhoto.sort_order)
            .limit(1)
        )

        place = listing.district
        if listing.neighborhood:
            place += f", {listing.neighborhood}"
        lines = [
            f"🏠 {listing.title}",
            f"💼 {_DEAL_LABELS.get(listing.deal_type, listing.deal_type)} · {listing.property_type}",
            f"📍 {place}",
            f"💰 {listing.price:,.0f} {listing.currency}",
            f"🚪 {listing.rooms if listing.rooms is not None else '—'} xona · "
            f"📐 {f'{listing.area_m2:g}' if listing.area_m2 is not None else '—'} m²",
        ]
        if listing.description.strip():
            lines.extend(["", listing.description.strip()[:350]])
        if listing.phone_consent and listing.contact_phone:
            lines.append(f"☎️ {listing.contact_phone}")
        lines.append(f"🆔 UyTop e’loni #{listing.id}")
        caption = "\n".join(lines)[:1000]

        keyboard = None
        if owner and owner.username:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✉️ Uy egasiga yozish", url=f"https://t.me/{owner.username}")
            ]])

        try:
            if photo:
                sent = await bot.send_photo(
                    chat_id=target,
                    photo=photo,
                    caption=caption,
                    reply_markup=keyboard,
                )
            else:
                sent = await bot.send_message(
                    chat_id=target,
                    text=caption,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
        except Exception as exc:
            logger.error("UyTop e’loni kanalga yuborilmadi (%s)", type(exc).__name__)
            return

        listing.telegram_channel_id = target
        listing.telegram_channel_message_id = sent.message_id
        await session.commit()
