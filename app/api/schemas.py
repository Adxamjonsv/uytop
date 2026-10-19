"""Validated request and response models for the Mini App API."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ListingCreate(BaseModel):
    title: str = Field(min_length=5, max_length=180)
    deal_type: Literal["rent", "sale", "daily"]
    property_type: Literal["apartment", "household", "house", "dormitory"]
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Literal["UZS", "USD"] = "UZS"
    district: str = Field(min_length=2, max_length=80)
    neighborhood: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=240)
    rooms: int | None = Field(default=None, ge=0, le=100)
    area_m2: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    floor: int | None = Field(default=None, ge=0, le=200)
    total_floors: int | None = Field(default=None, ge=0, le=200)
    description: str = Field(min_length=10, max_length=5000)
    amenities: list[str] = Field(default_factory=list, max_length=20)
    photo_file_ids: list[str] = Field(default_factory=list, max_length=12)
    contact_method: Literal["telegram", "phone", "both"] = "telegram"
    phone_consent: bool = False
    contact_phone: str | None = Field(default=None, max_length=32)

    @field_validator("amenities")
    @classmethod
    def clean_amenities(cls, values: list[str]) -> list[str]:
        return [value.strip()[:40] for value in values if value.strip()]

    @field_validator("contact_phone")
    @classmethod
    def phone_needs_consent(cls, value: str | None, info):
        if value and not info.data.get("phone_consent", False):
            raise ValueError("Telefon raqamini saqlash uchun egasining roziligi kerak")
        return value

    @model_validator(mode="after")
    def validate_contact(self):
        if self.contact_method in {"phone", "both"} and not self.contact_phone:
            raise ValueError("Telefon orqali aloqa tanlansa, telefon raqamini kiriting")
        if self.contact_phone:
            digits = "".join(char for char in self.contact_phone if char.isdigit())
            if len(digits) < 9 or len(digits) > 15:
                raise ValueError("Telefon raqamini xalqaro formatda kiriting")
        return self


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=180)
    price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    amenities: list[str] | None = Field(default=None, max_length=20)
    contact_phone: str | None = Field(default=None, max_length=32)
    phone_consent: bool | None = None


class ReportCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=80)
    details: str | None = Field(default=None, max_length=2000)


class DraftUpdate(BaseModel):
    current_step: int = Field(ge=1, le=7)
    data: dict[str, Any] = Field(default_factory=dict)


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    filters: dict[str, Any] = Field(default_factory=dict)


class NotificationSettingsUpdate(BaseModel):
    notifications_enabled: bool


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    deal_type: str
    property_type: str
    status: str
    price: Decimal
    currency: str
    district: str
    neighborhood: str | None
    rooms: int | None
    area_m2: Decimal | None
    floor: int | None
    description: str
    amenities: list[str]
    created_at: Any
    photos: list[str] = []
    channel_url: str | None = None

