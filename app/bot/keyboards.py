"""Telegram bot keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.config import Settings

DISTRICTS = ["Yunusobod", "Chilonzor", "Mirobod", "Shayxontohur", "Yakkasaroy", "Mirzo Ulug‘bek", "Sergeli", "Olmazor", "Uchtepa", "Yashnobod", "Bektemir", "Yangihayot"]
PROPERTY_TYPES = [("Kvartira", "apartment"), ("Xonadon", "household"), ("Uy", "house"), ("Yotoqxona", "dormitory")]


def main_menu(settings: Settings) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🔎 Uy qidirish"), KeyboardButton(text="➕ E’lon joylashtirish")],
        [KeyboardButton(text="📍 Hududlar"), KeyboardButton(text="💚 Sevimlilar")],
        [KeyboardButton(text="👤 Profil"), KeyboardButton(text="❔ Yordam")],
    ]
    if settings.mini_app_url.startswith("https://"):
        rows.append([KeyboardButton(text="📱 Mini App’ni ochish", web_app=WebAppInfo(url=settings.mini_app_url))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Kerakli bo‘limni tanlang")


def district_keyboard(prefix: str = "district", districts: list[str] | None = None) -> InlineKeyboardMarkup:
    names = districts or DISTRICTS
    buttons = [InlineKeyboardButton(text=name, callback_data=f"{prefix}:{index}") for index, name in enumerate(names)]
    rows = [buttons[index:index + 3] for index in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text="Barcha tumanlar", callback_data=f"{prefix}:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def property_keyboard(prefix: str = "ptype", options: list[dict[str, str]] | None = None) -> InlineKeyboardMarkup:
    values = [(item["label"], item["code"]) for item in options] if options else PROPERTY_TYPES
    rows = [[InlineKeyboardButton(text=label, callback_data=f"{prefix}:{value}")] for label, value in values]
    rows.insert(0, [InlineKeyboardButton(text="Barcha turdagi uylar", callback_data=f"{prefix}:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def draft_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="draft:back"), InlineKeyboardButton(text="Bekor qilish", callback_data="draft:cancel")],
    ])


def photos_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Rasmlar tayyor", callback_data="draft:photos_done")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="draft:back"), InlineKeyboardButton(text="Bekor qilish", callback_data="draft:cancel")],
    ])

