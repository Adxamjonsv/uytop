"""Telegram commands, search cards, durable listing drafts, and moderation actions."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import desc, func, select
from sqlalchemy.orm import joinedload

from app.bot.keyboards import DISTRICTS, draft_keyboard, main_menu, photos_keyboard, district_keyboard, property_keyboard, language_keyboard
from app.config import Settings
from app.bot.i18n import tr, language_code
from app.db import SessionFactory
from app.models import Admin, AdminAuditLog, Favorite, Inquiry, Listing, ListingDraft, ListingPhoto, ModerationLog, Notification, User
from app.services.catalog import get_catalogs

router = Router(name="uytop")
_reject_reason_for: dict[int, int] = {}


async def _telegram_user(tg) -> User:
    if tg is None:
        raise RuntimeError("Telegram foydalanuvchisi aniqlanmadi")
    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if user is None:
            user = User(telegram_id=tg.id, username=tg.username, full_name=tg.full_name[:160], language_code=language_code(tg.language_code))
            session.add(user)
        else:
            user.username, user.full_name, user.last_seen_at = tg.username, tg.full_name[:160], datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(user)
        return user


async def _user(message: Message) -> User:
    return await _telegram_user(message.from_user)


async def _callback_user(callback: CallbackQuery) -> User:
    return await _telegram_user(callback.from_user)


def _step_text(step: int) -> str:
    prompts = {
        1: "Uy turi va bitimni yuboring. Masalan: Kvartira | Uzoq muddatli ijara. Uy turi: kvartira, xonadon, uy yoki yotoqxona. Bitim: ijara, sotuv yoki kunlik.",
        2: "Tuman, mahalla va ixtiyoriy manzilni | bilan ajrating. Masalan: Yunusobod | Minor | Amir Temur ko‘chasi. Aniq manzil ommaga ko‘rsatilmaydi.",
        3: "Narx, valyuta, xona, maydon (m²), qavatni | bilan yuboring. Masalan: 4500000 | UZS | 2 | 60 | 5. Qavat noma’lum bo‘lsa 0 yozing.",
        4: "Sarlavha | tavsif | qulayliklar ko‘rinishida yuboring. Qulayliklar vergul bilan: mebel, konditsioner, Wi-Fi, faqat oilaga, hayvonlarga ruxsat.",
        5: "E’lon rasmlarini bittalab yuboring. Birinchi rasm asosiy rasm bo‘ladi. Tugagach «Rasmlar tayyor» tugmasini bosing.",
        6: "Aloqa usulini yuboring: telegram, telefon yoki ikkalasi. Telefonni e’londa ko‘rsatishga rozilik bersangiz, raqam va «roziman» deb yozing. Masalan: telefon | +998901234567 | roziman. Faqat Telegram uchun: telegram.",
        7: "E’lonni tekshirib, pastdagi tugma orqali moderatsiyaga yuboring.",
    }
    return prompts[step]


async def _get_draft(user_id: int, session):
    return await session.scalar(select(ListingDraft).where(ListingDraft.user_id == user_id, ListingDraft.source == "bot"))


async def _show_step(message: Message, step: int, photos: bool = False) -> None:
    if step == 7:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        user = await _user(message)
        async with SessionFactory() as session:
            draft = await _get_draft(user.id, session)
            data = draft.data if draft else {}
        summary = (f"📋 E’lonni tekshiring\n🏠 {data.get('title', '—')}\n📍 {data.get('district', '—')}\n"
                   f"💰 {data.get('price', '—')} {data.get('currency', '')}\n🚪 {data.get('rooms', '—')} xona · {data.get('area_m2') or '—'} m²\n\n"
                   f"{data.get('description', '')}\n\nRasmlar: {len(data.get('photos', []))} ta")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Moderatsiyaga yuborish", callback_data="draft:submit")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="draft:back"), InlineKeyboardButton(text="Bekor qilish", callback_data="draft:cancel")],
        ])
        await message.answer(summary, reply_markup=keyboard)
        return
    await message.answer(_step_text(step), reply_markup=photos_keyboard() if photos else draft_keyboard())


@router.message(CommandStart())
async def start(message: Message, settings: Settings) -> None:
    user = await _user(message)
    is_admin = bool(message.from_user and message.from_user.id in settings.admin_telegram_id_list)
    await message.answer(tr("welcome", user.language_code), reply_markup=main_menu(settings, user.language_code, is_admin))


@router.message(Command("language"))
@router.message(Command("lang"))
@router.message(F.text == "🌐 Til / Язык")
async def choose_language(message: Message, settings: Settings) -> None:
    user = await _user(message)
    await message.answer(tr("language_prompt", user.language_code), reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("language:"))
async def save_language(callback: CallbackQuery, settings: Settings) -> None:
    selected = callback.data.split(":", 1)[1]
    if selected not in {"uz", "ru"}:
        await callback.answer("Til tanlovi noto‘g‘ri.", show_alert=True)
        return
    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if user is None:
            await callback.answer("Avval /start buyrug‘ini yuboring.", show_alert=True)
            return
        user.language_code = selected
        await session.commit()
    await callback.answer()
    is_admin = callback.from_user.id in settings.admin_telegram_id_list
    await callback.message.answer(tr("language_saved", selected), reply_markup=main_menu(settings, selected, is_admin))


@router.message(Command("admin"))
async def admin_panel_link(message: Message, settings: Settings) -> None:
    if not message.from_user or message.from_user.id not in settings.admin_telegram_id_list:
        user = await _user(message)
        await message.answer(tr("admin_only", user.language_code))
        return
    if not settings.mini_app_url.startswith("https://"):
        await message.answer(tr("admin_unconfigured"))
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    language = (await _user(message)).language_code
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=tr("admin_button", language), web_app=WebAppInfo(url=settings.mini_app_url.rstrip("/") + "/admin/telegram-login"))]])
    await message.answer(tr("admin_button", language), reply_markup=keyboard)


@router.message(Command("help"))
@router.message(F.text == "❔ Yordam")
@router.message(F.text == "❔ Помощь")
async def help_command(message: Message, settings: Settings) -> None:
    user = await _user(message)
    support = settings.support_username.strip().lstrip("@")
    keyboard = None
    if support:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=tr("support_button", user.language_code), url=f"https://t.me/{support}")]])
    await message.answer(tr("help", user.language_code), reply_markup=keyboard or main_menu(settings, user.language_code, bool(message.from_user and message.from_user.id in settings.admin_telegram_id_list)))


@router.message(Command("id"))
async def telegram_id_command(message: Message) -> None:
    if message.from_user:
        await message.answer(f"Telegram ID’ingiz: {message.from_user.id}")


@router.message(Command("new"))
@router.message(F.text == "➕ E’lon joylashtirish")
@router.message(F.text == "➕ Разместить объявление")
async def new_listing(message: Message) -> None:
    user = await _user(message)
    async with SessionFactory() as session:
        draft = await _get_draft(user.id, session)
        if draft is None:
            draft = ListingDraft(user_id=user.id, source="bot", current_step=1, data={})
            session.add(draft)
            await session.commit()
        step = draft.current_step
    await _show_step(message, step, photos=step == 5)


@router.message(Command("search"))
@router.message(F.text == "🔎 Uy qidirish")
@router.message(F.text == "🔎 Найти жильё")
async def search_start(message: Message) -> None:
    await _user(message)
    catalogs = await get_catalogs()
    await message.answer("Qaysi tumanda uy qidiryapsiz?", reply_markup=district_keyboard("sd", catalogs["districts"]))


@router.message(F.text == "📍 Hududlar")
@router.message(F.text == "📍 Районы")
async def districts(message: Message) -> None:
    catalogs = await get_catalogs()
    await message.answer("Toshkent tumanlari:", reply_markup=district_keyboard("sd", catalogs["districts"]))


@router.callback_query(F.data.startswith("sd:"))
async def select_search_district(callback: CallbackQuery) -> None:
    await callback.answer()
    value = callback.data.split(":", 1)[1]
    index = "all" if value == "all" else int(value)
    catalogs = await get_catalogs()
    await callback.message.edit_text("Uy turini tanlang:", reply_markup=property_keyboard("st:" + str(index), catalogs["property_types"]))


@router.callback_query(F.data.startswith("st:"))
async def select_search_type(callback: CallbackQuery) -> None:
    await callback.answer()
    _, district_index, property_type = callback.data.split(":", 2)
    await _send_search_page(callback.message, district_index, property_type, 0)


async def _send_search_page(message: Message, district_index: str, property_type: str, offset: int) -> None:
    catalogs = await get_catalogs()
    districts = catalogs["districts"]
    filters = [Listing.status == "active"]
    if district_index != "all":
        if int(district_index) >= len(districts):
            await message.answer("Hududlar ro‘yxati yangilangan. Qidiruvni qayta boshlang.")
            return
        filters.append(Listing.district == districts[int(district_index)])
    if property_type != "all":
        filters.append(Listing.property_type == property_type)
    async with SessionFactory() as session:
        total = await session.scalar(select(func.count()).select_from(Listing).where(*filters)) or 0
        listing = await session.scalar(select(Listing).where(*filters).order_by(desc(Listing.created_at)).offset(offset).limit(1))
        if listing is None:
            await message.answer("Bu hudud va tur bo‘yicha hozircha faol e’lon yo‘q.")
            return
        photo = await session.scalar(select(ListingPhoto).where(ListingPhoto.listing_id == listing.id).order_by(ListingPhoto.sort_order).limit(1))
        district_name = listing.district
        title = listing.title
        price = f"{listing.price:,.0f} {listing.currency}"
        rooms = listing.rooms or "—"
        area = f"{listing.area_m2} m²" if listing.area_m2 else "—"
        floor = listing.floor if listing.floor is not None else "—"
        lid = listing.id
        has_phone = bool(listing.phone_consent and listing.contact_phone)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [[InlineKeyboardButton(text="Batafsil", callback_data=f"detail:{lid}"), InlineKeyboardButton(text="💚 Saqlash", callback_data=f"fav:{lid}")],
            [InlineKeyboardButton(text="Aloqa", callback_data=f"contact:{lid}")],
            [InlineKeyboardButton(text="⬅️", callback_data=f"page:{district_index}:{property_type}:{max(0, offset-1)}"), InlineKeyboardButton(text=f"{offset + 1}/{total}", callback_data="noop"), InlineKeyboardButton(text="➡️", callback_data=f"page:{district_index}:{property_type}:{offset+1}")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    caption = f"🏠 {title}\n📍 {district_name}\n💰 {price}\n🚪 {rooms} xona · {area} · {floor}-qavat"
    if photo:
        await message.answer_photo(photo.file_id, caption=caption, reply_markup=keyboard)
    else:
        await message.answer(caption, reply_markup=keyboard)


@router.callback_query(F.data.startswith("page:"))
async def search_page(callback: CallbackQuery) -> None:
    await callback.answer()
    _, district_index, property_type, offset = callback.data.split(":", 3)
    await _send_search_page(callback.message, district_index, property_type, int(offset))


@router.callback_query(F.data.startswith("detail:"))
async def listing_detail(callback: CallbackQuery) -> None:
    await callback.answer()
    listing_id = int(callback.data.split(":", 1)[1])
    async with SessionFactory() as session:
        listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == "active"))
        if listing is None:
            await callback.message.answer("Bu e’lon endi mavjud emas.")
            return
        text = f"{listing.title}\n\n{listing.description}\n\n📍 {listing.district}\n💰 {listing.price:,.0f} {listing.currency}\n🚪 {listing.rooms or '—'} xona · {listing.area_m2 or '—'} m²"
    await callback.message.answer(text)


@router.callback_query(F.data.startswith("fav:"))
async def favorite_listing(callback: CallbackQuery) -> None:
    user_id = (await _callback_user(callback)).id
    listing_id = int(callback.data.split(":", 1)[1])
    async with SessionFactory() as session:
        existing = await session.scalar(select(Favorite).where(Favorite.user_id == user_id, Favorite.listing_id == listing_id))
        if existing:
            await session.delete(existing)
            text = "Sevimlilardan olib tashlandi."
        else:
            session.add(Favorite(user_id=user_id, listing_id=listing_id))
            text = "Sevimlilarga saqlandi."
        await session.commit()
    await callback.answer(text, show_alert=True)


@router.callback_query(F.data.startswith("contact:"))
async def contact_owner(callback: CallbackQuery) -> None:
    await callback.answer()
    renter = await _callback_user(callback)
    listing_id = int(callback.data.split(":", 1)[1])
    async with SessionFactory() as session:
        row = await session.execute(select(Listing, User).join(User, User.id == Listing.owner_id).where(Listing.id == listing_id, Listing.status == "active"))
        item = row.first()
        if not item:
            await callback.message.answer("Bu e’lon topilmadi.")
            return
        listing, owner = item
        username, phone = owner.username, listing.contact_phone if listing.phone_consent else None
        session.add(Inquiry(listing_id=listing.id, renter_id=renter.id, owner_id=owner.id, channel="telegram"))
        await session.commit()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = []
    if username:
        buttons.append([InlineKeyboardButton(text="Telegram’da yozish", url=f"https://t.me/{username}")])
    if phone:
        buttons.append([InlineKeyboardButton(text="Telefon raqamini ko‘rish", callback_data=f"phone:{listing_id}")])
    if not buttons:
        await callback.message.answer("Uy egasi bilan bog‘lanish ma’lumoti mavjud emas.")
    else:
        await callback.message.answer("Uy egasi bilan bog‘lanish usulini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("phone:"))
async def show_phone(callback: CallbackQuery) -> None:
    await callback.answer()
    listing_id = int(callback.data.split(":", 1)[1])
    async with SessionFactory() as session:
        listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == "active", Listing.phone_consent.is_(True)))
        phone = listing.contact_phone if listing else None
    if phone:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Telefon raqamini ko‘rsatish", callback_data=f"phone_confirm:{listing_id}")]])
        await callback.message.answer("Uy egasining telefon raqami shaxsiy ma’lumot hisoblanadi. Ko‘rishni davom ettirasizmi?", reply_markup=keyboard)
    else:
        await callback.message.answer("Uy egasi telefon raqamini ko‘rsatishga rozilik bermagan.")


@router.callback_query(F.data.startswith("phone_confirm:"))
async def confirm_phone(callback: CallbackQuery) -> None:
    await callback.answer()
    renter = await _callback_user(callback)
    listing_id = int(callback.data.split(":", 1)[1])
    async with SessionFactory() as session:
        listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == "active", Listing.phone_consent.is_(True)))
        phone = listing.contact_phone if listing else None
        if listing:
            await session.refresh(listing)
            session.add(Inquiry(listing_id=listing.id, renter_id=renter.id, owner_id=listing.owner_id, channel="phone"))
            await session.commit()
    if phone:
        await callback.message.answer(f"Uy egasi telefoni: {phone}")
    else:
        await callback.message.answer("Uy egasi telefon raqamini ko‘rsatishga rozilik bermagan.")


@router.message(Command("myads"))
@router.message(F.text == "👤 Profil")
@router.message(F.text == "👤 Профиль")
async def my_ads(message: Message) -> None:
    user = await _user(message)
    async with SessionFactory() as session:
        listings = list((await session.scalars(select(Listing).where(Listing.owner_id == user.id).order_by(desc(Listing.created_at)).limit(15))).all())
    if not listings:
        await message.answer("Sizda hali e’lon yo‘q. «E’lon joylashtirish» tugmasidan boshlang.")
        return
    labels = {"draft": "Qoralama", "pending": "Tekshiruvda", "active": "Faol", "rejected": "Rad etilgan", "rented": "Band", "archived": "Arxiv"}
    await message.answer("Mening e’lonlarim:\n" + "\n".join(f"• {item.title} — {labels[item.status]}" for item in listings))


@router.message(F.text == "💚 Sevimlilar")
@router.message(F.text == "💚 Избранное")
async def favorites(message: Message) -> None:
    user = await _user(message)
    async with SessionFactory() as session:
        listings = list((await session.scalars(select(Listing).join(Favorite, Favorite.listing_id == Listing.id).where(Favorite.user_id == user.id, Listing.status == "active").order_by(desc(Favorite.created_at)).limit(20))).all())
    if not listings:
        await message.answer("Sevimlilarga saqlangan faol e’lon yo‘q.")
        return
    await message.answer("Sevimli e’lonlar:\n" + "\n".join(f"• {item.title} — {item.price:,.0f} {item.currency}" for item in listings))


@router.message(F.text)
async def draft_text(message: Message, settings: Settings) -> None:
    if message.from_user and message.from_user.id in _reject_reason_for:
        listing_id = _reject_reason_for.pop(message.from_user.id)
        await _reject_listing(message, listing_id, message.text or "")
        return
    user = await _user(message)
    async with SessionFactory() as session:
        draft = await _get_draft(user.id, session)
        if draft is None:
            await message.answer("Menyudan kerakli bo‘limni tanlang.", reply_markup=main_menu(settings))
            return
        values = [part.strip() for part in (message.text or "").split("|")]
        data = dict(draft.data)
        try:
            if draft.current_step == 1:
                if len(values) < 2:
                    raise ValueError
                deal = values[1].lower()
                data.update(property_label=values[0], property_type=_property_code(values[0]), deal_type=_deal_code(deal))
            elif draft.current_step == 2:
                if not values[0]: raise ValueError
                catalog = await get_catalogs()
                if values[0] not in catalog["districts"]: raise ValueError
                data.update(district=values[0], neighborhood=values[1] if len(values) > 1 else "", address=values[2] if len(values) > 2 else "")
            elif draft.current_step == 3:
                if len(values) < 5: raise ValueError
                price = Decimal(values[0].replace(" ", "").replace(",", ""))
                rooms, area, floor = int(values[2]), (Decimal(values[3]) if values[3] else None), int(values[4])
                if values[1].upper() not in {"UZS", "USD"} or price <= 0 or rooms < 0 or (area is not None and area <= 0) or floor < 0: raise ValueError
                data.update(price=str(price), currency=values[1].upper()[:3], rooms=rooms, area_m2=str(area) if area else None, floor=floor)
            elif draft.current_step == 4:
                if len(values) < 2 or not values[0] or not values[1]: raise ValueError
                data.update(title=values[0][:180], description=values[1][:5000], amenities=[x.strip() for x in (values[2].split(",") if len(values) > 2 else []) if x.strip()][:20])
            elif draft.current_step == 5:
                await message.answer("Rasmni surat ko‘rinishida yuboring yoki «Rasmlar tayyor» tugmasini bosing.", reply_markup=photos_keyboard())
                return
            elif draft.current_step == 6:
                method = values[0].lower()
                if method not in {"telegram", "telefon", "ikkalasi", "both"}: raise ValueError
                data["contact_method"] = {"telefon": "phone", "ikkalasi": "both"}.get(method, method)
                data["contact_phone"] = values[1] if len(values) > 1 else None
                data["phone_consent"] = len(values) > 2 and values[2].lower() in {"roziman", "ha", "yes"}
                if data["contact_method"] in {"phone", "both"} and not data["contact_phone"]: raise ValueError
                if data["contact_phone"] and not data["phone_consent"]: raise ValueError
        except (ValueError, InvalidOperation, KeyError):
            await message.answer("Kiritilgan ma’lumot formati noto‘g‘ri. Ko‘rsatilgan namuna bo‘yicha qayta yuboring.", reply_markup=draft_keyboard())
            return
        draft.data = data
        draft.current_step += 1
        await session.commit()
        step = draft.current_step
    await _show_step(message, step, photos=step == 5)


def _property_code(value: str) -> str:
    text = value.lower()
    for keyword, code in [("kvart", "apartment"), ("xonadon", "household"), ("yotoq", "dormitory"), ("uy", "house")]:
        if keyword in text: return code
    raise ValueError


def _deal_code(value: str) -> str:
    if "kun" in value: return "daily"
    if "sot" in value: return "sale"
    if "ijara" in value: return "rent"
    raise ValueError


@router.message(F.photo)
async def draft_photo(message: Message) -> None:
    user = await _user(message)
    file_id = message.photo[-1].file_id
    async with SessionFactory() as session:
        draft = await _get_draft(user.id, session)
        if draft is None or draft.current_step != 5:
            return
        data = dict(draft.data)
        photos = list(data.get("photos", []))
        if len(photos) >= 12:
            await message.answer("Ko‘pi bilan 12 ta rasm yuborish mumkin.")
            return
        photos.append(file_id)
        data["photos"] = photos
        draft.data = data
        await session.commit()
    await message.answer(f"Rasm saqlandi ({len(photos)}/12). Yana rasm yuboring yoki tugmani bosing.", reply_markup=photos_keyboard())


@router.callback_query(F.data == "draft:photos_done")
async def photos_done(callback: CallbackQuery) -> None:
    await callback.answer()
    user = await _callback_user(callback)
    async with SessionFactory() as session:
        draft = await _get_draft(user.id, session)
        if not draft or draft.current_step != 5: return
        draft.current_step = 6
        await session.commit()
    await _show_step(callback.message, 6)


@router.callback_query(F.data == "draft:back")
async def draft_back(callback: CallbackQuery) -> None:
    await callback.answer()
    user = await _callback_user(callback)
    async with SessionFactory() as session:
        draft = await _get_draft(user.id, session)
        if not draft: return
        draft.current_step = max(1, draft.current_step - 1)
        step = draft.current_step
        await session.commit()
    await _show_step(callback.message, step, photos=step == 5)


@router.callback_query(F.data == "draft:cancel")
async def draft_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Qoralama saqlab qolindi.")
    user = await _callback_user(callback)
    async with SessionFactory() as session:
        draft = await _get_draft(user.id, session)
        if draft:
            draft.current_step = 1
            await session.commit()
    await callback.message.answer("Qoralama saqlandi. Keyin «E’lon joylashtirish»ni bosing.")


@router.callback_query(F.data == "draft:submit")
async def submit_draft(callback: CallbackQuery, settings: Settings) -> None:
    await callback.answer()
    user = await _callback_user(callback)
    async with SessionFactory() as session:
        draft = await _get_draft(user.id, session)
        if not draft or draft.current_step != 7:
            await callback.message.answer("Qoralama topilmadi. /new orqali boshlang.")
            return
        data = draft.data
        listing = Listing(owner_id=user.id, title=data["title"], deal_type=data["deal_type"], property_type=data["property_type"], status="pending", price=Decimal(data["price"]), currency=data["currency"], district=data["district"], neighborhood=data.get("neighborhood") or None, address=data.get("address") or None, rooms=data["rooms"], area_m2=Decimal(data["area_m2"]) if data.get("area_m2") else None, floor=data["floor"], description=data["description"], amenities=data.get("amenities", []), contact_method=data["contact_method"], contact_phone=data.get("contact_phone"), phone_consent=data.get("phone_consent", False))
        user.role = "owner"
        session.add(listing)
        await session.flush()
        session.add_all([ListingPhoto(listing_id=listing.id, file_id=file_id, sort_order=index, is_cover=index == 0) for index, file_id in enumerate(data.get("photos", []))])
        await session.delete(draft)
        await session.commit()
        listing_id = listing.id
    await callback.message.answer(f"✅ E’lon #{listing_id} moderator tekshiruviga yuborildi. Tasdiqlanmaguncha qidiruvda ko‘rinmaydi.")
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    moderation_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"mod:approve:{listing_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"mod:reject:{listing_id}"),
    ]])
    for admin_telegram_id in settings.admin_telegram_id_list:
        try:
            await callback.bot.send_message(admin_telegram_id, f"Yangi e’lon moderatsiyaga keldi: #{listing_id}", reply_markup=moderation_keyboard)
        except Exception:
            continue


@router.message(F.text == "Rasmlar tayyor")
async def photo_text_done(message: Message) -> None:
    await message.answer("Pastdagi «Rasmlar tayyor» tugmasini bosing.", reply_markup=photos_keyboard())


@router.callback_query(F.data.startswith("mod:approve:"))
async def approve_listing(callback: CallbackQuery, settings: Settings) -> None:
    if callback.from_user.id not in settings.admin_telegram_id_list:
        await callback.answer("Bu amal faqat moderatorlar uchun.", show_alert=True)
        return
    await callback.answer()
    listing_id = int(callback.data.rsplit(":", 1)[1])
    approved = False
    async with SessionFactory() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == callback.from_user.id))
        listing = await session.get(Listing, listing_id)
        if listing and listing.status == "pending":
            listing.status = "active"
            if admin: listing.moderated_by = admin.id
            if admin:
                session.add(ModerationLog(listing_id=listing.id, moderator_id=admin.id, action="approved"))
                session.add(AdminAuditLog(admin_id=admin.id, action="listing_approved", entity_type="listing", entity_id=str(listing.id), details={}))
            notification = Notification(user_id=listing.owner_id, notification_type="listing_approved", payload={"listing_id": listing.id}, delivery_status="queued")
            session.add(notification)
            await session.commit()
            await callback.message.edit_text(f"✅ #{listing_id} e’lon tasdiqlandi.")
            owner = await session.get(User, listing.owner_id)
            try:
                await callback.bot.send_message(owner.telegram_id, f"E’loningiz tasdiqlandi va qidiruvda ko‘rinmoqda: #{listing_id}")
                notification.delivery_status, notification.sent_at = "sent", datetime.now(timezone.utc)
            except Exception:
                notification.delivery_status = "failed"
            await session.commit()
            approved = True
    if approved:
        from app.services.notifications import notify_saved_search_matches
        await notify_saved_search_matches(callback.bot, listing_id)


@router.callback_query(F.data.startswith("mod:reject:"))
async def request_rejection_reason(callback: CallbackQuery, settings: Settings) -> None:
    if callback.from_user.id not in settings.admin_telegram_id_list:
        await callback.answer("Bu amal faqat moderatorlar uchun.", show_alert=True)
        return
    await callback.answer()
    if callback.from_user is None: return
    _reject_reason_for[callback.from_user.id] = int(callback.data.rsplit(":", 1)[1])
    await callback.message.answer(f"#{callback.data.rsplit(':', 1)[1]} e’lonni rad etish sababini yozing:")


async def _reject_listing(message: Message, listing_id: int, reason: str) -> None:
    async with SessionFactory() as session:
        listing = await session.get(Listing, listing_id)
        if not listing or listing.status != "pending":
            await message.answer("Kutilayotgan e’lon topilmadi.")
            return
        listing.status, listing.rejection_reason = "rejected", reason[:1000]
        moderator = await session.scalar(select(Admin).where(Admin.telegram_id == message.from_user.id))
        if moderator:
            listing.moderated_by = moderator.id
            session.add(ModerationLog(listing_id=listing.id, moderator_id=moderator.id, action="rejected", reason=reason[:1000]))
            session.add(AdminAuditLog(admin_id=moderator.id, action="listing_rejected", entity_type="listing", entity_id=str(listing.id), details={"reason": reason[:1000]}))
        notification = Notification(user_id=listing.owner_id, notification_type="listing_rejected", payload={"listing_id": listing.id, "reason": reason[:1000]}, delivery_status="queued")
        session.add(notification)
        await session.commit()
        owner = await session.get(User, listing.owner_id)
        telegram_id = owner.telegram_id
        notification_id = notification.id
    try:
        await message.bot.send_message(telegram_id, f"E’loningiz rad etildi. Sabab: {reason[:1000]}")
        delivery_status = "sent"
    except Exception:
        delivery_status = "failed"
    async with SessionFactory() as session:
        notification = await session.get(Notification, notification_id)
        if notification:
            notification.delivery_status = delivery_status
            if delivery_status == "sent": notification.sent_at = datetime.now(timezone.utc)
            await session.commit()

