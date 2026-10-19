"""Session-protected admin panel with CSRF validation and audit logging."""

import hmac
import secrets
import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pwdlib import PasswordHash
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_session
from app.models import Admin, AdminAuditLog, Listing, ModerationLog, Notification, PlatformSetting, Report, User
from app.security import validate_telegram_init_data

router = APIRouter(prefix="/admin", tags=["admin"])
password_hasher = PasswordHash.recommended()


def _serializer(request: Request) -> URLSafeTimedSerializer:
    secret = request.app.state.settings.secret_key.get_secret_value()
    return URLSafeTimedSerializer(secret, salt="uytop-admin-session")


def _csrf(request: Request) -> str:
    token = request.cookies.get("uytop_csrf", "")
    if not token or not hmac.compare_digest(token, request.headers.get("x-csrf-token", "") or request.query_params.get("csrf", "")):
        raise HTTPException(403, "Forma muddati tugagan. Sahifani yangilang.")
    return token


def _secure_cookie(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"


async def _admin(request: Request, session: AsyncSession) -> Admin:
    cookie = request.cookies.get("uytop_admin", "")
    try:
        admin_id = _serializer(request).loads(cookie, max_age=request.app.state.settings.admin_session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Admin panelga qayta kiring.") from None
    admin = await session.get(Admin, int(admin_id))
    if admin is None or not admin.is_active:
        raise HTTPException(401, "Admin hisobi faol emas.")
    return admin


def _templates(request: Request):
    return request.app.state.templates


async def _require_superadmin(request: Request, session: AsyncSession) -> Admin:
    admin = await _admin(request, session)
    if admin.role != "superadmin":
        raise HTTPException(403, "Bu amal faqat superadmin uchun.")
    return admin


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    csrf = secrets.token_urlsafe(32)
    response = _templates(request).TemplateResponse(request=request, name="login.html", context={"csrf": csrf, "error": None})
    response.set_cookie("uytop_csrf", csrf, httponly=False, secure=_secure_cookie(request), samesite="strict", max_age=1800)
    return response


@router.get("/telegram-login", response_class=HTMLResponse)
async def telegram_login_page():
    return HTMLResponse("""<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UyTop admin</title><body style="font:16px sans-serif;padding:2rem"><p id="status">Telegram orqali administrator tekshiruvi...</p>
<script src="https://telegram.org/js/telegram-web-app.js"></script><script>
(async()=>{const status=document.getElementById("status");const tg=window.Telegram?.WebApp;tg?.ready();
if(!tg?.initData){status.textContent="Admin panelni bot ichidagi Admin panel tugmasidan oching.";return;}
try{const r=await fetch("/admin/telegram-auth",{method:"POST",headers:{Authorization:"tma "+tg.initData}});
const data=await r.json();if(!r.ok)throw new Error(data.detail||"Kirish rad etildi.");location.replace(data.redirect||"/admin");
}catch(e){status.textContent=e.message;}})();
</script></body></html>""")


@router.post("/telegram-auth")
async def telegram_auth(request: Request, session: AsyncSession = Depends(get_session)):
    authorization = request.headers.get("Authorization", "")
    init_data = authorization[4:] if authorization.lower().startswith("tma ") else ""
    signed_user = validate_telegram_init_data(init_data, request.app.state.settings)
    admin = await session.scalar(select(Admin).where(Admin.telegram_id == signed_user["id"], Admin.is_active.is_(True)))
    if admin is None:
        raise HTTPException(403, "Bu Telegram akkaunti administratorlar ro‘yxatida yo‘q.")
    response = JSONResponse({"ok": True, "redirect": "/admin"})
    response.set_cookie("uytop_admin", _serializer(request).dumps(admin.id), httponly=True, secure=_secure_cookie(request), samesite="lax", max_age=request.app.state.settings.admin_session_max_age_seconds, path="/")
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie("uytop_csrf", csrf_token, httponly=False, secure=_secure_cookie(request), samesite="strict", max_age=1800, path="/")
    return response


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...), csrf: str = Form(...), session: AsyncSession = Depends(get_session)):
    cookie_csrf = request.cookies.get("uytop_csrf", "")
    if not cookie_csrf or not hmac.compare_digest(cookie_csrf, csrf):
        raise HTTPException(403, "Forma muddati tugagan. Sahifani qayta oching.")
    admin = await session.scalar(select(Admin).where(Admin.username == username.strip(), Admin.is_active.is_(True)))
    if admin is None or not password_hasher.verify(password, admin.password_hash):
        response = _templates(request).TemplateResponse(request=request, name="login.html", context={"csrf": cookie_csrf, "error": "Login yoki parol noto‘g‘ri."}, status_code=401)
        response.set_cookie("uytop_csrf", cookie_csrf, httponly=False, secure=_secure_cookie(request), samesite="strict", max_age=1800)
        return response
    response = RedirectResponse("/admin", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie("uytop_admin", _serializer(request).dumps(admin.id), httponly=True, secure=_secure_cookie(request), samesite="lax", max_age=request.app.state.settings.admin_session_max_age_seconds)
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie("uytop_csrf", csrf_token, httponly=False, secure=_secure_cookie(request), samesite="strict", max_age=1800)
    return response


@router.post("/logout")
async def logout(request: Request, csrf: str = Form(...)):
    if not hmac.compare_digest(request.cookies.get("uytop_csrf", ""), csrf):
        raise HTTPException(403, "Forma muddati tugagan.")
    response = RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)
    response.delete_cookie("uytop_admin")
    response.delete_cookie("uytop_csrf")
    return response


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    try:
        admin = await _admin(request, session)
    except HTTPException:
        return RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)
    total_users = await session.scalar(select(func.count()).select_from(User)) or 0
    active_listings = await session.scalar(select(func.count()).select_from(Listing).where(Listing.status == "active")) or 0
    pending_listings = await session.scalar(select(func.count()).select_from(Listing).where(Listing.status == "pending")) or 0
    open_reports = await session.scalar(select(func.count()).select_from(Report).where(Report.status.in_(["open", "reviewing"]))) or 0
    new_today = await session.scalar(select(func.count()).select_from(Listing).where(Listing.created_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))) or 0
    return _templates(request).TemplateResponse(request=request, name="dashboard.html", context={"admin": admin, "csrf": request.cookies.get("uytop_csrf", ""), "total_users": total_users, "active_listings": active_listings, "pending_listings": pending_listings, "open_reports": open_reports, "new_today": new_today})


@router.get("/listings", response_class=HTMLResponse)
async def listings_page(request: Request, status_filter: str = "pending", q: str = "", session: AsyncSession = Depends(get_session)):
    try: admin = await _admin(request, session)
    except HTTPException: return RedirectResponse("/admin/login", status_code=303)
    if status_filter not in {"pending", "active", "rejected", "rented", "archived", "all"}: status_filter = "pending"
    query = select(Listing).order_by(desc(Listing.created_at)).limit(100)
    if status_filter != "all": query = query.where(Listing.status == status_filter)
    if q.strip(): query = query.where(Listing.title.ilike(f"%{q.strip()[:80]}%") | Listing.district.ilike(f"%{q.strip()[:80]}%"))
    rows = list((await session.scalars(query)).all())
    owner_ids = {row.owner_id for row in rows}
    owners = {owner.id: owner for owner in (await session.scalars(select(User).where(User.id.in_(owner_ids)))).all()} if owner_ids else {}
    return _templates(request).TemplateResponse(request=request, name="listings.html", context={"admin": admin, "csrf": request.cookies.get("uytop_csrf", ""), "items": rows, "owners": owners, "status_filter": status_filter})


@router.post("/listings/{listing_id}/moderate")
async def moderate_listing(listing_id: int, request: Request, action: str = Form(...), reason: str = Form(""), title: str = Form(""), price: str = Form(""), district: str = Form(""), description: str = Form(""), csrf: str = Form(...), session: AsyncSession = Depends(get_session)):
    if not hmac.compare_digest(request.cookies.get("uytop_csrf", ""), csrf): raise HTTPException(403, "Forma muddati tugagan.")
    admin = await _admin(request, session)
    listing = await session.get(Listing, listing_id)
    if listing is None: raise HTTPException(404, "E’lon topilmadi.")
    if action not in {"approve", "reject", "archive", "hide", "edit"}: raise HTTPException(400, "Amal noto‘g‘ri.")
    if action == "edit":
        try: edited_price = Decimal(price)
        except InvalidOperation: raise HTTPException(422, "Narx noto‘g‘ri.") from None
        if len(title.strip()) < 5 or edited_price <= 0 or not district.strip() or len(description.strip()) < 10:
            raise HTTPException(422, "Sarlavha, narx, tuman va tavsifni to‘ldiring.")
        listing.title, listing.price, listing.district, listing.description = title.strip()[:180], edited_price, district.strip()[:80], description.strip()[:5000]
        if listing.status == "active": listing.status = "pending"
        listing.moderated_by = admin.id
        session.add(AdminAuditLog(admin_id=admin.id, action="listing_edited", entity_type="listing", entity_id=str(listing.id), details={"status": listing.status}))
        await session.commit()
        return RedirectResponse("/admin/listings?status_filter=" + listing.status, status_code=303)
    if action == "reject" and len(reason.strip()) < 5: raise HTTPException(400, "Rad etish sababi kamida 5 belgi bo‘lishi kerak.")
    if action == "approve": listing.status, log_action = "active", "approved"
    elif action == "reject": listing.status, listing.rejection_reason, log_action = "rejected", reason.strip()[:1000], "rejected"
    elif action == "archive": listing.status, log_action = "archived", "hidden"
    else: listing.status, log_action = "archived", "hidden"
    listing.moderated_by = admin.id
    session.add(ModerationLog(listing_id=listing.id, moderator_id=admin.id, action=log_action, reason=reason.strip() or None))
    session.add(AdminAuditLog(admin_id=admin.id, action=f"listing_{action}", entity_type="listing", entity_id=str(listing.id), details={"status": listing.status, "reason": reason[:1000]}))
    owner = await session.get(User, listing.owner_id)
    if action in {"approve", "reject"}:
        notification_text = f"E’loningiz tasdiqlandi: #{listing.id}" if action == "approve" else f"E’loningiz rad etildi. Sabab: {reason.strip()}"
        session.add(Notification(user_id=owner.id, notification_type=f"listing_{action}", payload={"listing_id": listing.id, "message": notification_text}, delivery_status="queued"))
    owner_tg_id = owner.telegram_id
    await session.commit()
    if action in {"approve", "reject"}:
        try:
            await request.app.state.bot.send_message(owner_tg_id, notification_text)
            notification = await session.scalar(select(Notification).where(Notification.user_id == owner.id, Notification.notification_type == f"listing_{action}").order_by(desc(Notification.created_at)))
            if notification:
                notification.delivery_status, notification.sent_at = "sent", datetime.now(timezone.utc)
                await session.commit()
        except Exception:
            pass
    if action == "approve":
        from app.services.notifications import notify_saved_search_matches
        await notify_saved_search_matches(request.app.state.bot, listing.id)
    return RedirectResponse("/admin/listings?status_filter=pending", status_code=303)


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, q: str = "", session: AsyncSession = Depends(get_session)):
    try: admin = await _admin(request, session)
    except HTTPException: return RedirectResponse("/admin/login", status_code=303)
    query = select(User).order_by(desc(User.created_at)).limit(100)
    if q.strip().isdigit(): query = query.where(User.telegram_id == int(q.strip()))
    elif q.strip(): query = query.where(User.full_name.ilike(f"%{q.strip()[:80]}%"))
    items = list((await session.scalars(query)).all())
    return _templates(request).TemplateResponse(request=request, name="users.html", context={"admin": admin, "csrf": request.cookies.get("uytop_csrf", ""), "items": items, "q": q})


@router.post("/users/{user_id}/block")
async def block_user(user_id: int, request: Request, csrf: str = Form(...), session: AsyncSession = Depends(get_session)):
    if not hmac.compare_digest(request.cookies.get("uytop_csrf", ""), csrf): raise HTTPException(403, "Forma muddati tugagan.")
    admin = await _require_superadmin(request, session)
    user = await session.get(User, user_id)
    if not user: raise HTTPException(404, "Foydalanuvchi topilmadi.")
    user.status = "blocked" if user.status == "active" else "active"
    session.add(AdminAuditLog(admin_id=admin.id, action=f"user_{user.status}", entity_type="user", entity_id=str(user.id), details={}))
    await session.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, session: AsyncSession = Depends(get_session)):
    try: admin = await _admin(request, session)
    except HTTPException: return RedirectResponse("/admin/login", status_code=303)
    items = list((await session.scalars(select(Report).order_by(desc(Report.created_at)).limit(100))).all())
    return _templates(request).TemplateResponse(request=request, name="reports.html", context={"admin": admin, "csrf": request.cookies.get("uytop_csrf", ""), "items": items})


@router.post("/reports/{report_id}/resolve")
async def resolve_report(report_id: int, request: Request, action: str = Form("resolved"), csrf: str = Form(...), session: AsyncSession = Depends(get_session)):
    if not hmac.compare_digest(request.cookies.get("uytop_csrf", ""), csrf): raise HTTPException(403, "Forma muddati tugagan.")
    admin = await _admin(request, session)
    report = await session.get(Report, report_id)
    if not report: raise HTTPException(404, "Shikoyat topilmadi.")
    report.status = "dismissed" if action == "dismissed" else "resolved"
    report.resolved_by, report.resolved_at = admin.id, datetime.now(timezone.utc)
    session.add(AdminAuditLog(admin_id=admin.id, action=f"report_{report.status}", entity_type="report", entity_id=str(report.id), details={}))
    await session.commit()
    return RedirectResponse("/admin/reports", status_code=303)


@router.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request, session: AsyncSession = Depends(get_session)):
    try: admin = await _admin(request, session)
    except HTTPException: return RedirectResponse("/admin/login", status_code=303)
    items = list((await session.scalars(select(AdminAuditLog).order_by(desc(AdminAuditLog.created_at)).limit(200))).all())
    return _templates(request).TemplateResponse(request=request, name="audit.html", context={"admin": admin, "csrf": request.cookies.get("uytop_csrf", ""), "items": items})


@router.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request, sent: int | None = None, failed: int | None = None, session: AsyncSession = Depends(get_session)):
    try: admin = await _admin(request, session)
    except HTTPException: return RedirectResponse("/admin/login", status_code=303)
    result = {"sent": sent, "failed": failed} if sent is not None and failed is not None else None
    return _templates(request).TemplateResponse(request=request, name="broadcast.html", context={"admin": admin, "csrf": request.cookies.get("uytop_csrf", ""), "result": result})


@router.post("/broadcast", response_class=HTMLResponse)
async def broadcast(request: Request, message: str = Form(...), csrf: str = Form(...), session: AsyncSession = Depends(get_session)):
    if not hmac.compare_digest(request.cookies.get("uytop_csrf", ""), csrf): raise HTTPException(403, "Forma muddati tugagan.")
    admin = await _require_superadmin(request, session)
    text_message = message.strip()
    if not text_message or len(text_message) > 3500: raise HTTPException(422, "Xabar 1–3500 belgi oralig‘ida bo‘lishi kerak.")
    users = list((await session.scalars(select(User).where(User.status == "active", User.notifications_enabled.is_(True)))).all())
    result = {"sent": 0, "failed": 0}
    for user in users:
        notification = Notification(user_id=user.id, notification_type="broadcast", payload={"message": text_message}, delivery_status="queued")
        session.add(notification)
        try:
            await request.app.state.bot.send_message(user.telegram_id, text_message)
            notification.delivery_status, notification.sent_at = "sent", datetime.now(timezone.utc)
            result["sent"] += 1
        except Exception:
            notification.delivery_status = "failed"
            result["failed"] += 1
        await session.flush()
        await asyncio.sleep(0.04)
    session.add(AdminAuditLog(admin_id=admin.id, action="broadcast", entity_type="users", details={**result, "recipient_count": len(users)}))
    await session.commit()
    return RedirectResponse(f"/admin/broadcast?sent={result['sent']}&failed={result['failed']}", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session: AsyncSession = Depends(get_session)):
    try: admin = await _admin(request, session)
    except HTTPException: return RedirectResponse("/admin/login", status_code=303)
    admins = list((await session.scalars(select(Admin).order_by(Admin.username))).all())
    from app.bot.keyboards import DISTRICTS
    district_setting = await session.get(PlatformSetting, "districts")
    property_setting = await session.get(PlatformSetting, "property_types")
    districts = district_setting.value if district_setting else DISTRICTS
    from app.services.catalog import DEFAULT_PROPERTY_TYPES
    property_types = property_setting.value if property_setting else DEFAULT_PROPERTY_TYPES
    property_lines = "\n".join(f"{item['code']} | {item['label']}" for item in property_types)
    return _templates(request).TemplateResponse(request=request, name="settings.html", context={"admin": admin, "csrf": request.cookies.get("uytop_csrf", ""), "admins": admins, "districts": districts, "property_lines": property_lines})


@router.post("/settings/catalogs")
async def update_catalogs(request: Request, districts_text: str = Form(...), property_types_text: str = Form(...), csrf: str = Form(...), session: AsyncSession = Depends(get_session)):
    if not hmac.compare_digest(request.cookies.get("uytop_csrf", ""), csrf): raise HTTPException(403, "Forma muddati tugagan.")
    admin = await _require_superadmin(request, session)
    districts = list(dict.fromkeys(line.strip() for line in districts_text.splitlines() if line.strip()))
    if not districts or len(districts) > 50 or any(len(name) > 80 for name in districts):
        raise HTTPException(422, "1 dan 50 tagacha, har biri 80 belgidan oshmaydigan tuman kiriting.")
    props = []
    for line in property_types_text.splitlines():
        if not line.strip(): continue
        parts = [part.strip() for part in line.split("|", 1)]
        if len(parts) != 2 or not parts[1] or len(parts[1]) > 40: raise HTTPException(422, "Uy turi code | nom ko‘rinishida bo‘lsin.")
        props.append({"code": parts[0], "label": parts[1]})
    allowed_codes = {"apartment", "household", "house", "dormitory"}
    if {item["code"] for item in props} != allowed_codes or len(props) != len(allowed_codes):
        raise HTTPException(422, "Uy turlari apartment, household, house va dormitory kodlarini bir martadan o‘z ichiga olishi kerak.")
    for key, value in (("districts", districts), ("property_types", props)):
        setting = await session.get(PlatformSetting, key)
        if setting is None: session.add(PlatformSetting(key=key, value=value))
        else: setting.value = value
    session.add(AdminAuditLog(admin_id=admin.id, action="catalogs_updated", entity_type="platform_settings", details={"district_count": len(districts), "property_types": props}))
    await session.commit()
    return RedirectResponse("/admin/settings", status_code=303)


@router.post("/settings/admin/{admin_id}/role")
async def change_admin_role(admin_id: int, request: Request, role: str = Form(...), csrf: str = Form(...), session: AsyncSession = Depends(get_session)):
    if not hmac.compare_digest(request.cookies.get("uytop_csrf", ""), csrf): raise HTTPException(403, "Forma muddati tugagan.")
    actor = await _require_superadmin(request, session)
    target = await session.get(Admin, admin_id)
    if target is None: raise HTTPException(404, "Admin topilmadi.")
    if role not in {"superadmin", "moderator"}: raise HTTPException(422, "Admin roli noto‘g‘ri.")
    if target.id == actor.id and role != "superadmin": raise HTTPException(400, "O‘zingizning superadmin huquqingizni olib tashlay olmaysiz.")
    target.role = role
    session.add(AdminAuditLog(admin_id=actor.id, action="admin_role_changed", entity_type="admin", entity_id=str(target.id), details={"role": role}))
    await session.commit()
    return RedirectResponse("/admin/settings", status_code=303)

