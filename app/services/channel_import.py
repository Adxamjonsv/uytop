"""Import structured-enough public channel posts into searchable UyTop listings."""

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.config import Settings
from app.db import SessionFactory
from app.models import ChannelPost, Listing, ListingPhoto, User
from app.services.catalog import get_catalogs
from app.services.channel_settings import get_channel_settings
from app.services.channel_sync import channel_target, sync_listing_to_channel

logger = logging.getLogger(__name__)

_DISTRICT_ALIASES = {
    "yunusobod": ("yunusobod", "юнусабад", "юнусобод"),
    "chilonzor": ("chilonzor", "чиланзар"),
    "mirobod": ("mirobod", "мираба́д", "мирабад"),
    "shayxontohur": ("shayxontohur", "шайхантахур"),
    "yakkasaroy": ("yakkasaroy", "яккасарай"),
    "mirzo ulug‘bek": ("mirzo ulug‘bek", "mirzo ulug'bek", "мирзо-улугбек", "мирзо улугбек"),
    "sergeli": ("sergeli", "сергели"),
    "olmazor": ("olmazor", "алмазар"),
    "uchtepa": ("uchtepa", "учтепа"),
    "yashnobod": ("yashnobod", "яшнабад"),
    "bektemir": ("bektemir", "бектемир"),
    "yangihayot": ("yangihayot", "янгихаёт", "янгахаёт"),
}
_LABEL_LINE = re.compile(r"^(?:narx|narxi|цена|price|tuman|район|district|shahar|город|city|hudud|manzil|адрес|turi|uy turi|deal|bitim|сделка|rooms?|xona(?:lar)?|xona soni|комнат|area|maydon|площадь|mahalla|махалля|telefon|телефон|aloqa|bog.?lanish|murojaat|контакт|связь|contact)\s*[:—-]", re.I)


def _number(raw: str, multiplier: int = 1) -> Decimal:
    value = raw.strip().replace(" ", "").replace("\u00a0", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif value.count(".") > 1 or value.count(",") > 1:
        value = value.replace(".", "").replace(",", "")
    elif "." in value or "," in value:
        separator = "." if "." in value else ","
        left, right = value.rsplit(separator, 1)
        value = left + (("." + right) if len(right) <= 2 else right)
    return Decimal(value) * multiplier


def _extract(text: str, district_names: list[str], channel_username: str) -> dict | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    title_line = next((line for line in lines if not _LABEL_LINE.match(re.sub(r"^[^\wА-Яа-яЁё]+", "", line)) and not re.match(r"^(?:https?://|t\.me/|@|#)", re.sub(r"^[^\wА-Яа-яЁё]+", "", line), re.I)), "")
    title = re.sub(r"^[^\wА-Яа-яЁё]+", "", title_line)
    if len(title) < 5:
        return None

    price_match = re.search(
        r"(?:narx(?:i)?|цена|стоимость|price|💰|💵)\s*[:—-]?\s*([0-9][0-9\s.,]*)\s*(mln|млн|million)?\s*(USD|UZS|сум|\$)?",
        text,
        re.I,
    )
    if not price_match:
        price_match = re.search(r"([0-9][0-9\s.,]*)\s*(mln|млн|million)?\s*(USD|UZS|\$)", text, re.I)
    if not price_match:
        return None
    try:
        price = _number(price_match.group(1), 1_000_000 if price_match.group(2) else 1)
    except InvalidOperation:
        return None
    if price <= 0:
        return None
    currency = "USD" if (price_match.group(3) or "").lower() in {"usd", "$"} else "UZS"

    lowered = text.casefold()
    deal_type = "sale" if any(word in lowered for word in ("sotuv", "продажа", "продаётся", "продается", "sale")) else "daily" if any(word in lowered for word in ("kunlik", "сутки", "посуточ", "daily")) else "rent" if any(word in lowered for word in ("ijara", "аренда", "сдается", "сдаётся", "rent")) else "unknown"
    property_type = "dormitory" if any(word in lowered for word in ("yotoqxona", "общежити", "dormitory")) else "household" if any(word in lowered for word in ("xonadon", "жильё", "жилье")) else "house" if re.search(r"\b(?:hovli|коттедж)\b|(?:uy|house|дом)\s*(?:turi|type|тип)?\s*[:—-]|(?:turi|тип жилья)\s*[:—-]\s*(?:uy|house|дом)", lowered) else "apartment" if any(word in lowered for word in ("kvartira", "квартира", "apartment")) else "unknown"

    district = None
    combined = f" {lowered} "
    for canonical in district_names:
        aliases = _DISTRICT_ALIASES.get(canonical.casefold(), (canonical.casefold(),))
        if any(alias.casefold() in combined for alias in aliases):
            district = canonical
            break
    if district is None:
        return None

    rooms_match = re.search(r"(?:xona(?:lar)?|xona soni|комнат(?:ы)?|rooms?)\s*[:—-]?\s*(\d+)|(\d+)\s*-?\s*(?:xonali|xona(?:lar)?|комнат(?:ы)?|rooms?)", text, re.I)
    area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m²|m2|кв\.?\s*м|м²)", text, re.I)
    floor_match = re.search(r"(?:(\d+)\s*-?\s*(?:qavat|этаж)(?:\s*/\s*(\d+))?)|(?:(?:qavat|этаж)\s*[:—-]?\s*(\d+)(?:\s*/\s*(\d+))?)|(?<!\d)(\d+)\s*/\s*(\d+)", text, re.I)
    amenities_match = re.search(r"(?:qulayliklar|mebel(?: va texnika)?|мебель|удобства)\s*[:—-]\s*([^\n]+)", text, re.I)
    amenities = [part.strip()[:40] for part in re.split(r"[,;]", amenities_match.group(1)) if part.strip()] if amenities_match else []
    neighborhood_match = re.search(r"(?:mahalla|махалля|мфй)\s*[:—-]\s*([^\n,;]+)", text, re.I)
    contact_text = "\n".join(line for line in lines if re.search(r"aloqa|bog.?lanish|murojaat|kontakt|telefon|телефон|тел\.?|связь|contact", line, re.I))
    handles = re.findall(r"(?<![\w])@([A-Za-z][A-Za-z0-9_]{4,31})", contact_text)
    handle = next((item for item in handles if item.casefold() != channel_username.casefold()), None)
    if handle is None:
        links = re.findall(r"(?:https?://)?t\.me/([A-Za-z][A-Za-z0-9_]{4,31})", contact_text, re.I)
        handle = next((item for item in links if item.casefold() != channel_username.casefold()), None)
    if handle is None:
        handles = re.findall(r"(?<![\w])@([A-Za-z][A-Za-z0-9_]{4,31})", text)
        handle = next((item for item in handles if item.casefold() != channel_username.casefold()), None)
    phone_match = re.search(r"(?<!\d)(?:\+?998[\s()-]?)?(?:\d[\s()-]?){9,12}(?!\d)", contact_text)
    phone = re.sub(r"[\s()-]", "", phone_match.group(0)) if phone_match else None
    if phone and phone.startswith("998") and not phone.startswith("+"):
        phone = "+" + phone

    description_lines = [line for line in lines if line != title_line and not _LABEL_LINE.match(re.sub(r"^[^\wА-Яа-яЁё]+", "", line)) and not re.match(r"^[^\wА-Яа-яЁё]*(?:💼|📍|💰|🚪|📐|🆔|☎️|📩)", line) and not re.search(r"aloqa|bog.?lanish|murojaat|kontakt|telefon|телефон|связь|contact", line, re.I)]
    description = "\n".join(description_lines)[:5000]
    return {
        "title": title[:180],
        "price": price,
        "currency": currency,
        "deal_type": deal_type,
        "property_type": property_type,
        "district": district,
        "neighborhood": neighborhood_match.group(1).strip()[:120] if neighborhood_match else None,
        "rooms": int(rooms_match.group(1) or rooms_match.group(2)) if rooms_match else None,
        "area_m2": Decimal(area_match.group(1).replace(",", ".")) if area_match else None,
        "floor": int(floor_match.group(1) or floor_match.group(3) or floor_match.group(5)) if floor_match else None,
        "total_floors": int(floor_match.group(2) or floor_match.group(4) or floor_match.group(6)) if floor_match and (floor_match.group(2) or floor_match.group(4) or floor_match.group(6)) else None,
        "amenities": amenities,
        "description": description,
        "username": handle,
        "phone": phone,
        "photos": [],
    }


def _matches_channel(message: Message, setting: str, source_chat_id: int | None = None, source_username: str | None = None) -> bool:
    target = channel_target(setting)
    candidate_id = source_chat_id if source_chat_id is not None else message.chat.id
    candidate_username = source_username if source_chat_id is not None else message.chat.username
    if not target:
        return False
    if target.lstrip("-").isdigit():
        return str(candidate_id) == target or str(abs(candidate_id)) == target.lstrip("-")
    return (candidate_username or "").casefold() == target.lstrip("@").casefold()


async def _notify_admins(bot: Bot, settings: Settings, message_id: int) -> None:
    note = (
        f"⚠️ Kanal post #{message_id} UyTop qidiruviga kiritilmadi. "
        "Postda narx, Toshkent tumani va e’lon sarlavhasi topilmadi. "
        "Narx va tuman satrlarini aniq yozib, postni tahrirlang."
    )
    for telegram_id in settings.admin_telegram_id_list:
        try:
            await bot.send_message(telegram_id, note)
        except Exception:
            continue


async def import_channel_post(bot: Bot, message: Message, settings: Settings, *, source_chat_id: int | None = None, source_message_id: int | None = None, source_username: str | None = None, sync_after: bool = True) -> None:
    """Create/update a listing from a post in the configured channel or a forwarded copy."""
    if not _matches_channel(message, settings.channel_target_id, source_chat_id, source_username):
        return
    channel_id = str(source_chat_id if source_chat_id is not None else message.chat.id)
    message_id = source_message_id if source_message_id is not None else message.message_id
    group_id = message.media_group_id
    body = message.text or message.caption or ""
    channel_username = source_username or message.chat.username or ""

    async with SessionFactory() as session:
        options = await get_channel_settings(session)
        if not options["channel_import_enabled"]:
            return
        channel_post = await session.scalar(select(ChannelPost).where(ChannelPost.chat_id == channel_id, ChannelPost.message_id == message_id))
        body = message.text or message.caption or ""
        if channel_post and channel_post.is_bot_post and (body or "") == (channel_post.caption or ""):
            return
        listing = await session.scalar(
            select(Listing).where(
                Listing.telegram_channel_id == channel_id,
                Listing.telegram_channel_message_id == message_id,
            )
        )
        if listing is None:
            listing = await session.scalar(select(Listing).where(Listing.channel_chat_id == channel_id, Listing.channel_message_id == message_id))
        if listing is not None and body:
            rented_words = [word.casefold() for word in options["channel_rented_keywords"]]
            if any(word and word in body.casefold() for word in rented_words):
                listing.status = "rented"
                await session.commit()
                await sync_listing_to_channel(bot, listing.id, settings.channel_target_id)
                return
        if listing is None and group_id and not body:
            listing = await session.scalar(
                select(Listing).where(
                    Listing.telegram_channel_id == channel_id,
                    Listing.telegram_media_group_id == group_id,
                )
            )
            if listing is None:
                listing = await session.scalar(select(Listing).where(Listing.channel_chat_id == channel_id, Listing.media_group_id == group_id))
            if listing is not None and message.photo:
                existing = await session.scalar(
                    select(ListingPhoto.id).where(
                        ListingPhoto.listing_id == listing.id,
                        ListingPhoto.telegram_source_message_id == message_id,
                    )
                )
                if existing is None:
                    session.add(ListingPhoto(listing_id=listing.id, file_id=message.photo[-1].file_id, sort_order=message_id, is_cover=False, telegram_source_message_id=message_id))
                if channel_post is None:
                    session.add(ChannelPost(listing_id=listing.id, chat_id=channel_id, message_id=message_id, is_album_part=True, posted_at=message.date, status=listing.status, media_group_id=group_id, file_id=message.photo[-1].file_id, is_bot_post=False))
                await session.commit()
                if sync_after:
                    await sync_listing_to_channel(bot, listing.id, settings.channel_target_id)
            return
        if not body:
            return

        catalogs = await get_catalogs()
        parsed = _extract(body, catalogs["districts"], channel_username)
        if parsed is None:
            await _notify_admins(bot, settings, message.message_id)
            return
        fully_parsed = parsed["deal_type"] != "unknown" and parsed["property_type"] != "unknown"
        status = "active" if options["channel_import_mode"] == "auto" and fully_parsed else "pending"

        if listing is None:
            stable_telegram_id = settings.admin_telegram_id_list[0] if settings.admin_telegram_id_list else None
            if stable_telegram_id is None:
                await _notify_admins(bot, settings, message_id)
                return
            owner = await session.scalar(select(User).where(User.telegram_id == stable_telegram_id))
            if owner is None:
                owner = User(
                    telegram_id=stable_telegram_id,
                    username=parsed["username"],
                    full_name=(message.chat.title or channel_username or "UyTop kanal")[:160],
                    role="owner",
                )
                session.add(owner)
                await session.flush()
            listing = Listing(
                owner_id=owner.id,
                status=status,
                payment_status="paid",
                admin_approved=status == "active",
                telegram_channel_id=channel_id,
                telegram_channel_message_id=message_id,
                telegram_channel_media=bool(message.photo or message.video or message.document or message.animation),
                telegram_media_group_id=group_id,
                source="channel", channel_chat_id=channel_id, channel_message_id=message_id,
                media_group_id=group_id, imported_at=datetime.now(timezone.utc), contact_username=parsed["username"],
                contact_method="both" if parsed["username"] and parsed["phone"] else "telegram" if parsed["username"] or not parsed["phone"] else "phone",
                phone_consent=bool(parsed["phone"]),
                contact_phone=parsed["phone"],
                **{key: parsed[key] for key in ("title", "price", "currency", "deal_type", "property_type", "district", "neighborhood", "rooms", "area_m2", "floor", "total_floors", "amenities", "description")},
            )
            session.add(listing)
            await session.flush()
            if message.photo:
                session.add(ListingPhoto(listing_id=listing.id, file_id=message.photo[-1].file_id, sort_order=0, is_cover=True, telegram_source_message_id=message_id))
        else:
            owner = await session.get(User, listing.owner_id)
            if owner:
                owner.username = parsed["username"]
            listing.contact_phone = parsed["phone"]
            listing.phone_consent = bool(parsed["phone"])
            listing.contact_method = "both" if parsed["username"] and parsed["phone"] else "telegram" if parsed["username"] or not parsed["phone"] else "phone"
            overrides = set(listing.channel_overrides or [])
            for key in ("title", "price", "currency", "deal_type", "property_type", "district", "neighborhood", "rooms", "area_m2", "floor", "total_floors", "amenities", "description"):
                if key not in overrides:
                    setattr(listing, key, parsed[key])
            listing.status = "active" if options["channel_import_mode"] == "auto" and fully_parsed else "pending"
            listing.payment_status = "paid"
            listing.admin_approved = listing.status == "active"
            listing.source = "channel"
            listing.channel_chat_id, listing.channel_message_id = channel_id, message_id
            listing.media_group_id, listing.imported_at = group_id, datetime.now(timezone.utc)
            listing.contact_username = parsed["username"]
            listing.telegram_channel_media = bool(message.photo or message.video or message.document or message.animation)
            listing.telegram_media_group_id = group_id
            if message.photo:
                cover = await session.scalar(
                    select(ListingPhoto).where(ListingPhoto.listing_id == listing.id, ListingPhoto.is_cover.is_(True))
                )
                if cover:
                    cover.file_id = message.photo[-1].file_id
                    cover.telegram_source_message_id = message_id
                else:
                    session.add(ListingPhoto(listing_id=listing.id, file_id=message.photo[-1].file_id, sort_order=0, is_cover=True, telegram_source_message_id=message_id))
        listing_id = listing.id
        if channel_post is None:
            channel_post = ChannelPost(listing_id=listing.id, chat_id=channel_id, message_id=message_id)
            session.add(channel_post)
        channel_post.listing_id = listing.id
        channel_post.is_album_part = bool(group_id)
        channel_post.posted_at = message.date
        channel_post.status = listing.status
        channel_post.media_group_id = group_id
        channel_post.caption = body
        channel_post.file_id = message.photo[-1].file_id if message.photo else None
        channel_post.is_bot_post = False
        listing_id = listing.id
        pending = listing.status == "pending"
        await session.commit()

    if pending:
        keyboard_rows = [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"mod:approve:{listing_id}"), InlineKeyboardButton(text="❌ Rad etish", callback_data=f"mod:reject:{listing_id}")]]
        if settings.mini_app_url.startswith("https://"):
            keyboard_rows.append([InlineKeyboardButton(text="✏️ Panelda tahrirlash", url=settings.mini_app_url.rstrip("/") + f"/admin/listings?status_filter=pending")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        for admin_id in settings.admin_telegram_id_list:
            try:
                await bot.send_message(admin_id, f"📥 Kanaldan yangi e’lon moderatsiyasi · #{listing_id}\\n{parsed['title']}\\n{parsed['district']} · {parsed['price']} {parsed['currency']}", reply_markup=keyboard)
            except Exception:
                continue
    if sync_after:
        await sync_listing_to_channel(bot, listing_id, settings.channel_target_id)
