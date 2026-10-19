"""Telegram bot keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.config import Settings
from app.bot.i18n import tr, translate_text

DISTRICTS = ["Yunusobod", "Chilonzor", "Mirobod", "Shayxontohur", "Yakkasaroy", "Mirzo Ulug‘bek", "Sergeli", "Olmazor", "Uchtepa", "Yashnobod", "Bektemir", "Yangihayot"]
PROPERTY_TYPES = [("Kvartira", "apartment"), ("Xonadon", "household"), ("Uy", "house"), ("Yotoqxona", "dormitory")]


def main_menu(settings: Settings, language: str = "uz", is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=tr("menu_search", language)), KeyboardButton(text=tr("menu_add", language))],
        [KeyboardButton(text=tr("menu_districts", language)), KeyboardButton(text=tr("menu_favorites", language))],
        [KeyboardButton(text=tr("menu_profile", language)), KeyboardButton(text=tr("menu_help", language))],
        [KeyboardButton(text=tr("menu_language", language))],
    ]
    if settings.mini_app_url.startswith("https://"):
        rows.append([KeyboardButton(text=tr("menu_miniapp", language), web_app=WebAppInfo(url=settings.mini_app_url))])
        if is_admin:
            admin_url = settings.mini_app_url.rstrip("/") + "/admin/telegram-login"
            rows.append([KeyboardButton(text=tr("menu_admin", language), web_app=WebAppInfo(url=admin_url))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder=tr("placeholder", language))


def language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="language:uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="language:ru"),
    ]])


def district_keyboard(prefix: str = "district", districts: list[str] | None = None, language: str = "uz") -> InlineKeyboardMarkup:
    names = districts or DISTRICTS
    buttons = [InlineKeyboardButton(text=translate_text(name, language), callback_data=f"{prefix}:{index}") for index, name in enumerate(names)]
    rows = [buttons[index:index + 3] for index in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text=translate_text("Barcha tumanlar", language), callback_data=f"{prefix}:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def property_keyboard(prefix: str = "ptype", options: list[dict[str, str]] | None = None) -> InlineKeyboardMarkup:
    values = [(item["label"], item["code"]) for item in options] if options else PROPERTY_TYPES
    rows = [[InlineKeyboardButton(text=label, callback_data=f"{prefix}:{value}")] for label, value in values]
    rows.insert(0, [InlineKeyboardButton(text="Barcha turdagi uylar", callback_data=f"{prefix}:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def draft_keyboard(language: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate_text("⬅️ Orqaga", language), callback_data="draft:back"), InlineKeyboardButton(text=translate_text("Bekor qilish", language), callback_data="draft:cancel")],
    ])


def photos_keyboard(language: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate_text("✅ Rasmlar tayyor", language), callback_data="draft:photos_done")],
        [InlineKeyboardButton(text=translate_text("⬅️ Orqaga", language), callback_data="draft:back"), InlineKeyboardButton(text=translate_text("Bekor qilish", language), callback_data="draft:cancel")],
    ])

