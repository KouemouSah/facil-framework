"""Pydantic schemas for the location module (Site Create/Update)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_CODE = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$"


class SiteCreate(BaseModel):
    organization_id: str
    org_unit_id: str | None = None
    parent_site_id: str | None = None
    code: str = Field(..., pattern=_CODE)
    name: str = Field(..., min_length=1, max_length=255)
    site_type: str = Field("branch", max_length=40)
    address_id: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = Field(None, max_length=120)
    region: str | None = Field(None, max_length=120)
    country_code: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = Field(None, max_length=20)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    operating_hours: dict = Field(default_factory=dict)
    timezone: str | None = Field(None, max_length=64)
    is_primary: bool = False
    notes: str | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        return v.strip()

    @field_validator("country_code")
    @classmethod
    def _upper_cc(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("org_unit_id", "parent_site_id", "address_id", mode="before")
    @classmethod
    def _blank_fk_to_none(cls, v: object) -> object:
        return None if v == "" else v


class SiteUpdate(BaseModel):
    """All optional; `code` and `organization_id` are immutable."""
    org_unit_id: str | None = None
    parent_site_id: str | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    site_type: str | None = Field(None, max_length=40)
    address_id: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    country_code: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    phone: str | None = None
    email: str | None = None
    operating_hours: dict | None = None
    timezone: str | None = None
    is_primary: bool | None = None
    notes: str | None = None
    metadata: dict | None = None
    is_active: bool | None = None

    @field_validator("org_unit_id", "parent_site_id", "address_id", mode="before")
    @classmethod
    def _blank_fk_to_none(cls, v: object) -> object:
        return None if v == "" else v
