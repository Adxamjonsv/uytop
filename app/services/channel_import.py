"""Import structured-enough public channel posts into searchable UyTop listings."""

import logging
import re
from decimal import Decimal, InvalidOperation

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select

from app.config import Settings
from app.db import SessionFactory
from app.models import Listing, ListingPhoto, User
from app.services.catalog import get_catalogs
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
_LABEL_LINE = re.compile(r"^(?:narx|narxi|цена|price|tuman|район|district|hudud|manzil|адрес|turi|uy turi|deal|bitim|сделка|rooms?|xona(?:lar)?|xona soni|комнат|area|maydon|площадь|mahalla|махалля|telefon|телефон|aloqa|bog.?lanish|murojaat|контакт|связь|contact)\s*[:—-]", re.I)


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
    deal_type = "sale" if any(word in lowered for word in ("sotuv", "продажа", "продаётся", "продается", "sale")) else "daily" if any(word in lowered for word in ("kunlik", "сутки", "посуточ", "daily")) else "rent"
    property_type = "dormitory" if any(word in lowered for word in ("yotoqxona", "общежити", "dormitory")) else "household" if any(word in lowered for word in ("xonadon", "жильё", "жилье")) else "house" if re.search(r"\b(?:hovli|коттедж)\b|(?:uy|house|дом)\s*(?:turi|type|тип)?\s*[:—-]|(?:turi|тип жилья)\s*[:—-]\s*(?:uy|house|дом)", lowered) else "apartment"

    district = None
    combined = f" {lowered} "
    for canonical in district_names:
        aliases = _DISTRICT_ALIASES.get(canonical.casefold(), (canonical.casefold(),))
        if any(alias.casefold() in combined for alias in aliases):
            district = canonical
            break
    if district is None:
        return None

    rooms_match = re.search(r"(?:xona(?:lar)?|xona soni|комнат(?:ы)?|rooms?)\s*[:—-]?\s*(\d+)|(\d+)\s*(?:xonali|xona(?:lar)?|комнат(?:ы)?|rooms?)", text, re.I)
    area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m²|m2|кв\.?\s*м|м²)", text, re.I)
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
        "description": description,
        "username": handle,
        "phone": phone,
        "photos": [],
    }


def _matches_channel(message: Message, setting: str) -> bool:
    target = channel_target(setting)
    if not target:
        return False
    if target.lstrip("-").isdigit():
        return str(message.chat.id) == target or str(abs(message.chat.id)) == target
    return (message.chat.username or "").casefold() == target.lstrip("@").casefold()


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


async def import_channel_post(bot: Bot, message: Message, settings: Settings) -> None:
    """Create/update a listing from an admin-authored post in the configured channel."""
    if not _matches_channel(message, settings.telegram_channel_id):
        return
    channel_id = str(message.chat.id)
    group_id = message.media_group_id
    body = message.text or message.caption or ""
    channel_username = message.chat.username or ""

    async with SessionFactory() as session:
        listing = await session.scalar(
            select(Listing).where(
                Listing.telegram_channel_id == channel_id,
                Listing.telegram_channel_message_id == message.message_id,
            )
        )
        if listing is None and group_id and not body:
            listing = await session.scalar(
                select(Listing).where(
                    Listing.telegram_channel_id == channel_id,
                    Listing.telegram_media_group_id == group_id,
                )
            )
            if listing is not None and message.photo:
                existing = await session.scalar(
                    select(ListingPhoto.id).where(
                        ListingPhoto.listing_id == listing.id,
                        ListingPhoto.telegram_source_message_id == message.message_id,
                    )
                )
                if existing is None:
                    session.add(ListingPhoto(listing_id=listing.id, file_id=message.photo[-1].file_id, sort_order=message.message_id, is_cover=False, telegram_source_message_id=message.message_id))
                    await session.commit()
            return
        if not body:
            return

        catalogs = await get_catalogs()
        parsed = _extract(body, catalogs["districts"], channel_username)
        if parsed is None:
            await _notify_admins(bot, settings, message.message_id)
            return

        if listing is None:
            stable_telegram_id = -(abs(message.chat.id) * 1_000_000 + message.message_id)
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
                status="active",
                telegram_channel_id=channel_id,
                telegram_channel_message_id=message.message_id,
                telegram_channel_media=bool(message.photo or message.video or message.document or message.animation),
                telegram_media_group_id=group_id,
                contact_method="both" if parsed["username"] and parsed["phone"] else "telegram" if parsed["username"] else "phone",
                phone_consent=bool(parsed["phone"]),
                contact_phone=parsed["phone"],
                **{key: parsed[key] for key in ("title", "price", "currency", "deal_type", "property_type", "district", "neighborhood", "rooms", "area_m2", "description")},
            )
            session.add(listing)
            await session.flush()
            if message.photo:
                session.add(ListingPhoto(listing_id=listing.id, file_id=message.photo[-1].file_id, sort_order=0, is_cover=True, telegram_source_message_id=message.message_id))
        else:
            for key in ("title", "price", "currency", "deal_type", "property_type", "district", "neighborhood", "rooms", "area_m2", "description"):
                setattr(listing, key, parsed[key])
            owner = await session.get(User, listing.owner_id)
            if owner:
                owner.username = parsed["username"]
            listing.contact_phone = parsed["phone"]
            listing.phone_consent = bool(parsed["phone"])
            listing.contact_method = "both" if parsed["username"] and parsed["phone"] else "telegram" if parsed["username"] else "phone"
            listing.status = "active"
            listing.telegram_channel_media = bool(message.photo or message.video or message.document or message.animation)
            listing.telegram_media_group_id = group_id
            if message.photo:
                cover = await session.scalar(
                    select(ListingPhoto).where(ListingPhoto.listing_id == listing.id, ListingPhoto.is_cover.is_(True))
                )
                if cover:
                    cover.file_id = message.photo[-1].file_id
                    cover.telegram_source_message_id = message.message_id
                else:
                    session.add(ListingPhoto(listing_id=listing.id, file_id=message.photo[-1].file_id, sort_order=0, is_cover=True, telegram_source_message_id=message.message_id))
        listing_id = listing.id
        await session.commit()

    await sync_listing_to_channel(bot, listing_id, settings.telegram_channel_id)
