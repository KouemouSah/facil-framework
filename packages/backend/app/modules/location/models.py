"""SQLAlchemy model for the location module: Site.

Generalises the legacy `entity_locations` (entity_code/city/region/... ) into a
generic site/branch belonging to an Organization (+ optional OrgUnit), with a
self-FK for branch hierarchy. Geo as ISO country_code + free region/city + lat/lng.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase


class Site(UUIDAuditBase):
    __tablename__ = "site"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_site_org_code"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    org_unit_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("org_unit.id"), nullable=True, index=True)
    parent_site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("site.id"), nullable=True, index=True)

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    # headquarters / branch / office / counter / warehouse — free/configurable.
    site_type: Mapped[str] = mapped_column(String(40), default="branch")

    # ERP-grade F.3c: structured reusable address (party module). Supersedes the
    # flat geo text columns below, which are kept non-destructively during the
    # transition (backfilled into address by a later data migration).
    address_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("address.id", ondelete="SET NULL"), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_line2: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    operating_hours: Mapped[dict] = mapped_column(JSONType, default=dict)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Generalises the legacy is_main_office.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONType, default=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "organization_id": self.organization_id,
            "org_unit_id": self.org_unit_id, "parent_site_id": self.parent_site_id,
            "code": self.code, "name": self.name, "site_type": self.site_type,
            "address_id": self.address_id,
            "address_line1": self.address_line1, "address_line2": self.address_line2,
            "city": self.city, "region": self.region,
            "country_code": self.country_code, "postal_code": self.postal_code,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "phone": self.phone, "email": self.email,
            "operating_hours": self.operating_hours or {}, "timezone": self.timezone,
            "is_primary": self.is_primary, "notes": self.notes,
            "metadata": self.meta or {}, "is_active": self.is_active,
        }
