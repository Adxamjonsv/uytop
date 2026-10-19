"""Mini App listing, favorite, image, contact, and report endpoints."""

import logging
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from aiogram.types import BufferedInputFile
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_user
from app.api.schemas import DraftUpdate, ListingCreate, ListingOut, ListingUpdate, NotificationSettingsUpdate, ReportCreate, SavedSearchCreate
from app.db import get_session
from app.models import Admin, Favorite, Inquiry, Listing, ListingDraft, ListingPhoto, ListingView, Report, SavedSearch, User
from app.services.catalog import get_catalogs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["mini-app"])
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_SIGNATURES = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",), "image/gif": (b"GIF87a", b"GIF89a")}


async def _notify_moderators(request: Request, listing_id: int) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    ids = request.app.state.settings.admin_telegram_id_list
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"mod:approve:{listing_id}"), InlineKeyboardButton(text="❌ Rad etish", callback_data=f"mod:reject:{listing_id}")]])
    for telegram_id in ids:
        try: await request.app.state.bot.send_message(telegram_id, f"Mini App’dan yangi e’lon: #{listing_id}", reply_markup=keyboard)
        except Exception as exc: logger.warning("Moderatorga e’lon xabari yuborilmadi (%s)", type(exc).__name__)


@router.get("/draft")
async def get_draft(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    draft = await session.scalar(select(ListingDraft).where(ListingDraft.user_id == user.id, ListingDraft.source == "mini_app"))
    return {"current_step": draft.current_step, "data": draft.data} if draft else {"current_step": 1, "data": {}}


@router.put("/draft")
async def save_draft(data: DraftUpdate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    draft = await session.scalar(select(ListingDraft).where(ListingDraft.user_id == user.id))
    if draft is None:
        draft = ListingDraft(user_id=user.id, source="mini_app", current_step=data.current_step, data=data.data)
        session.add(draft)
    else:
        draft.current_step, draft.data = data.current_step, data.data
    await session.commit()
    return {"saved": True, "current_step": draft.current_step}


async def _listing_out(session: AsyncSession, listing: Listing, favorite_ids: set[int] | None = None) -> dict:
    photos = list((await session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id == listing.id).order_by(ListingPhoto.sort_order))).all())
    result = ListingOut.model_validate(listing).model_dump(mode="json")
    result["photos"] = [f"/api/photos/{quote(photo.file_id, safe='')}" for photo in photos]
    if favorite_ids is not None:
        result["is_favorite"] = listing.id in favorite_ids
    return result


@router.get("/me")
async def me(request: Request, user: User = Depends(current_user)):
    support = request.app.state.settings.support_username.strip().lstrip("@")
    return {"id": user.id, "name": user.full_name, "username": user.username, "role": user.role, "phone": user.phone, "notifications_enabled": user.notifications_enabled, "language_code": user.language_code, "support_username": support}


@router.put("/me/language")
async def update_language(language_code: str = Query(..., pattern="^(uz|ru)$"), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    user.language_code = language_code
    await session.commit()
    return {"language_code": user.language_code}


@router.get("/catalogs")
async def catalogs(user: User = Depends(current_user)):
    return await get_catalogs()


@router.put("/me/notifications")
async def notification_preferences(data: NotificationSettingsUpdate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    user.notifications_enabled = data.notifications_enabled
    await session.commit()
    return {"notifications_enabled": user.notifications_enabled}


@router.get("/listings")
async def list_listings(
    request: Request,
    district: str | None = Query(default=None, max_length=80),
    deal_type: str | None = Query(default=None, pattern="^(rent|sale|daily)$"),
    property_type: str | None = Query(default=None, pattern="^(apartment|household|house|dormitory)$"),
    min_price: float | None = Query(default=None, ge=0), max_price: float | None = Query(default=None, ge=0),
    min_area: float | None = Query(default=None, gt=0), max_area: float | None = Query(default=None, gt=0),
    rooms: int | None = Query(default=None, ge=0, le=100), offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=50),
    sort: str = Query(default="newest", pattern="^(newest|price_asc|price_desc)$"),
    amenity: list[str] | None = Query(default=None, max_length=8),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    query = select(Listing).where(Listing.status == "active")
    if district: query = query.where(Listing.district == district)
    if deal_type: query = query.where(Listing.deal_type == deal_type)
    if property_type: query = query.where(Listing.property_type == property_type)
    if min_price is not None: query = query.where(Listing.price >= min_price)
    if max_price is not None: query = query.where(Listing.price <= max_price)
    if rooms is not None: query = query.where(Listing.rooms == rooms)
    if min_area is not None: query = query.where(Listing.area_m2 >= min_area)
    if max_area is not None: query = query.where(Listing.area_m2 <= max_area)
    for amenity_name in amenity or []:
        query = query.where(Listing.amenities.cast(JSONB).contains([amenity_name[:40]]))
    ordering = {"newest": desc(Listing.created_at), "price_asc": Listing.price.asc(), "price_desc": desc(Listing.price)}[sort]
    items = list((await session.scalars(query.order_by(ordering).offset(offset).limit(limit + 1))).all())
    more = len(items) > limit
    items = items[:limit]
    favorite_ids = set((await session.scalars(select(Favorite.listing_id).where(Favorite.user_id == user.id, Favorite.listing_id.in_([x.id for x in items])))).all()) if items else set()
    return {"items": [await _listing_out(session, item, favorite_ids) for item in items], "has_more": more, "next_offset": offset + len(items)}


@router.get("/listings/{listing_id}")
async def listing_detail(listing_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == "active"))
    if listing is None: raise HTTPException(404, "E’lon topilmadi.")
    view = await session.scalar(select(ListingView).where(ListingView.user_id == user.id, ListingView.listing_id == listing.id))
    if view is None:
        session.add(ListingView(user_id=user.id, listing_id=listing.id))
    else:
        from datetime import datetime, timezone
        view.viewed_at = datetime.now(timezone.utc)
    await session.commit()
    return await _listing_out(session, listing)


@router.post("/listings", status_code=201)
async def create_listing(data: ListingCreate, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    catalogs_data = await get_catalogs()
    if data.district not in catalogs_data["districts"]:
        raise HTTPException(422, "Ro‘yxatdan tuman tanlang.")
    listing = Listing(owner_id=user.id, title=data.title, deal_type=data.deal_type, property_type=data.property_type, status="pending", price=data.price, currency=data.currency, district=data.district, neighborhood=data.neighborhood, address=data.address, rooms=data.rooms, area_m2=data.area_m2, floor=data.floor, total_floors=data.total_floors, description=data.description, amenities=data.amenities, contact_method=data.contact_method, contact_phone=data.contact_phone, phone_consent=data.phone_consent)
    session.add(listing)
    user.role = "owner"
    await session.flush()
    session.add_all([ListingPhoto(listing_id=listing.id, file_id=file_id, sort_order=index, is_cover=index == 0) for index, file_id in enumerate(data.photo_file_ids)])
    await session.commit()
    await session.refresh(listing)
    await _notify_moderators(request, listing.id)
    return {"id": listing.id, "status": listing.status, "message": "E’lon moderator tekshiruviga yuborildi."}


@router.patch("/listings/{listing_id}")
async def update_listing(listing_id: int, data: ListingUpdate, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.owner_id == user.id))
    if listing is None: raise HTTPException(404, "E’lon topilmadi yoki sizga tegishli emas.")
    if listing.status == "archived": raise HTTPException(409, "Arxivlangan e’lonni tahrirlab bo‘lmaydi.")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(listing, key, value)
    if listing.status in {"active", "rejected"}:
        listing.status, listing.rejection_reason = "pending", None
    await session.commit()
    if listing.status == "pending": await _notify_moderators(request, listing.id)
    return {"id": listing.id, "status": listing.status, "message": "O‘zgarishlar moderatsiyaga yuborildi."}


@router.post("/listings/{listing_id}/archive")
async def archive_listing(listing_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.owner_id == user.id))
    if listing is None: raise HTTPException(404, "E’lon topilmadi yoki sizga tegishli emas.")
    listing.status = "archived"
    await session.commit()
    return {"status": "archived"}


@router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.owner_id == user.id))
    if listing is None: raise HTTPException(404, "E’lon topilmadi yoki sizga tegishli emas.")
    listing.status = "archived"
    await session.commit()
    return {"status": "archived", "message": "E’lon arxivga ko‘chirildi."}


@router.post("/listings/{listing_id}/rented")
async def mark_rented(listing_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.owner_id == user.id))
    if listing is None: raise HTTPException(404, "E’lon topilmadi yoki sizga tegishli emas.")
    listing.status = "rented"
    await session.commit()
    return {"status": "rented"}


@router.get("/my/listings")
async def my_listings(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = list((await session.scalars(select(Listing).where(Listing.owner_id == user.id).order_by(desc(Listing.updated_at)))).all())
    items = []
    for row in rows:
        data = await _listing_out(session, row)
        data["contact_phone"], data["phone_consent"] = row.contact_phone, row.phone_consent
        items.append(data)
    return {"items": items}


@router.get("/my/viewed")
async def viewed_listings(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = list((await session.scalars(select(Listing).join(ListingView, ListingView.listing_id == Listing.id).where(ListingView.user_id == user.id, Listing.status == "active").order_by(desc(ListingView.viewed_at)).limit(30))).all())
    return {"items": [await _listing_out(session, row) for row in rows]}


@router.get("/saved-searches")
async def saved_searches(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = list((await session.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(desc(SavedSearch.created_at)))).all())
    return {"items": [{"id": item.id, "name": item.name, "filters": item.filters, "notifications_enabled": item.notifications_enabled} for item in rows]}


@router.post("/saved-searches", status_code=201)
async def create_saved_search(data: SavedSearchCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    safe_keys = {"district", "deal_type", "property_type", "min_price", "max_price", "min_area", "max_area", "rooms", "amenity"}
    filters = {key: value for key, value in data.filters.items() if key in safe_keys and (isinstance(value, (str, int, float, bool)) or (key == "amenity" and isinstance(value, list) and len(value) <= 8 and all(isinstance(v, str) for v in value)))}
    item = SavedSearch(user_id=user.id, name=data.name.strip(), filters=filters)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return {"id": item.id, "name": item.name, "filters": item.filters}


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search(search_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    item = await session.scalar(select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id))
    if item: await session.delete(item); await session.commit()
    return {"deleted": bool(item)}


@router.get("/favorites")
async def favorites(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = list((await session.scalars(select(Listing).join(Favorite, Favorite.listing_id == Listing.id).where(Favorite.user_id == user.id, Listing.status == "active").order_by(desc(Favorite.created_at)))).all())
    return {"items": [await _listing_out(session, row, {row.id}) for row in rows]}


@router.put("/favorites/{listing_id}")
async def add_favorite(listing_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == "active"))
    if listing is None: raise HTTPException(404, "Faol e’lon topilmadi.")
    existing = await session.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.listing_id == listing_id))
    if existing is None: session.add(Favorite(user_id=user.id, listing_id=listing_id))
    await session.commit()
    return {"saved": True}


@router.delete("/favorites/{listing_id}")
async def remove_favorite(listing_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    existing = await session.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.listing_id == listing_id))
    if existing: await session.delete(existing)
    await session.commit()
    return {"saved": False}


@router.post("/listings/{listing_id}/contact")
async def contact_owner(listing_id: int, confirm_phone: bool = False, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == "active"))
    if listing is None: raise HTTPException(404, "Faol e’lon topilmadi.")
    if listing.owner_id == user.id: raise HTTPException(400, "O‘z e’loningizga murojaat qila olmaysiz.")
    owner = await session.get(User, listing.owner_id)
    if not confirm_phone:
        session.add(Inquiry(listing_id=listing.id, renter_id=user.id, owner_id=owner.id, channel="telegram"))
        await session.commit()
    result = {"telegram_url": f"https://t.me/{owner.username}" if owner.username else None, "phone_warning": None, "phone": None}
    if confirm_phone:
        if listing.phone_consent and listing.contact_phone:
            result["phone"] = listing.contact_phone
        else:
            result["phone_warning"] = "Uy egasi telefon raqamini ko‘rsatishga rozilik bermagan."
    elif listing.phone_consent and listing.contact_phone:
        result["phone_warning"] = "Telefon raqamini ko‘rsatish uchun alohida roziligingizni tasdiqlang."
    return result


@router.post("/listings/{listing_id}/reports", status_code=201)
async def report_listing(listing_id: int, data: ReportCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == "active"))
    if listing is None: raise HTTPException(404, "E’lon topilmadi.")
    session.add(Report(reporter_id=user.id, listing_id=listing.id, reason=data.reason, details=data.details))
    await session.commit()
    return {"message": "Shikoyatingiz moderatorlarga yuborildi."}


@router.post("/uploads/photos", status_code=201)
async def upload_photo(request: Request, photo: UploadFile = File(...), user: User = Depends(current_user)):
    content_type = photo.content_type or ""
    signatures = IMAGE_SIGNATURES.get(content_type)
    if not signatures: raise HTTPException(415, "Faqat JPEG, PNG, WEBP yoki GIF rasm yuborish mumkin.")
    raw = await photo.read(MAX_IMAGE_BYTES + 1)
    await photo.close()
    if len(raw) > MAX_IMAGE_BYTES: raise HTTPException(413, "Rasm hajmi 8 MB dan oshmasligi kerak.")
    signature_ok = raw.startswith(signatures)
    if content_type == "image/webp": signature_ok = len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    if not signature_ok: raise HTTPException(415, "Fayl tarkibi rasm formatiga mos kelmadi.")
    bot = request.app.state.bot
    try:
        sent = await bot.send_photo(chat_id=user.telegram_id, photo=BufferedInputFile(raw, filename=photo.filename or "uytop.jpg"), caption="Mini App orqali yuborgan rasmingiz UyTop e’loniga saqlash uchun tayyor.")
        file_id = sent.photo[-1].file_id
    except Exception as exc:
        logger.error("Telegram rasm qabul qilmadi (%s)", type(exc).__name__)
        raise HTTPException(502, "Rasmni Telegram’da saqlab bo‘lmadi. Botga /start yuborganingizni tekshiring.") from exc
    return {"file_id": file_id}


@router.get("/photos/{file_id}")
async def photo_proxy(file_id: str, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    allowed = await session.scalar(select(ListingPhoto.id).join(Listing, Listing.id == ListingPhoto.listing_id).where(ListingPhoto.file_id == file_id, (Listing.status == "active") | (Listing.owner_id == user.id)).limit(1))
    if allowed is None: raise HTTPException(404, "Rasm topilmadi.")
    bot = request.app.state.bot
    try:
        file = await bot.get_file(file_id)
        if not file.file_path: raise HTTPException(404, "Rasm topilmadi.")
        token = request.app.state.settings.bot_token.get_secret_value()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"https://api.telegram.org/file/bot{token}/{file.file_path}")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "image/jpeg")
        if not content_type.startswith("image/"): raise HTTPException(415, "Telegram fayli rasm emas.")
        return Response(response.content, media_type=content_type, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Telegram rasm proksisi ishlamadi (%s)", type(exc).__name__)
        raise HTTPException(502, "Rasmni yuklab bo‘lmadi.") from exc

