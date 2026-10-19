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

BOT_RU = {
    "Qaysi tumanda uy qidiryapsiz?": "В каком районе ищете жильё?",
    "Toshkent tumanlari:": "Районы Ташкента:",
    "Uy turini tanlang:": "Выберите тип жилья:",
    "Barcha tumanlar": "Все районы",
    "Barcha turdagi uylar": "Любой тип жилья",
    "Hududlar ro‘yxati yangilangan. Qidiruvni qayta boshlang.": "Список районов обновился. Начните поиск заново.",
    "Bu hudud va tur bo‘yicha hozircha faol e’lon yo‘q.": "Пока нет активных объявлений по этому району и типу жилья.",
    "Bu e’lon endi mavjud emas.": "Это объявление больше недоступно.",
    "Bu e’lon topilmadi.": "Объявление не найдено.",
    "Uy egasi bilan bog‘lanish ma’lumoti mavjud emas.": "Контактные данные владельца отсутствуют.",
    "Uy egasi bilan bog‘lanish usulini tanlang:": "Выберите способ связи с владельцем:",
    "Uy egasining telefon raqami shaxsiy ma’lumot hisoblanadi. Ko‘rishni davom ettirasizmi?": "Номер телефона владельца является личными данными. Показать его?",
    "Uy egasi telefon raqamini ko‘rsatishga rozilik bermagan.": "Владелец не разрешил показывать номер телефона.",
    "Telefon raqamini ko‘rsatish": "Показать номер телефона",
    "Sizda hali e’lon yo‘q. «E’lon joylashtirish» tugmasidan boshlang.": "У вас пока нет объявлений. Нажмите «Разместить объявление».",
    "Sevimlilarga saqlangan faol e’lon yo‘q.": "В избранном пока нет активных объявлений.",
    "Kiritilgan ma’lumot formati noto‘g‘ri. Ko‘rsatilgan namuna bo‘yicha qayta yuboring.": "Неверный формат. Отправьте данные по указанному примеру.",
    "Rasmni surat ko‘rinishida yuboring yoki «Rasmlar tayyor» tugmasini bosing.": "Отправьте фотографию или нажмите «Фотографии готовы».",
    "Ko‘pi bilan 12 ta rasm yuborish mumkin.": "Можно отправить не более 12 фотографий.",
    "Qoralama saqlandi. Keyin «E’lon joylashtirish»ni bosing.": "Черновик сохранён. Позже нажмите «Разместить объявление».",
    "Qoralama topilmadi. /new orqali boshlang.": "Черновик не найден. Начните заново командой /new.",
    "Pastdagi «Rasmlar tayyor» tugmasini bosing.": "Нажмите кнопку «Фотографии готовы» ниже.",
    "Til tanlovi noto‘g‘ri.": "Неверный выбор языка.",
    "Avval /start buyrug‘ini yuboring.": "Сначала отправьте команду /start.",
    "Rasmlar tayyor": "Фотографии готовы",
    "⬅️ Orqaga": "⬅️ Назад",
    "Bekor qilish": "Отмена",
    "✅ Moderatsiyaga yuborish": "✅ Отправить на модерацию",
    "✅ Rasmlar tayyor": "✅ Фотографии готовы",
    "Uy turi va bitimni yuboring. Masalan: Kvartira | Uzoq muddatli ijara. Uy turi: kvartira, xonadon, uy yoki yotoqxona. Bitim: ijara, sotuv yoki kunlik.": "Укажите тип жилья и сделку. Например: Квартира | Долгосрочная аренда. Тип: квартира, дом или общежитие. Сделка: аренда, продажа или посуточно.",
    "Tuman, mahalla va ixtiyoriy manzilni | bilan ajrating. Masalan: Yunusobod | Minor | Amir Temur ko‘chasi. Aniq manzil ommaga ko‘rsatilmaydi.": "Укажите район, махаллю и адрес (необязательно), разделяя символом |. Например: Юнусабад | Минор | улица Амира Темура. Точный адрес публично не показывается.",
    "Narx, valyuta, xona, maydon (m²), qavatni | bilan yuboring. Masalan: 4500000 | UZS | 2 | 60 | 5. Qavat noma’lum bo‘lsa 0 yozing.": "Укажите цену, валюту, комнаты, площадь (м²) и этаж через |. Например: 4500000 | UZS | 2 | 60 | 5. Если этаж неизвестен, укажите 0.",
    "Sarlavha | tavsif | qulayliklar ko‘rinishida yuboring. Qulayliklar vergul bilan: mebel, konditsioner, Wi-Fi, faqat oilaga, hayvonlarga ruxsat.": "Отправьте заголовок | описание | удобства. Удобства укажите через запятую: мебель, кондиционер, Wi-Fi, только для семьи, можно с животными.",
    "E’lon rasmlarini bittalab yuboring. Birinchi rasm asosiy rasm bo‘ladi. Tugagach «Rasmlar tayyor» tugmasini bosing.": "Отправляйте фотографии объявления по одной. Первая будет главной. Когда закончите, нажмите «Фотографии готовы».",
    "Aloqa usulini yuboring: telegram, telefon yoki ikkalasi. Telefonni e’londa ko‘rsatishga rozilik bersangiz, raqam va «roziman» deb yozing. Masalan: telefon | +998901234567 | roziman. Faqat Telegram uchun: telegram.": "Укажите способ связи: telegram, телефон или оба. Чтобы показать телефон в объявлении, отправьте номер и слово «согласен». Например: телефон | +998901234567 | согласен. Только Telegram: telegram.",
    "E’lonni tekshirib, pastdagi tugma orqali moderatsiyaga yuboring.": "Проверьте объявление и отправьте его на модерацию кнопкой ниже.",
    "📋 E’lonni tekshiring": "📋 Проверьте объявление",
    "Menyudan kerakli bo‘limni tanlang.": "Выберите нужный раздел в меню.",
    "Mening e’lonlarim:": "Мои объявления:",
    "Sevimli e’lonlar:": "Избранные объявления:",
    "E’loningiz tasdiqlandi:": "Ваше объявление подтверждено:",
    "E’loningiz rad etildi. Sabab:": "Ваше объявление отклонено. Причина:",
    "E’loningiz tasdiqlandi va qidiruvda ko‘rinmoqda:": "Ваше объявление подтверждено и отображается в поиске:",
    "Rasm saqlandi": "Фото сохранено",
    "ta ko‘rsatildi": "показано",
    "xona ·": "комн. ·",
    "xona": "комнат",
    "Hudud:": "Район:",
    "Xonadon": "Жильё",
    "Uy": "Дом",
    "Kvartira": "Квартира",
    "Yotoqxona": "Общежитие",
}


def translate_text(value: str, language: str = "uz") -> str:
    if language != "ru" or not isinstance(value, str):
        return value
    result = value
    for uz, ru in sorted(BOT_RU.items(), key=lambda pair: len(pair[0]), reverse=True):
        result = result.replace(uz, ru)
    return result
