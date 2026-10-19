"""Authentication helpers shared by the API and admin panel."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request, status

from app.config import Settings


def validate_telegram_init_data(init_data: str, settings: Settings) -> dict:
    """Validate Telegram WebApp initData and return its signed user payload."""
    if not init_data or len(init_data) > 16_384:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram tasdiqlash ma'lumoti topilmadi.")
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
        received_hash = fields.pop("hash")
        auth_date = int(fields["auth_date"])
        user = json.loads(fields["user"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App ma’lumoti to‘liq kelmadi. @Boshpanagobot’da /start yuboring va Mini App’ni bot tugmasidan qayta oching.",
        ) from None
    now = int(time.time())
    if auth_date > now + 30 or now - auth_date > settings.init_data_max_age_seconds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram sessiyasi eskirgan. Mini App'ni qayta oching.")
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", settings.bot_token.get_secret_value().encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram tasdiqlash imzosi mos kelmadi.")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram foydalanuvchisi ma'lumoti topilmadi.")
    return user


async def get_telegram_user(request: Request) -> dict:
    settings: Settings = request.app.state.settings
    init_data = request.headers.get("Authorization", "")
    if init_data.lower().startswith("tma "):
        init_data = init_data[4:]
    return validate_telegram_init_data(init_data, settings)

