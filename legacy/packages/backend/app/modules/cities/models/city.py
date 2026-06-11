"""
City Pydantic models.

Defines the data structures for city and entity management.
"""

from datetime import datetime
from typing import Optional, List, Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# Valid regions (fixed)
VALID_REGIONS = ["Insular", "Continental"]
RegionType = Literal["Insular", "Continental"]


class CityBase(BaseModel):
    """Base model with common city fields."""
    name: str = Field(..., min_length=2, max_length=100)
    region: RegionType
    description: Optional[str] = None
    is_capital: bool = False
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Normalize city name (capitalize first letter)."""
        return v.strip().title()


class CityCreate(CityBase):
    """Model for creating a new city."""
    pass


class CityUpdate(BaseModel):
    """Model for updating a city. All fields optional."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    region: Optional[RegionType] = None
    description: Optional[str] = None
    is_capital: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip().title()


class City(CityBase):
    """Full city model with all fields."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None

    model_config = {"from_attributes": True}


class CityResponse(BaseModel):
    """Response model for a single city."""
    id: UUID
    name: str
    region: RegionType
    description: Optional[str] = None
    is_capital: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CitySimple(BaseModel):
    """Simplified city model for dropdowns."""
    id: UUID
    name: str
    region: RegionType
    is_capital: bool

    model_config = {"from_attributes": True}


class CityListResponse(BaseModel):
    """Response model for list of cities."""
    items: List[CityResponse]
    total: int


# =============================================================================
# Entity models
# =============================================================================

from enum import Enum


class EntityType(str, Enum):
    """Entity type enum - matches DB entity_type_enum."""
    ENTITY = "entity"        # Top-level entity (independent or ministry-linked)
    DEPARTMENT = "department"  # Department within an entity (must have parent)
    TREASURY = "treasury"    # Treasury entity (Tesoro Público — payment validation)


class EntityBase(BaseModel):
    """Base model with common entity fields."""
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    entity_type: EntityType = Field(default=EntityType.ENTITY)
    parent_entity_id: Optional[UUID] = Field(
        None,
        description="Parent entity ID (required for departments)"
    )
    ministry_id: Optional[int] = Field(
        None,
        description="Ministry ID (optional link to ministries table)"
    )
    workflow_codes: List[str] = Field(
        default_factory=list,
        description="Array of workflow codes this entity handles. Codes must exist in workflows table."
    )
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Normalize entity code to uppercase."""
        return v.strip().upper()

    @field_validator("workflow_codes")
    @classmethod
    def validate_workflow_codes(cls, v: List[str]) -> List[str]:
        """Normalize workflow codes to uppercase."""
        if v is None:
            return []
        return [code.strip().upper() for code in v]


class EntityCreate(EntityBase):
    """Model for creating a new entity."""
    pass


class EntityUpdate(BaseModel):
    """Model for updating an entity. All fields optional."""
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    entity_type: Optional[EntityType] = None
    parent_entity_id: Optional[UUID] = None
    ministry_id: Optional[int] = None
    workflow_codes: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip().upper()

    @field_validator("workflow_codes")
    @classmethod
    def validate_workflow_codes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return [code.strip().upper() for code in v]


class Entity(EntityBase):
    """Full entity model with all fields."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None

    model_config = {"from_attributes": True}


class EntityResponse(BaseModel):
    """Response model for a single entity."""
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    entity_type: EntityType
    parent_entity_id: Optional[UUID] = None
    ministry_id: Optional[int] = None
    workflow_codes: List[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntityWithDetails(EntityResponse):
    """Entity response with joined details (parent, ministry, resolved workflows)."""
    # Parent entity info
    parent_entity_code: Optional[str] = None
    parent_entity_name: Optional[str] = None
    # Ministry info
    ministry_code: Optional[str] = None
    ministry_name: Optional[str] = None
    # Resolved workflows (inherited if entity.workflow_codes is empty)
    resolved_workflow_codes: List[str] = Field(default_factory=list)
    workflow_count: int = 0


class EntitySimple(BaseModel):
    """Simplified entity model for dropdowns."""
    id: UUID
    code: str
    name: str
    entity_type: EntityType = EntityType.ENTITY

    model_config = {"from_attributes": True}


class EntityListResponse(BaseModel):
    """Response model for list of entities."""
    items: List[EntityResponse]
    total: int


class EntityWithDetailsListResponse(BaseModel):
    """Response model for list of entities with details."""
    items: List[EntityWithDetails]
    total: int
