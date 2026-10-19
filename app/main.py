"""FastAPI application, webhook/polling lifecycle, and health endpoint."""

import asyncio
import hmac
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pwdlib import PasswordHash
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware

from app.admin.routes import router as admin_router
from app.api.routes import router as api_router
from app.bot.handlers import router as bot_router
from app.bot.middleware import AntiFloodMiddleware, LanguageMiddleware
from app.config import Settings, get_settings
from app.db import SessionFactory, engine
from app.models import Admin, PlatformSetting
from app.bot.keyboards import DISTRICTS, PROPERTY_TYPES

BASE_DIR = Path(__file__).resolve().parent.parent
logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("uytop")


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-process request throttle for public/API endpoints."""

    def __init__(self, app, limit: int, window: int):
        super().__init__(app)
        self.limit, self.window = limit, window
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health" or request.url.path.startswith("/static/"):
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        history = self.requests[client]
        while history and now - history[0] > self.window:
            history.popleft()
        if len(history) >= self.limit:
            return JSONResponse(status_code=429, content={"detail": "So‘rovlar juda tez yuborildi. Birozdan keyin urinib ko‘ring."}, headers={"Retry-After": str(self.window)})
        history.append(now)
        return await call_next(request)


async def _bootstrap_admins(settings: Settings) -> None:
    """Create initial panel and Telegram moderators without replacing existing accounts."""
    hasher = PasswordHash.recommended()
    async with SessionFactory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == settings.admin_username))
        if admin is None:
            password = settings.admin_password.get_secret_value()
            if len(password) < 12:
                raise RuntimeError("ADMIN_PASSWORD kamida 12 belgidan iborat bo‘lishi kerak")
            session.add(Admin(username=settings.admin_username, password_hash=hasher.hash(password), role="superadmin", is_active=True))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
        superadmin_ids = set(settings.superadmin_telegram_id_list)
        for telegram_id in settings.admin_telegram_id_list:
            exists = await session.scalar(select(Admin).where(Admin.telegram_id == telegram_id))
            if exists is None:
                session.add(Admin(username=f"telegram_{telegram_id}", telegram_id=telegram_id, password_hash=hasher.hash(f"disabled-{telegram_id}-{settings.secret_key.get_secret_value()}"), role="superadmin" if telegram_id in superadmin_ids else "moderator", is_active=True))
            elif telegram_id in superadmin_ids and exists.role != "superadmin":
                exists.role = "superadmin"
        for key, value in (("districts", DISTRICTS), ("property_types", [{"code": code, "label": label} for label, code in PROPERTY_TYPES])):
            setting = await session.get(PlatformSetting, key)
            if setting is None:
                session.add(PlatformSetting(key=key, value=value))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_runtime_secrets()
    await _bootstrap_admins(settings)
    bot = Bot(token=settings.bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher.include_router(bot_router)
    dispatcher.message.outer_middleware(AntiFloodMiddleware())
    dispatcher.callback_query.outer_middleware(AntiFloodMiddleware())
    dispatcher.message.outer_middleware(LanguageMiddleware())
    dispatcher.callback_query.outer_middleware(LanguageMiddleware())
    app.state.settings, app.state.bot, app.state.dispatcher = settings, bot, dispatcher
    polling_task = None
    try:
        if settings.mode == "webhook":
            await bot.set_webhook(f"{settings.webhook_base_url.rstrip('/')}/telegram/webhook", secret_token=settings.webhook_secret.get_secret_value(), drop_pending_updates=False, allowed_updates=dispatcher.resolve_used_update_types())
        else:
            await bot.delete_webhook(drop_pending_updates=False)
            polling_task = asyncio.create_task(dispatcher.start_polling(bot, handle_signals=False, allowed_updates=dispatcher.resolve_used_update_types(), settings=settings))
        logger.info("UyTop ishga tushdi; MODE=%s", settings.mode)
        yield
    finally:
        if polling_task:
            try:
                await dispatcher.stop_polling()
            except RuntimeError:
                logger.info("Polling shutdown oldindan boshlangan")
            try:
                await asyncio.wait_for(polling_task, timeout=10)
            except asyncio.TimeoutError:
                polling_task.cancel()
                await asyncio.gather(polling_task, return_exceptions=True)
            except Exception as exc:
                logger.error("Polling yopilishida xato (%s)", type(exc).__name__)
        await bot.session.close()
        await engine.dispose()


settings = get_settings()
app = FastAPI(title="UyTop API", version="1.0.0", lifespan=lifespan)
app.add_middleware(ApiRateLimitMiddleware, limit=settings.rate_limit_requests, window=settings.rate_limit_window_seconds)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.include_router(api_router)
app.include_router(admin_router)


@app.get("/", include_in_schema=False)
async def mini_app_index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
async def health():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.error("Health check: ma’lumotlar bazasiga ulanish xatosi")
        raise HTTPException(status_code=503, detail="Ma’lumotlar bazasi hozircha ishlamayapti.") from None
    return {"status": "ok", "service": "uytop"}


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    settings: Settings = request.app.state.settings
    expected = settings.webhook_secret.get_secret_value()
    if settings.mode != "webhook" or not x_telegram_bot_api_secret_token or not hmac.compare_digest(expected, x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=403, detail="Webhook so‘rovi rad etildi.")
    body = await request.body()
    if len(body) > 1_048_576:
        raise HTTPException(status_code=413, detail="Webhook so‘rovi juda katta.")
    try:
        update = Update.model_validate_json(body, context={"bot": request.app.state.bot})
        await request.app.state.dispatcher.feed_update(request.app.state.bot, update, settings=settings)
    except Exception as exc:
        logger.error("Telegram update qayta ishlanmadi (%s)", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Telegram yangilanishini qayta ishlashda xato.") from None
    return {"ok": True}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Kiritilgan ma’lumotlarni tekshiring.", "errors": [{"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]} for error in exc.errors()]})


