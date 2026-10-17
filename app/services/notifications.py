"""Deliver matching saved-search alerts after a listing becomes public."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.db import SessionFactory
from app.models import Listing, Notification, SavedSearch, User


def _matches(filters: dict, listing: Listing) -> bool:
    if filters.get("district") and filters["district"] != listing.district: return False
    if filters.get("deal_type") and filters["deal_type"] != listing.deal_type: return False
    if filters.get("property_type") and filters["property_type"] != listing.property_type: return False
    if filters.get("rooms") not in (None, "") and int(filters["rooms"]) != listing.rooms: return False
    if filters.get("min_price") not in (None, "") and listing.price < Decimal(str(filters["min_price"])): return False
    if filters.get("max_price") not in (None, "") and listing.price > Decimal(str(filters["max_price"])): return False
    if filters.get("min_area") not in (None, "") and (listing.area_m2 is None or listing.area_m2 < Decimal(str(filters["min_area"]))): return False
    if filters.get("max_area") not in (None, "") and (listing.area_m2 is None or listing.area_m2 > Decimal(str(filters["max_area"]))): return False
    if filters.get("amenity") and not set(filters["amenity"]).issubset(set(listing.amenities or [])): return False
    return True


async def notify_saved_search_matches(bot, listing_id: int) -> None:
    async with SessionFactory() as session:
        listing = await session.get(Listing, listing_id)
        if listing is None or listing.status != "active": return
        rows = (await session.execute(select(SavedSearch, User).join(User, User.id == SavedSearch.user_id).where(SavedSearch.notifications_enabled.is_(True), User.notifications_enabled.is_(True), User.status == "active").limit(300))).all()
        for saved_search, user in rows:
            try:
                matched = _matches(saved_search.filters, listing)
            except (ValueError, InvalidOperation, TypeError):
                matched = False
            if not matched: continue
            notification = Notification(user_id=user.id, notification_type="saved_search_match", payload={"listing_id": listing.id, "search_id": saved_search.id}, delivery_status="queued")
            session.add(notification)
            await session.flush()
            try:
                await bot.send_message(user.telegram_id, f"Saqlangan qidiruvingizga mos yangi e’lon: {listing.title}\n📍 {listing.district}\n💰 {listing.price:,.0f} {listing.currency}\nUyTop Mini App’dan batafsil ko‘ring.")
                notification.delivery_status, notification.sent_at = "sent", datetime.now(timezone.utc)
            except Exception:
                notification.delivery_status = "failed"
            await asyncio.sleep(0.04)
        await session.commit()
