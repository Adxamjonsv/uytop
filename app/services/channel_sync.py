"""Publish active listings to the configured Telegram channel and withdraw inactive posts."""

import logging

from aiogram import Bot
from sqlalchemy import select

from app.db import SessionFactory
from app.models import Listing, ListingPhoto, User

logger = logging.getLogger(__name__)
_DEAL_LABELS = {"rent": "Ijara", "sale": "Sotuv", "daily": "Kunlik ijara"}


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
                try:
                    await bot.delete_message(listing.telegram_channel_id, listing.telegram_channel_message_id)
                except Exception as exc:
                    logger.warning("UyTop kanal postini olib tashlab bo‘lmadi (%s)", type(exc).__name__)
                    return
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
        place = listing.district + (f", {listing.neighborhood}" if listing.neighborhood else "")
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
        if owner and owner.username:
            lines.append(f"📩 Aloqa: @{owner.username}")
        if listing.phone_consent and listing.contact_phone:
            lines.append(f"☎️ Telefon: {listing.contact_phone}")
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
