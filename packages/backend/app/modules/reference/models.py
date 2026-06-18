"""SQLAlchemy models for the reference module: Currency, Country, CountryRegion.

Managed master data (vs the old free-text fields on organization/site):
- Currency  — ISO 4217 (code, symbol, decimal places).
- Country   — ISO 3166-1 (alpha-2 code, alpha-3, numeric, phone code, default currency).
- CountryRegion — ISO 3166-2 subdivisions (states/provinces/regions), FK to Country.

Every label carries an optional `name_i18n` JSONB ({lang: value}) for data-level
i18n (F5); `name` is the default/fallback. UUID PK + `is_active` (archive flag)
come from UUIDAuditBase; the ISO `code` is the stable business key used by seeds
(idempotent upsert by code) and lookups.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase


class Currency(UUIDAuditBase):
    __tablename__ = "currency"

    # ISO 4217 alpha code (USD, EUR, XAF…). Business key.
    code: Mapped[str] = mapped_column(String(3), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_i18n: Mapped[dict] = mapped_column(JSONType, default=dict)
    symbol: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Minor-unit digits (2 for USD/EUR, 0 for JPY/XAF, 3 for some). Drives rounding.
    decimal_places: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "code": self.code, "name": self.name,
            "name_i18n": self.name_i18n or {}, "symbol": self.symbol,
            "decimal_places": self.decimal_places, "is_active": self.is_active,
        }


class Country(UUIDAuditBase):
    __tablename__ = "country"

    # ISO 3166-1 alpha-2 (GQ, FR, US…). Business key.
    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)
    alpha3: Mapped[str | None] = mapped_column(String(3), nullable=True)
    numeric_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    name_i18n: Mapped[dict] = mapped_column(JSONType, default=dict)
    phone_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Default settlement currency for the country (nullable; SET NULL on delete).
    default_currency_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("currency.id", ondelete="SET NULL"), nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "code": self.code, "alpha3": self.alpha3,
            "numeric_code": self.numeric_code, "name": self.name,
            "name_i18n": self.name_i18n or {}, "phone_code": self.phone_code,
            "default_currency_id": self.default_currency_id, "is_active": self.is_active,
        }


class CountryRegion(UUIDAuditBase):
    """ISO 3166-2 subdivision (state / province / region) of a Country."""

    __tablename__ = "country_region"
    __table_args__ = (
        UniqueConstraint("country_id", "code", name="uq_country_region_code"),
    )

    country_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("country.id", ondelete="CASCADE"), index=True)
    # Subdivision code (ISO 3166-2 suffix, e.g. "CA" within US, or full "US-CA").
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(120))
    name_i18n: Mapped[dict] = mapped_column(JSONType, default=dict)
    # Free/configurable subdivision kind (state / province / region / department).
    region_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "country_id": self.country_id, "code": self.code,
            "name": self.name, "name_i18n": self.name_i18n or {},
            "region_type": self.region_type, "is_active": self.is_active,
        }
