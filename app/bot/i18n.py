"""Small, explicit Uzbek/Russian interface strings for the Telegram bot."""

TEXT = {
    "uz": {
        "menu_search": "🔎 Uy qidirish",
        "menu_add": "➕ E’lon joylashtirish",
        "menu_districts": "📍 Hududlar",
        "menu_favorites": "💚 Sevimlilar",
        "menu_profile": "👤 Profil",
        "menu_help": "❔ Yordam",
        "menu_language": "🌐 Til / Язык",
        "menu_miniapp": "📱 Mini App’ni ochish",
        "menu_admin": "🛡 Admin panel",
        "placeholder": "Kerakli bo‘limni tanlang",
        "welcome": "Assalomu alaykum! UyTop — maklersiz kvartira ijarasi platformasi.\n\nUy qidiring yoki e’loningizni joylashtiring.",
        "language_prompt": "Tilni tanlang / Выберите язык:",
        "language_saved": "Til o‘zbekchaga o‘zgartirildi.",
        "help": "UyTop’da uy egasi e’lonini moderator tasdiqlaganidan keyin ko‘rasiz. Shubhali e’lonni shikoyat qiling.",
        "support_button": "✉️ Yordam uchun yozish",
        "admin_only": "Bu bo‘lim faqat administratorlar uchun.",
        "admin_button": "🛡 Admin panelni ochish",
        "admin_unconfigured": "Admin panel havolasi sozlanmagan.",
    },
    "ru": {
        "menu_search": "🔎 Найти жильё",
        "menu_add": "➕ Разместить объявление",
        "menu_districts": "📍 Районы",
        "menu_favorites": "💚 Избранное",
        "menu_profile": "👤 Профиль",
        "menu_help": "❔ Помощь",
        "menu_language": "🌐 Til / Язык",
        "menu_miniapp": "📱 Открыть Mini App",
        "menu_admin": "🛡 Панель администратора",
        "placeholder": "Выберите нужный раздел",
        "welcome": "Здравствуйте! UyTop — платформа аренды жилья без посредников.\n\nНайдите жильё или разместите объявление.",
        "language_prompt": "Tilni tanlang / Выберите язык:",
        "language_saved": "Язык изменён на русский.",
        "help": "Объявления владельцев публикуются после проверки модератором. О подозрительных объявлениях можно сообщить.",
        "support_button": "✉️ Написать в поддержку",
        "admin_only": "Этот раздел доступен только администраторам.",
        "admin_button": "🛡 Открыть панель администратора",
        "admin_unconfigured": "Ссылка на панель администратора не настроена.",
    },
}


def tr(key: str, language: str = "uz") -> str:
    locale = "ru" if language == "ru" else "uz"
    return TEXT[locale].get(key, TEXT["uz"].get(key, key))


def language_code(value: str | None) -> str:
    return "ru" if (value or "").lower().startswith("ru") else "uz"
