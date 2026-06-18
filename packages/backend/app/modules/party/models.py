"""SQLAlchemy models for the party module: Party, PartyRole, Address, PartyAddress.

Canonical directory model (Odoo res.partner / SAP Business Partner):
- Party        — a person or an organization (name, legal identifiers, contact).
- PartyRole    — the business natures a party plays (customer/vendor/employee/…).
- Address      — a reusable postal address; geography references the reference
                 module (country / country_region), so it is FK-integral, not free text.
- PartyAddress — links a party to its addresses (billing/shipping/…), with a primary.

UUID PK + is_active (archive) + audit come from UUIDAuditBase. Addresses are first
class so a Company (organization.hq_address_id) and a Site (site.address_id) reuse
the same shape — no geography duplicated across tables.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase

PARTY_TYPES = ("person", "organization")


class Party(UUIDAuditBase):
    __tablename__ = "party"

    party_type: Mapped[str] = mapped_column(String(20), default="organization")
    # Display / legal name (for a person: full name; for an org: legal name).
    name: Mapped[str] = mapped_column(String(255))
    # Legal identifiers (live here, NOT on organization — the Company references it).
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Extensibility hook (F.6) — custom fields without schema change.
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "party_type": self.party_type, "name": self.name,
            "tax_id": self.tax_id, "registration_number": self.registration_number,
            "email": self.email, "phone": self.phone, "website": self.website,
            "custom_fields": self.custom_fields or {}, "is_active": self.is_active,
        }


class PartyRole(UUIDAuditBase):
    """A business nature a party plays (customer / vendor / employee / contact …).
    Free/configurable role code (not a locked enum) — a party can hold several."""

    __tablename__ = "party_role"
    __table_args__ = (
        UniqueConstraint("party_id", "role", name="uq_party_role"),
    )

    party_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("party.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(40))

    def as_dict(self) -> dict:
        return {"id": self.id, "party_id": self.party_id, "role": self.role,
                "is_active": self.is_active}


class Address(UUIDAuditBase):
    """A reusable postal address. Geography is FK-integral to the reference module
    (country / country_region); city stays validated text (cities are not ISO data)."""

    __tablename__ = "address"

    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    line1: Mapped[str | None] = mapped_column(Text, nullable=True)
    line2: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("country.id", ondelete="SET NULL"), nullable=True, index=True)
    country_region_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("country_region.id", ondelete="SET NULL"), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "line1": self.line1, "line2": self.line2,
            "city": self.city, "postal_code": self.postal_code,
            "country_id": self.country_id, "country_region_id": self.country_region_id,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "is_active": self.is_active,
        }


class PartyAddress(UUIDAuditBase):
    """Links a party to a reusable address (billing / shipping / …)."""

    __tablename__ = "party_address"
    __table_args__ = (
        UniqueConstraint("party_id", "address_id", "address_type",
                         name="uq_party_address"),
    )

    party_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("party.id", ondelete="CASCADE"), index=True)
    address_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("address.id", ondelete="CASCADE"), index=True)
    address_type: Mapped[str] = mapped_column(String(30), default="main")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def as_dict(self) -> dict:
        return {"id": self.id, "party_id": self.party_id, "address_id": self.address_id,
                "address_type": self.address_type, "is_primary": self.is_primary,
                "is_active": self.is_active}
