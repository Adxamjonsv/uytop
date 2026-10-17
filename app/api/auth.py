"""Mini App identity dependency; client-supplied user IDs are never trusted."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security import get_telegram_user


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    signed_user = await get_telegram_user(request)
    user = await session.scalar(select(User).where(User.telegram_id == signed_user["id"]))
    if user is None:
        name = " ".join(part for part in [signed_user.get("first_name"), signed_user.get("last_name")] if part).strip() or "Telegram foydalanuvchisi"
        user = User(telegram_id=signed_user["id"], username=signed_user.get("username"), full_name=name[:160])
        session.add(user)
        await session.commit()
        await session.refresh(user)
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Hisobingiz vaqtincha bloklangan.")
    return user

