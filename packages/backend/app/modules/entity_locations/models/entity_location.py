"""
Entity Location Pydantic models.

Defines the data structures for entity office locations.
Each entity (CNEDOGE, DGT, etc.) can have locations in different cities.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator


# Default entity codes (can be extended dynamically)
DEFAULT_ENTITY_CODES = ["CNEDOGE", "DGT", "EXTRANJERIA", "MINFP", "ONRC", "MINHV"]

# Default cities (can be extended dynamically)
DEFAULT_CITIES = ["Malabo", "Bata", "Mongomo", "Evinayong", "Ebebiyin"]

# Valid regions
VALID_REGIONS = ["Insular", "Continental"]

# Default city to region mapping (used as suggestion for auto-fill)
DEFAULT_CITY_REGION_MAP = {
    "Malabo": "Insular",
    "Bata": "Continental",
    "Mongomo": "Continental",
    "Evinayong": "Continental",
    "Ebebiyin": "Continental",
}



class DayHours(BaseModel):
    """Operating hours for a single day."""
    open: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")
    close: str = Field(default="16:00", pattern=r"^\d{2}:\d{2}$")


class OperatingHours(BaseModel):
    """Operating hours for each day of the week."""
    monday: Optional[DayHours] = DayHours()
    tuesday: Optional[DayHours] = DayHours()
    wednesday: Optional[DayHours] = DayHours()
    thursday: Optional[DayHours] = DayHours()
    friday: Optional[DayHours] = DayHours()
    saturday: Optional[DayHours] = None
    sunday: Optional[DayHours] = None


class EntityLocationBase(BaseModel):
    """Base model with common fields."""
    entity_code: str = Field(..., min_length=2, max_length=50)
    city: str = Field(..., min_length=2, max_length=100)
    region: str = Field(..., min_length=2, max_length=50)
    location_name: str = Field(..., min_length=3, max_length=255)
    location_address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    is_main_office: bool = False
    is_active: bool = True
    operating_hours: Optional[OperatingHours] = None
    notes: Optional[str] = None

    @field_validator("entity_code")
    @classmethod
    def validate_entity_code(cls, v: str) -> str:
        """Normalize entity code to uppercase."""
        return v.upper()

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate region is either Insular or Continental."""
        v = v.strip().title()
        if v not in VALID_REGIONS:
            raise ValueError(f"region must be one of {VALID_REGIONS}")
        return v

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        """Normalize city name (capitalize first letter)."""
        return v.strip().title()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Remove spaces and validate basic format
        v = v.strip()
        if v and not v.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Invalid phone number format")
        return v


class EntityLocationCreate(EntityLocationBase):
    """Model for creating a new entity location."""

    @classmethod
    def get_suggested_region(cls, city: str) -> str:
        """Get suggested region based on known city mappings."""
        return DEFAULT_CITY_REGION_MAP.get(city, "Continental")

    model_config = {
        "json_schema_extra": {
            "example": {
                "entity_code": "CNEDOGE",
                "city": "Malabo",
                "region": "Insular",
                "location_name": "CNEDOGE Malabo",
                "location_address": "Monstoles",
                "phone": "+240 222 251 000",
                "is_main_office": True,
                "is_active": True,
            }
        }
    }


class EntityLocationUpdate(BaseModel):
    """Model for updating an entity location. All fields optional."""
    entity_code: Optional[str] = Field(None, min_length=2, max_length=50)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    region: Optional[str] = Field(None, min_length=2, max_length=50)
    location_name: Optional[str] = Field(None, min_length=3, max_length=255)
    location_address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    is_main_office: Optional[bool] = None
    is_active: Optional[bool] = None
    operating_hours: Optional[OperatingHours] = None
    notes: Optional[str] = None

    @field_validator("entity_code")
    @classmethod
    def validate_entity_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.upper()

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().title()
        if v not in VALID_REGIONS:
            raise ValueError(f"region must be one of {VALID_REGIONS}")
        return v

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip().title()

    model_config = {
        "json_schema_extra": {
            "example": {
                "location_name": "CNEDOGE Malabo - Sede Central",
                "phone": "+240 222 251 001",
            }
        }
    }


class EntityLocation(EntityLocationBase):
    """Full entity location model with all fields."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None

    model_config = {"from_attributes": True}


class EntityLocationResponse(BaseModel):
    """Response model for a single entity location."""
    id: UUID
    entity_code: str
    city: str
    region: str
    location_name: str
    location_address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_main_office: bool
    is_active: bool
    operating_hours: Optional[OperatingHours] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "entity_code": "CNEDOGE",
                "city": "Malabo",
                "region": "Insular",
                "location_name": "CNEDOGE Malabo",
                "location_address": "Monstoles",
                "phone": "+240 222 251 000",
                "email": None,
                "is_main_office": True,
                "is_active": True,
                "operating_hours": {
                    "monday": {"open": "08:00", "close": "16:00"},
                    "tuesday": {"open": "08:00", "close": "16:00"},
                    "wednesday": {"open": "08:00", "close": "16:00"},
                    "thursday": {"open": "08:00", "close": "16:00"},
                    "friday": {"open": "08:00", "close": "16:00"},
                },
                "notes": None,
                "created_at": "2026-01-03T10:00:00Z",
                "updated_at": "2026-01-03T10:00:00Z",
            }
        }
    }


class EntityLocationListResponse(BaseModel):
    """Response model for list of entity locations."""
    items: List[EntityLocationResponse]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 10,
                "page": 1,
                "page_size": 20,
                "total_pages": 1,
            }
        }
    }


class EntityLocationSimple(BaseModel):
    """Simplified location model for dropdowns and selectors."""
    id: UUID
    entity_code: str
    city: str
    region: str
    location_name: str
    is_main_office: bool

    model_config = {"from_attributes": True}
