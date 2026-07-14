"""SQLAlchemy models for the organization module: Organization + OrgUnit.

Generalises the legacy `entities` table, de-hardcoded of gov specifics
(ministry_id -> external_ref; entity_type=treasury -> free unit_type; no
workflow_codes here). Hierarchy via self-FK parent_id + materialized `path`.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase


class Organization(UUIDAuditBase):
    __tablename__ = "organization"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_line2: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(80), nullable=True)

    default_locale: Mapped[str | None] = mapped_column(String(5), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # Letterhead/footer/seal config consumed by the Document Designer (Phase N).
    document_identity: Mapped[dict] = mapped_column(JSONType, default=dict)
    settings: Mapped[dict] = mapped_column(JSONType, default=dict)

    # ERP Company links (F.3): parent for multi-company consolidation; party_id =
    # the legal identity in the directory (legal_name/tax_id/address migrate there);
    # hq_address + currency reference the master data. The text geo/currency columns
    # above are kept during the transition and backfilled into party/address.
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=True, index=True)
    party_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("party.id", ondelete="SET NULL"), nullable=True)
    hq_address_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("address.id", ondelete="SET NULL"), nullable=True)
    currency_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("currency.id", ondelete="SET NULL"), nullable=True)

    # User-defined fields (SP1). Kept SEPARATE from `settings`/document_identity,
    # which are UNCONTROLLED extension bags: mixing schema'd fields into them
    # would destroy the allowlist guarantee (an undeclared key could no longer
    # be rejected). Definitions live in `field_definition`; only VALUES here.
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "code": self.code, "legal_name": self.legal_name,
            "display_name": self.display_name, "logo_url": self.logo_url,
            "email": self.email, "phone": self.phone, "website": self.website,
            "address_line1": self.address_line1, "address_line2": self.address_line2,
            "city": self.city, "region": self.region,
            "country_code": self.country_code, "postal_code": self.postal_code,
            "tax_id": self.tax_id, "registration_number": self.registration_number,
            "default_locale": self.default_locale, "timezone": self.timezone,
            "currency": self.currency, "document_identity": self.document_identity or {},
            "settings": self.settings or {},
            "parent_id": self.parent_id, "party_id": self.party_id,
            "hq_address_id": self.hq_address_id, "currency_id": self.currency_id,
            "custom_fields": self.custom_fields or {},
            "is_active": self.is_active,
        }


class OrgUnit(UUIDAuditBase):
    __tablename__ = "org_unit"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_org_unit_org_code"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("org_unit.id"), nullable=True)

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    # Free/configurable (division/department/unit/agency) — NOT a locked enum.
    unit_type: Mapped[str] = mapped_column(String(40), default="department")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Materialized path ("/uuid/uuid/…") + depth for fast subtree queries.
    path: Mapped[str] = mapped_column(String(1024), default="", index=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)

    # Generic external linkage (replaces gov-specific ministry_id).
    external_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONType, default=dict)

    # User-defined fields (SP1). Kept SEPARATE from `meta`/`metadata`, which is an
    # UNCONTROLLED extension bag: mixing schema'd fields into it would destroy the
    # allowlist guarantee (an undeclared key could no longer be rejected).
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "organization_id": self.organization_id,
            "parent_id": self.parent_id, "code": self.code, "name": self.name,
            "unit_type": self.unit_type, "description": self.description,
            "path": self.path, "depth": self.depth,
            "external_ref": self.external_ref, "metadata": self.meta or {},
            "custom_fields": self.custom_fields or {},
            "is_active": self.is_active,
        }
