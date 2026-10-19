# UyTop

UyTop Toshkentda uy egasi va ijarachini maklersiz bog‘laydigan Telegram bot, Telegram Mini App va admin panelidir. FastAPI, aiogram 3, SQLAlchemy 2 async va PostgreSQL ishlatiladi. Rasmlar Telegram `file_id` orqali olinadi; ilova serverining vaqtinchalik diskiga saqlanmaydi.

## Loyihani ishga tushirish

Kerak bo‘ladi: Python 3.11 yoki yangiroq, ishlaydigan PostgreSQL va Telegram BotFather’dan olingan bot tokeni.

PowerShell’da loyiha papkasiga kiring va buyruqlarni ketma-ket bajaring:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` faylida quyidagilarni kiriting:

- `BOT_TOKEN`: BotFather bergan token.
- `DATABASE_URL`: PostgreSQL ulanish manzili. Masalan `postgresql+asyncpg://uytop:parol@localhost:5432/uytop`.
- `SECRET_KEY`: kamida 32 belgili maxfiy qiymat. PowerShell’da `python -c "import secrets; print(secrets.token_hex(32))"` orqali yarating.
- `ADMIN_USERNAME` va `ADMIN_PASSWORD`: birinchi admin uchun login va kamida 12 belgili kuchli parol.
- `ADMIN_TELEGRAM_IDS`: bot moderatsiya xabarlari oladigan Telegram raqamli ID’lari, vergul bilan ajratiladi. Botdan admin panelga kirish uchun o‘z Telegram ID’ingizni kiriting.
- `SUPPORT_USERNAME`: mijozlar yordam so‘rashi uchun Telegram username, masalan `YordamchiIsmi`; `@UyTopSupport` kodda qattiq yozilmagan.
- Lokal rejim uchun `MODE=polling`; `WEBHOOK_BASE_URL` va `MINI_APP_URL` lokal HTTP’da bo‘sh qolishi mumkin.

`DATABASE_URL` dan `postgresql://` yoki Railway `postgres://` berilsa ham sozlama uni `postgresql+asyncpg://` ga o‘giradi.

PostgreSQL’da `uytop` bazasini yarating. So‘ng:

```powershell
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Brauzerda `http://127.0.0.1:8000/health` ni oching. Mini App Telegram ichidan ochilganda `initData` talab qiladi; oddiy brauzerda haqiqiy foydalanuvchi ma’lumotlari so‘ralmaydi. Admin panel `http://127.0.0.1:8000/admin/login` manzilida.

Bot menyusi `/start`, `/search`, `/new`, `/myads`, `/help` va `/language` buyruqlari bilan ishlaydi. O‘zbekcha va ruscha tanlov saqlanadi. `ADMIN_TELEGRAM_IDS` dagi administratorlar bot menyusidan admin panelni ochishi mumkin. E’lon moderator tasdiqlamaguncha ommaviy qidiruvda ko‘rinmaydi.

## BotFather sozlamasi

1. BotFather’da bot yarating va tokenni xavfsiz joyda saqlang.
2. Railway domeni tayyor bo‘lgach, BotFather’dagi `/setdomain` orqali domenni ulang.
3. BotFather’da Mini App yoki bot menyusidagi Web App tugmasini `https://SIZNING-DOMEN/` manziliga sozlang. Bot `/start` menyusida `MINI_APP_URL` to‘ldirilganida Mini App tugmasini chiqaradi.
4. Botni shaxsiy chatda bir marta `/start` qiling. Mini App’dan rasm yuborish Telegram orqali `file_id` oladi.

Moderator o‘zining raqamli ID’sini botga `/id` yuborib ko‘radi; kerakli ID’larni `ADMIN_TELEGRAM_IDS` ga vergul bilan kiriting va xizmatni qayta ishga tushiring.

Mini App har bir API so‘rovida Telegram `initData` yuboradi. Server HMAC imzosini va `auth_date` yoshini tekshiradi; klient yuborgan alohida user ID’ga ishonmaydi.

## GitHub’ga private repository qilib joylash

`.env` `.gitignore` ichida; uni, bot tokenini yoki haqiqiy parollarni repository’ga qo‘shmang.

1. GitHub’da yangi **Private** repository yarating.
2. Shu papkani GitHub Desktop bilan oching yoki terminalda:

```powershell
git init
git add .
git status
git commit -m "UyTop MVP"
git branch -M main
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

`git status` natijasida `.env` staged fayllar ichida yo‘qligini tekshiring. `git remote` manzilidagi USERNAME va REPOSITORY’ni o‘zingiznikiga almashtiring.

## Railway’ga deploy

1. Railway’da yangi project oching, GitHub’dagi private repository’ni ulang va PostgreSQL service qo‘shing. PostgreSQL va bot web service bir project ichida bo‘lsin.
2. Web service Variables bo‘limida quyidagilarni kiriting. Maxfiy qiymatlarni faqat Railway Variables’da saqlang:

| Variable | Qiymat |
|---|---|
| `BOT_TOKEN` | BotFather tokeni |
| `DATABASE_URL` | Variables oynasida PostgreSQL service’dan reference qilingan `DATABASE_URL`; `localhost` manzilini qo‘ymang |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` chiqargan qiymat |
| `ADMIN_USERNAME` | Panel uchun login |
| `ADMIN_PASSWORD` | Kuchli, kamida 12 belgili parol |
| `ADMIN_TELEGRAM_IDS` | Moderator Telegram ID’lari, masalan `123456789,987654321`; bot ichida admin panelni ochish huquqi ham beradi |
| `SUPPORT_USERNAME` | Siz tanlagan yordamchi username, masalan `YordamchiIsmi` ( `@` belgisisiz yoki bilan) |
| `MODE` | `webhook` |
| `WEBHOOK_BASE_URL` | Railway yaratgan `https://...` domeni |
| `WEBHOOK_SECRET` | Kompyuteringizda buyruq chiqargan tasodifiy qiymatning o‘zi (buyruq matni emas) |
| `MINI_APP_URL` | `WEBHOOK_BASE_URL` bilan bir xil, oxiri `/` bilan |

> **WEBHOOK_SECRET yaratish:** Windows PowerShell’ni kompyuteringizda ochib `python -c "import secrets; print(secrets.token_urlsafe(32))"` buyrug‘ini bajaring. Chiqadigan tasodifiy matnni nusxalab Railway’dagi `WEBHOOK_SECRET` qiymatiga qo‘ying. Railway maydoniga `python -c ...` buyrug‘ining o‘zini kiritmang; qo‘shtirnoqlarni ham qo‘shmang. `python` topilmasa, `py -c "import secrets; print(secrets.token_urlsafe(32))"` dan foydalaning.\n\n3. Railway domeni yaratilganidan keyin shu HTTPS domenni `WEBHOOK_BASE_URL` va `MINI_APP_URL` ga kiriting; BotFather Mini App’ida ham shu manzilni belgilang.
4. `railway.toml` deploy paytida `alembic upgrade head` bajarib, so‘ng Uvicorn’ni Railway `PORT` qiymatida ochadi. Health check `/health` manzilini tekshiradi.
5. Birinchi deploy `ADMIN_USERNAME` va `ADMIN_PASSWORD` asosida superadmin yozuvini yaratadi. Keyingi deploylar parolni qayta yozmaydi. Kirish manzili: `https://SIZNING-DOMEN/admin/login`.

Railway Postgres ma’lumotlarini va Telegram rasmlarini doimiy xizmatda saqlaydi. Ilova ko‘p nusxaga scale qilinsa, botni polling rejimida qoldirmang: loyiha webhook rejimini mo‘ljallaydi va per-process anti-flood sanagichi har bir instance’da alohida ishlaydi. PostgreSQL uchun muntazam backup sozlang.

## Ma’lumotlar bazasi va migratsiyalar

Jadvallar `users`, `admins`, `listings`, `listing_photos`, `listing_drafts`, `favorites`, `listing_views`, `inquiries`, `saved_searches`, `reports`, `moderation_logs`, `admin_audit_logs`, `notifications` va `platform_settings` ni o‘z ichiga oladi. Sxema o‘zgarishi uchun yangi Alembic revision yarating va faqat oldinga qarab migratsiya yozing. Loyihada `create_all()` ishlatilmaydi; `downgrade` ataylab bloklangan, chunki production jadvallarini o‘chirish xavfli.

Migratsiya holatini ko‘rish:

```powershell
alembic current
alembic history
```

## Tekshiruv ro‘yxati

- `/health` `{"status":"ok"}` qaytaradi.
- `/start` asosiy bot menyusini ko‘rsatadi.
- `/new` qoralama yaratadi; bot qayta ochilganda qoralama davom etadi.
- Yangi e’lon moderatorga yuboriladi; tasdiqlanmaguncha `/search` va Mini App natijalarida ko‘rinmaydi.
- Mini App `initData` tekshiruvisiz API so‘rovlarini rad qiladi.
- E’lon egasi bo‘lmagan foydalanuvchi e’lonni tahrirlay olmaydi.
- Admin panel login, CSRF cookie, rol nazorati va audit yozuvlari bilan ishlaydi.
- Deploydan keyin Railway Logs’da migration va `UyTop ishga tushdi` yozuvlarini tekshiring.

