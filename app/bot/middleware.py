"""Small per-process anti-flood guard for Telegram updates."""

import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.db import SessionFactory
from app.models import User
from app.bot.i18n import language_code, translate_text


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 8, window_seconds: int = 10) -> None:
        self.limit = limit
        self.window = window_seconds
        self.events: dict[int, deque[float]] = defaultdict(deque)
        self.block_cache: dict[int, tuple[float, bool]] = {}

    async def _is_blocked(self, telegram_id: int, now: float) -> bool:
        cached = self.block_cache.get(telegram_id)
        if cached and now - cached[0] < 30:
            return cached[1]
        async with SessionFactory() as session:
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            blocked = bool(user and user.status == "blocked")
        self.block_cache[telegram_id] = (now, blocked)
        return blocked

    async def __call__(self, handler, event, data):
        user = event.from_user if isinstance(event, (Message, CallbackQuery)) else None
        if user is None:
            return await handler(event, data)
        now = time.monotonic()
        if await self._is_blocked(user.id, now):
            if isinstance(event, Message):
                await event.answer("Hisobingiz moderator tomonidan vaqtincha bloklangan. Yordam uchun admin bilan bog‘laning.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Hisobingiz vaqtincha bloklangan.", show_alert=True)
            return None
        history = self.events[user.id]
        while history and now - history[0] > self.window:
            history.popleft()
        if len(history) >= self.limit:
            if isinstance(event, Message):
                await event.answer("Juda tez yuboryapsiz. Biroz kutib, qayta urinib ko‘ring.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Juda tez yuboryapsiz. Biroz kuting.", show_alert=True)
            return None
        history.append(now)
        return await handler(event, data)



class _LocalizedMessage:
    def __init__(self, message: Message, locale: str):
        self._message = message
        self.language_code = locale

    def __getattr__(self, name):
        return getattr(self._message, name)

    async def answer(self, text, *args, **kwargs):
        return await self._message.answer(translate_text(text, self.language_code), *args, **kwargs)

    async def answer_photo(self, photo, *args, **kwargs):
        if kwargs.get("caption") is not None:
            kwargs["caption"] = translate_text(kwargs["caption"], self.language_code)
        return await self._message.answer_photo(photo, *args, **kwargs)

    async def edit_text(self, text, *args, **kwargs):
        return await self._message.edit_text(translate_text(text, self.language_code), *args, **kwargs)


class _LocalizedCallback:
    def __init__(self, callback: CallbackQuery, locale: str):
        self._callback = callback
        self.language_code = locale

    def __getattr__(self, name):
        if name == "message" and self._callback.message is not None:
            return _LocalizedMessage(self._callback.message, self.language_code)
        return getattr(self._callback, name)

    async def answer(self, text=None, *args, **kwargs):
        translated = translate_text(text, self.language_code) if text is not None else None
        return await self._callback.answer(translated, *args, **kwargs)


class LanguageMiddleware(BaseMiddleware):
    """Load each Telegram user's saved locale and translate outgoing bot copy."""

    async def __call__(self, handler, event, data):
        tg_user = getattr(event, "from_user", None)
        if tg_user is None or not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        async with SessionFactory() as session:
            locale = await session.scalar(select(User.language_code).where(User.telegram_id == tg_user.id))
        locale = locale or language_code(getattr(tg_user, "language_code", None))
        data["language_code"] = locale
        localized = _LocalizedMessage(event, locale) if isinstance(event, Message) else _LocalizedCallback(event, locale)
        return await handler(localized, data)
