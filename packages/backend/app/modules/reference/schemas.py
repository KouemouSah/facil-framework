"""Pydantic schemas for the reference module (create/update payloads)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _upper(v: str) -> str:
    return v.strip().upper()


class CurrencyIn(BaseModel):
    code: str = Field(min_length=3, max_length=3)
    name: str = Field(min_length=1, max_length=80)
    symbol: str | None = Field(default=None, max_length=8)
    decimal_places: int = Field(default=2, ge=0, le=4)
    name_i18n: dict = Field(default_factory=dict)

    _c = field_validator("code")(classmethod(lambda cls, v: _upper(v)))


class CurrencyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    symbol: str | None = Field(default=None, max_length=8)
    decimal_places: int | None = Field(default=None, ge=0, le=4)
    name_i18n: dict | None = None


class CountryIn(BaseModel):
    code: str = Field(min_length=2, max_length=2)
    alpha3: str | None = Field(default=None, max_length=3)
    numeric_code: str | None = Field(default=None, max_length=3)
    name: str = Field(min_length=1, max_length=120)
    phone_code: str | None = Field(default=None, max_length=8)
    default_currency_id: str | None = None
    name_i18n: dict = Field(default_factory=dict)

    _c = field_validator("code")(classmethod(lambda cls, v: _upper(v)))


class CountryUpdate(BaseModel):
    alpha3: str | None = Field(default=None, max_length=3)
    numeric_code: str | None = Field(default=None, max_length=3)
    name: str | None = Field(default=None, max_length=120)
    phone_code: str | None = Field(default=None, max_length=8)
    default_currency_id: str | None = None
    name_i18n: dict | None = None


class RegionIn(BaseModel):
    country_id: str
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    region_type: str | None = Field(default=None, max_length=40)
    name_i18n: dict = Field(default_factory=dict)


class RegionUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=10)
    name: str | None = Field(default=None, max_length=120)
    region_type: str | None = Field(default=None, max_length=40)
    name_i18n: dict | None = None
