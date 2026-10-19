"""Reliable bot-to-channel publishing and withdrawal for UyTop listings."""

import asyncio
import logging
import re

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionFactory
from app.models import ChannelPost, Listing, ListingPhoto, User
from app.services.channel_settings import get_channel_settings

logger = logging.getLogger(__name__)
_DEAL_LABELS = {"rent": "Ijara", "sale": "Sotuv", "daily": "Kunlik ijara", "unknown": "Kelishiladi"}
_PROPERTY_LABELS = {"apartment": "Kvartira", "household": "Xonadon", "house": "Uy", "dormitory": "Yotoqxona", "unknown": "Ko‘rsatilmagan"}


def channel_target(value: str) -> str:
    value = (value or "").strip()
    if value and not value.lstrip("-").isdigit() and not value.startswith("@"):
        return "@" + value
    return value


def channel_post_url(chat_id: str | None, message_id: int | None, username: str = "") -> str | None:
    if not chat_id or not message_id:
        return None
    public_name = (username or "").strip().lstrip("@")
    if public_name:
        return f"https://t.me/{public_name}/{message_id}"
    raw = str(chat_id)
    if raw.startswith("-100"):
        return f"https://t.me/c/{raw[4:]}/{message_id}"
    return None


async def _call(operation, label: str):
    for attempt in range(3):
        try:
            return await operation()
        except TelegramRetryAfter as exc:
            if attempt == 2:
                raise
            await asyncio.sleep(min(float(exc.retry_after) + 0.2, 30))
        except Exception as exc:
            if "message is not modified" in str(exc).casefold():
                return None
            if attempt == 2:
                raise
            logger.warning("Telegram %s vaqtincha xato (%s), qayta uriniladi", label, type(exc).__name__)
            await asyncio.sleep(0.5 * (2 ** attempt))


async def _notify_admins(bot: Bot, message: str) -> None:
    try:
        ids = get_settings().admin_telegram_id_list
    except Exception:
        logger.exception("Kanal xatosi uchun adminlar ro‘yxatini o‘qib bo‘lmadi")
        return
    for telegram_id in ids:
        try:
            await bot.send_message(telegram_id, message[:3500])
        except Exception:
            continue


def _listing_text(listing: Listing, owner: User | None, bot_username: str, channel_username: str, band: bool = False) -> str:
    details: dict[str, str] = {}
    remaining: list[str] = []
    aliases = {
        "metro": {"metro", "метро"},
        "building": {"uy turi", "dom turi", "тип дома"},
        "repair": {"ta'mir darajasi", "tamir darajasi", "ремонт"},
        "audience": {"kimlarga", "кому"},
        "payment": {"to'lov turi", "tolov turi", "тип оплаты"},
        "description": {"tavsif", "izoh", "описание"},
        "amenities": {"mebel va texnika", "mebel", "qulayliklar"},
    }
    for line in (listing.description or "").splitlines():
        match = re.match(r"^([^:—-]{2,48})\s*[:—-]\s*(.*)$", line.strip())
        if not match:
            remaining.append(line)
            continue
        label = match.group(1).strip().casefold().replace("’", "'").replace("ʻ", "'")
        key = next((name for name, values in aliases.items() if label in values), None)
        if key:
            details[key] = match.group(2).strip()
        else:
            remaining.append(line)
    amenities = list(listing.amenities or [])
    if not amenities and details.get("amenities"):
        amenities = [item.strip(" •·-") for item in re.split(r"[,;\n]", details["amenities"]) if item.strip(" •·-")]
    if listing.price is None:
        price = "Kelishiladi"
    else:
        period = " / oy" if listing.deal_type == "rent" else " / kun" if listing.deal_type == "daily" else ""
        currency = listing.currency or ""
        price = f"{listing.price:,.0f} {currency}{period}".strip()
    floor = f"{listing.floor} / {listing.total_floors}" if listing.floor is not None and listing.total_floors is not None else str(listing.floor) if listing.floor is not None else "—"
    rows = [
        f"{'✅ BAND · ' if band else ''}🏠 {listing.title or 'Uy e’loni'}",
        f"💰 {price}",
        "🛡 Maklersiz · Uy egasidan",
        f"📍 Shahar: {listing.region or 'Toshkent'}",
        f"🏙 Tuman: {listing.district or '—'}",
        f"🏘 Bitim: {_DEAL_LABELS.get(listing.deal_type, listing.deal_type)} · {_PROPERTY_LABELS.get(listing.property_type, listing.property_type)}",
        f"🚇 Metro: {details.get('metro', '—')}",
        f"↗️ Qavat: {floor}",
        f"📐 Maydon: {f'{listing.area_m2:g}' if listing.area_m2 is not None else '—'} m²",
        f"🛏 Xonalar soni: {listing.rooms if listing.rooms is not None else '—'} xona",
        f"🛠 Ta’mir: {details.get('repair', '—')}",
        f"👥 Kimlarga: {details.get('audience', '—')}",
        f"💳 To‘lov turi: {details.get('payment', '—')}",
        "",
        "📝 Tavsif:",
        "\n".join(remaining)[:300] or "—",
        "",
        "🛋 Qulayliklar:",
        ", ".join(amenities[:20]) or "—",
    ]
    contact_username = listing.contact_username or (owner.username if owner else None)
    if listing.phone_consent and listing.contact_phone:
        rows.append(f"☎️ Telefon: {listing.contact_phone}")
    if contact_username:
        rows.append(f"✈️ Telegram: @{contact_username.lstrip('@')}")
    return "\n".join(rows)[:1000]


async def _delete_posts(bot: Bot, session, rows: list[ChannelPost]) -> None:
    for row in rows:
        if row.status == "deleted":
            continue
        try:
            await _call(lambda: bot.delete_message(chat_id=row.chat_id, message_id=row.message_id), "postni o‘chirish")
        except Exception as exc:
            if "message to delete not found" not in str(exc).casefold():
                logger.error("Kanal postini o‘chirishda xato (%s)", type(exc).__name__)
                await _notify_admins(bot, f"⚠️ Kanal postini o‘chirib bo‘lmadi: {row.chat_id}/{row.message_id}. Bot huquqlari va Telegram loglarini tekshiring.")
                continue
        row.status = "deleted"
    await session.commit()


async def _save_message(session, listing: Listing, message, body: str, *, control: bool = False) -> ChannelPost:
    row = await session.scalar(select(ChannelPost).where(ChannelPost.chat_id == str(message.chat.id), ChannelPost.message_id == message.message_id))
    if row is None:
        row = ChannelPost(listing_id=listing.id, chat_id=str(message.chat.id), message_id=message.message_id)
        session.add(row)
    row.listing_id = listing.id
    row.is_album_part = bool(message.media_group_id)
    row.posted_at = message.date
    row.status = "published"
    row.media_group_id = message.media_group_id
    row.caption = body or None
    row.file_id = message.photo[-1].file_id if message.photo else None
    row.is_bot_post = True
    row.is_control_post = control
    return row


async def sync_listing_to_channel(bot: Bot, listing_id: int, channel_setting: str = "") -> None:
    """Publish, edit, mark as rented, or withdraw the listing's tracked channel messages."""
    runtime = get_settings()
    target = channel_target(channel_setting or runtime.channel_target_id)
    async with SessionFactory() as session:
        options = await get_channel_settings(session)
        if not options["channel_sync_enabled"]:
            return
        listing = await session.get(Listing, listing_id)
        if listing is None:
            return
        rows = list((await session.scalars(
            select(ChannelPost).where(ChannelPost.listing_id == listing.id).order_by(ChannelPost.message_id)
        )).all())
        if not rows and listing.telegram_channel_id and listing.telegram_channel_message_id:
            legacy_ids = {listing.telegram_channel_message_id}
            legacy_ids.update((await session.scalars(
                select(ListingPhoto.telegram_source_message_id).where(
                    ListingPhoto.listing_id == listing.id,
                    ListingPhoto.telegram_source_message_id.is_not(None),
                )
            )).all())
            for message_id in legacy_ids:
                rows.append(ChannelPost(
                    listing_id=listing.id, chat_id=listing.telegram_channel_id,
                    message_id=message_id, status="published",
                    is_bot_post=listing.source == "bot",
                    is_album_part=listing.telegram_channel_media,
                ))
                session.add(rows[-1])
            await session.flush()

        # A source channel post remains visible while it waits for moderation.
        if listing.status == "pending" and listing.source == "channel":
            return

        if listing.status not in {"active", "rented"}:
            await _delete_posts(bot, session, rows)
            return
        if not target and not listing.channel_chat_id and not listing.telegram_channel_id:
            await _notify_admins(bot, "⚠️ Kanalga post yuborilmadi: CHANNEL_ID yoki CHANNEL_USERNAME sozlanmagan.")
            return
        if listing.status == "rented" and options["channel_rented_action"] == "delete":
            await _delete_posts(bot, session, rows)
            return

        owner = await session.get(User, listing.owner_id)
        photo_rows = list((await session.scalars(
            select(ListingPhoto).where(ListingPhoto.listing_id == listing.id).order_by(ListingPhoto.sort_order).limit(10)
        )).all())
        photo_ids = [item.file_id for item in photo_rows]
        body = _listing_text(listing, owner, "", runtime.channel_username, band=listing.status == "rented")
        bot_user = await _call(bot.get_me, "bot username olish")
        bot_username = bot_user.username if bot_user else ""
        detail_url = f"https://t.me/{bot_username}?start=listing_{listing.id}" if bot_username else runtime.mini_app_url
        contact_username = listing.contact_username or (owner.username if owner else None)
        contact_url = f"https://t.me/{contact_username.lstrip('@')}" if contact_username else None
        if not contact_url and listing.phone_consent and listing.contact_phone:
            contact_url = f"https://wa.me/{re.sub(r'\D', '', listing.contact_phone)}"
        fallback_url = channel_post_url(listing.channel_chat_id, listing.channel_message_id, runtime.channel_username)
        contact_url = contact_url or fallback_url
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Batafsil", url=detail_url)] if detail_url else [],
            [InlineKeyboardButton(text="✉️ Bog‘lanish", url=contact_url)] if contact_url else [],
        ])
        keyboard.inline_keyboard = [row for row in keyboard.inline_keyboard if row]

        media_posts = [row for row in rows if not row.is_control_post and row.status != "deleted"]
        control_posts = [row for row in rows if row.is_control_post and row.status != "deleted"]
        destination = listing.channel_chat_id or listing.telegram_channel_id or target
        has_single_photo = len(photo_ids) == 1
        needs_album = len(photo_ids) > 1

        try:
            if media_posts and len(media_posts) == len(photo_ids) and len(photo_ids) > 1:
                for index, (post, file_id) in enumerate(zip(media_posts, photo_ids)):
                    media = InputMediaPhoto(media=file_id, caption=body if index == 0 else None)
                    await _call(lambda post=post, media=media: bot.edit_message_media(
                        chat_id=destination, message_id=post.message_id, media=media,
                    ), "albomni tahrirlash")
                    post.file_id = file_id
                    post.caption = body if index == 0 else None
                    post.status = "published"
                    post.is_bot_post = True
                if not control_posts:
                    sent_control = await _call(lambda: bot.send_message(
                        chat_id=destination, text=f"📌 UyTop e’loni #{listing.id}", reply_markup=keyboard,
                    ), "tugma postini yuborish")
                    control_posts = [sent_control]
                    await _save_message(session, listing, sent_control, f"📌 UyTop e’loni #{listing.id}", control=True)
                else:
                    control = control_posts[0]
                    await _call(lambda: bot.edit_message_text(
                        chat_id=destination, message_id=control.message_id,
                        text=f"📌 UyTop e’loni #{listing.id}", reply_markup=keyboard,
                    ), "tugma postini tahrirlash")
            elif media_posts and len(photo_ids) == 1 and len(media_posts) == 1:
                await _call(lambda: bot.edit_message_media(
                    chat_id=destination, message_id=media_posts[0].message_id,
                    media=InputMediaPhoto(media=photo_ids[0], caption=body),
                    reply_markup=keyboard,
                ), "rasmli postni tahrirlash")
                media_posts[0].file_id, media_posts[0].caption = photo_ids[0], body
                media_posts[0].status, media_posts[0].is_bot_post = "published", True
                await _delete_posts(bot, session, control_posts)
            elif media_posts and not photo_ids and len(media_posts) == 1 and not media_posts[0].is_album_part:
                await _call(lambda: bot.edit_message_caption(
                    chat_id=destination, message_id=media_posts[0].message_id,
                    caption=body, reply_markup=keyboard,
                ), "rasm osti matnini tahrirlash")
                media_posts[0].caption, media_posts[0].status = body, "published"
                media_posts[0].is_bot_post = True
            elif media_posts and not photo_ids and len(media_posts) == 1 and media_posts[0].file_id is None:
                await _call(lambda: bot.edit_message_text(
                    chat_id=destination, message_id=media_posts[0].message_id,
                    text=body, reply_markup=keyboard, disable_web_page_preview=True,
                ), "matnli postni tahrirlash")
                media_posts[0].caption, media_posts[0].status = body, "published"
                media_posts[0].is_bot_post = True
            else:
                # Telegram cannot change album size or turn text into media in place.
                if media_posts or control_posts:
                    await _delete_posts(bot, session, media_posts + control_posts)
                if needs_album:
                    media_group = [InputMediaPhoto(media=file_id, caption=body if index == 0 else None) for index, file_id in enumerate(photo_ids)]
                    sent = await _call(lambda: bot.send_media_group(chat_id=target, media=media_group), "albom yuborish")
                    for index, message in enumerate(sent):
                        await _save_message(session, listing, message, body if index == 0 else "")
                    control = await _call(lambda: bot.send_message(
                        chat_id=target, text=f"📌 UyTop e’loni #{listing.id}", reply_markup=keyboard,
                    ), "tugma postini yuborish")
                    await _save_message(session, listing, control, f"📌 UyTop e’loni #{listing.id}", control=True)
                    listing.telegram_channel_media = True
                    listing.telegram_channel_id = str(sent[0].chat.id)
                    listing.telegram_channel_message_id = sent[0].message_id
                    listing.telegram_media_group_id = sent[0].media_group_id
                elif has_single_photo:
                    sent = await _call(lambda: bot.send_photo(
                        chat_id=target, photo=photo_ids[0], caption=body, reply_markup=keyboard,
                    ), "rasmli post yuborish")
                    await _save_message(session, listing, sent, body)
                    listing.telegram_channel_media = True
                    listing.telegram_channel_id = str(sent.chat.id)
                    listing.telegram_channel_message_id = sent.message_id
                    listing.telegram_media_group_id = None
                else:
                    sent = await _call(lambda: bot.send_message(
                        chat_id=target, text=body, reply_markup=keyboard, disable_web_page_preview=True,
                    ), "matnli post yuborish")
                    await _save_message(session, listing, sent, body)
                    listing.telegram_channel_media = False
                    listing.telegram_channel_id = str(sent.chat.id)
                    listing.telegram_channel_message_id = sent.message_id
                    listing.telegram_media_group_id = None

            listing.channel_chat_id = str(listing.channel_chat_id or listing.telegram_channel_id or target)
            listing.channel_message_id = listing.telegram_channel_message_id
            listing.source = listing.source or "bot"
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.exception("UyTop e’loni kanal bilan sinxronlanmadi (%s)", type(exc).__name__)
            await _notify_admins(bot, f"⚠️ E’lon #{listing_id} kanalga sinxronlanmadi ({type(exc).__name__}). Railway Deploy Logs va kanal ruxsatlarini tekshiring.")
