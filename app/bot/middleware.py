"""Small per-process anti-flood guard for Telegram updates."""

import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.db import SessionFactory
from app.models import User


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

