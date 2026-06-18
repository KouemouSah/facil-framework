"""Pydantic schemas for the organization module (Create/Update/Response)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_CODE = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$"


class OrganizationCreate(BaseModel):
    code: str = Field(..., pattern=_CODE)
    legal_name: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = Field(None, max_length=255)
    logo_url: str | None = None
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=255)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = Field(None, max_length=120)
    region: str | None = Field(None, max_length=120)
    country_code: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = Field(None, max_length=20)
    tax_id: str | None = Field(None, max_length=80)
    registration_number: str | None = Field(None, max_length=80)
    default_locale: str | None = Field(None, max_length=5)
    timezone: str | None = Field(None, max_length=64)
    currency: str | None = Field(None, min_length=3, max_length=3)
    document_identity: dict = Field(default_factory=dict)
    settings: dict = Field(default_factory=dict)
    # ERP Company links (F.3): consolidation parent + canonical FKs to the
    # party/address/currency master data. Optional; FK integrity enforced by the
    # DB (a bad reference surfaces as 409 via the API's IntegrityError mapping).
    parent_id: str | None = None
    party_id: str | None = None
    hq_address_id: str | None = None
    currency_id: str | None = None

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        return v.strip()

    @field_validator("country_code")
    @classmethod
    def _upper_cc(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    # A cleared picker in the UI sends "" — treat it as "no link" (NULL), never
    # store an empty string that would then fail the existence/FK checks.
    @field_validator("parent_id", "party_id", "hq_address_id", "currency_id",
                     mode="before")
    @classmethod
    def _blank_fk_to_none(cls, v: object) -> object:
        return None if v == "" else v


class OrganizationUpdate(BaseModel):
    """All fields optional; `code` is immutable (not updatable)."""
    legal_name: str | None = Field(None, min_length=1, max_length=255)
    display_name: str | None = None
    logo_url: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    country_code: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = None
    tax_id: str | None = None
    registration_number: str | None = None
    default_locale: str | None = None
    timezone: str | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)
    document_identity: dict | None = None
    settings: dict | None = None
    is_active: bool | None = None
    # ERP Company links (F.3) — see OrganizationCreate. `parent_id` self-reference
    # is rejected by the service (consolidation-cycle guard).
    parent_id: str | None = None
    party_id: str | None = None
    hq_address_id: str | None = None
    currency_id: str | None = None

    @field_validator("parent_id", "party_id", "hq_address_id", "currency_id",
                     mode="before")
    @classmethod
    def _blank_fk_to_none(cls, v: object) -> object:
        return None if v == "" else v


class OrgUnitCreate(BaseModel):
    code: str = Field(..., pattern=_CODE)
    name: str = Field(..., min_length=1, max_length=255)
    unit_type: str = Field("department", max_length=40)
    parent_id: str | None = None
    description: str | None = None
    external_ref: str | None = Field(None, max_length=80)
    metadata: dict = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        return v.strip()


class OrgUnitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    unit_type: str | None = Field(None, max_length=40)
    parent_id: str | None = None  # set to reparent; see service cycle guard
    description: str | None = None
    external_ref: str | None = Field(None, max_length=80)
    metadata: dict | None = None
    is_active: bool | None = None
