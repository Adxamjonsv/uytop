"""Environment-backed application settings."""

from functools import lru_cache
import re

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore", validate_default=True)

    bot_token: SecretStr = SecretStr("")
    database_url: str = ""
    webhook_base_url: str = ""
    webhook_secret: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")
    admin_username: str = "admin"
    admin_password: SecretStr = SecretStr("")
    admin_telegram_ids: str = ""
    mini_app_url: str = ""
    mode: str = "polling"
    log_level: str = "INFO"
    init_data_max_age_seconds: int = Field(default=86400, ge=60, le=604800)
    admin_session_max_age_seconds: int = Field(default=43200, ge=300, le=604800)
    rate_limit_requests: int = Field(default=60, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> str:
        url = str(value or "").strip()
        if not url:
            raise ValueError("DATABASE_URL kiritilmagan. Railway’da PostgreSQL service qo‘shib, uning DATABASE_URL qiymatini web service Variables’iga ulang.")
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL PostgreSQL uchun postgresql+asyncpg:// formatida bo‘lishi kerak")
        return url

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"polling", "webhook"}:
            raise ValueError("MODE faqat 'polling' yoki 'webhook' bo'lishi mumkin")
        return normalized

    @field_validator("webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if secret and not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
            raise ValueError("WEBHOOK_SECRET noto‘g‘ri. Buyruqni Railway’ga qo‘ymang: uni kompyuteringizda ishga tushirib, faqat hosil bo‘lgan qiymatni Railway Variables maydoniga kiriting (README’dagi ko‘rsatmaga qarang). Ruxsat etilgan belgilar: A-Z, a-z, 0-9, _ va -")
        return value

    @property
    def admin_telegram_id_list(self) -> list[int]:
        ids: list[int] = []
        for item in self.admin_telegram_ids.split(","):
            item = item.strip()
            if item:
                try:
                    ids.append(int(item))
                except ValueError as exc:
                    raise ValueError("ADMIN_TELEGRAM_IDS vergul bilan ajratilgan sonlar bo'lishi kerak") from exc
        return ids

    def validate_runtime_secrets(self) -> None:
        required = {"BOT_TOKEN": self.bot_token.get_secret_value(), "SECRET_KEY": self.secret_key.get_secret_value()}
        missing = [name for name, value in required.items() if not value]
        admin_password = self.admin_password.get_secret_value()
        if not admin_password:
            missing.append("ADMIN_PASSWORD")
        if missing:
            raise RuntimeError("Quyidagi environment qiymatlari sozlanmagan: " + ", ".join(missing))
        if len(self.secret_key.get_secret_value()) < 32 or "replace" in self.secret_key.get_secret_value().lower():
            raise RuntimeError("SECRET_KEY kamida 32 belgidan iborat bo'lishi kerak")
        if len(admin_password) < 12 or "replace" in admin_password.lower():
            raise RuntimeError("ADMIN_PASSWORD uchun kamida 12 belgili yangi parol kiriting")
        if self.mode == "webhook":
            if not self.webhook_base_url.startswith("https://"):
                raise RuntimeError("Webhook rejimida WEBHOOK_BASE_URL HTTPS manzil bo'lishi kerak")
            if len(self.webhook_secret.get_secret_value()) < 16 or "replace" in self.webhook_secret.get_secret_value().lower():
                raise RuntimeError("Webhook rejimida WEBHOOK_SECRET kamida 16 belgidan iborat bo'lishi kerak")
        if not self.admin_username.strip():
            raise RuntimeError("ADMIN_USERNAME bo‘sh bo‘lishi mumkin emas")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
