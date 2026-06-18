"""Pydantic schemas for the party module."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.modules.party.models import PARTY_TYPES


class PartyIn(BaseModel):
    party_type: str = "organization"
    name: str = Field(min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, max_length=80)
    registration_number: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    custom_fields: dict = Field(default_factory=dict)

    @field_validator("party_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in PARTY_TYPES:
            raise ValueError(f"party_type must be one of {PARTY_TYPES}")
        return v


class PartyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=80)
    registration_number: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    custom_fields: dict | None = None


class PartyRoleIn(BaseModel):
    role: str = Field(min_length=1, max_length=40)


class AddressIn(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    line1: str | None = None
    line2: str | None = None
    city: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    country_id: str | None = None
    country_region_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AddressUpdate(AddressIn):
    pass


class PartyAddressIn(BaseModel):
    address_id: str
    address_type: str = Field(default="main", max_length=30)
    is_primary: bool = False
