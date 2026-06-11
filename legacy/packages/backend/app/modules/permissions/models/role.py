"""
Role Models - Pydantic schemas for roles

Updated 2026-01-19: Added menu_config and dashboard_config for dynamic menu system
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator


class RoleBase(BaseModel):
    """Base role model with common fields"""
    name: str = Field(..., min_length=2, max_length=100, description="Role display name")
    code: str = Field(..., min_length=2, max_length=50, description="Unique role code (used in code)")
    entity_type: Optional[str] = Field(None, max_length=50, description="Entity type: DGI, Ministry, or NULL for global")
    description: Optional[str] = Field(None, description="Role description")
    menu_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Menu configuration JSON. NULL = auto-generate from entity.workflow_codes"
    )
    dashboard_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Dashboard widget configuration JSON. NULL = default dashboard"
    )
    ui_config: Optional[Dict[str, Any]] = Field(
        None,
        description="UI preferences (theme, shortcuts, display options). NULL = defaults"
    )
    default_agent_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Default agent profile config for this role. NULL = system defaults"
    )


class RoleCreate(RoleBase):
    """Schema for creating a new role"""

    @validator('code')
    def validate_code_format(cls, v):
        """Validate role code format: lowercase with underscores only (for creation only)"""
        if not v.replace('_', '').isalnum():
            raise ValueError('Role code must contain only alphanumeric characters and underscores')
        if v != v.lower():
            raise ValueError('Role code must be lowercase')
        return v

    @validator('entity_type')
    def validate_entity_type(cls, v):
        """Validate entity_type is one of allowed agent_type values"""
        # Valid agent_type values from agent_profiles table (migration 048)
        valid_agent_types = ['ministry_agent', 'entity_agent']
        if v is not None and v not in valid_agent_types:
            raise ValueError(f'entity_type must be one of: {", ".join(valid_agent_types)}, or NULL')
        return v


class RoleUpdate(BaseModel):
    """Schema for updating an existing role"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    menu_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Menu configuration JSON. Set to empty dict {} to remove, NULL to keep unchanged"
    )
    dashboard_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Dashboard widget configuration JSON"
    )
    ui_config: Optional[Dict[str, Any]] = Field(
        None,
        description="UI preferences JSON"
    )
    default_agent_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Default agent config. Set to {} to clear."
    )


class WidgetConfigSchema(BaseModel):
    """Validates a single dashboard widget configuration entry"""
    id: str = Field(..., min_length=1, max_length=50)
    visible: bool
    position: int = Field(..., ge=0)
    size: Literal['small', 'medium', 'large', 'full']

    class Config:
        extra = 'allow'


class DashboardConfigSchema(BaseModel):
    """Structured validation for roles.dashboard_config"""
    version: str = Field(default='1.0', max_length=10)
    layout: Literal['grid', 'list', 'custom'] = 'grid'
    widgets: List[WidgetConfigSchema] = Field(default_factory=list)

    class Config:
        extra = 'allow'


class UiConfigSchema(BaseModel):
    """Structured validation for roles.ui_config"""
    theme: Optional[Literal['default', 'compact']] = 'default'
    table_density: Optional[Literal['comfortable', 'compact']] = 'comfortable'
    auto_refresh_interval: Optional[int] = Field(default=0, ge=0, le=3600)

    class Config:
        extra = 'allow'


class RoleMenuConfigUpdate(BaseModel):
    """
    Typed request body for PUT /{role_id}/menu-config.
    Each field is optional — None means 'no change for this field'.
    """
    menu_config: Optional[Dict[str, Any]] = None
    dashboard_config: Optional[DashboardConfigSchema] = None
    ui_config: Optional[UiConfigSchema] = None


class RoleResponse(RoleBase):
    """Schema for role responses"""
    id: UUID = Field(..., description="Role UUID")
    is_system: bool = Field(..., description="System roles cannot be modified/deleted")
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = Field(None, description="User ID who created this role (NULL for system roles)")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Supervisor Entidad Junior",
                "code": "supervisor_entity_junior",
                "entity_type": "agent",
                "description": "Supervisor junior con permisos limitados",
                "is_system": False,
                "created_at": "2025-11-17T10:00:00Z",
                "updated_at": "2025-11-17T10:00:00Z",
                "created_by": "admin-user-id"
            }
        }


class RoleWithPermissionsResponse(RoleResponse):
    """Schema for role with associated permissions"""
    permissions: List[str] = Field(default_factory=list, description="List of permission names")
    permissions_count: int = Field(0, description="Total number of permissions")


class RoleListResponse(BaseModel):
    """Schema for paginated role list"""
    roles: List[RoleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AssignPermissionsToRoleRequest(BaseModel):
    """Schema for assigning multiple permissions to a role"""
    permission_ids: List[UUID] = Field(..., min_length=1, description="List of permission UUIDs to assign")
    granted: bool = Field(True, description="True to grant, False to deny")

    @validator('permission_ids')
    def validate_permission_ids(cls, v):
        """Ensure permission IDs are unique"""
        if len(v) != len(set(v)):
            raise ValueError('Duplicate permission IDs found')
        return v


class RemovePermissionsFromRoleRequest(BaseModel):
    """Schema for removing permissions from a role"""
    permission_ids: List[UUID] = Field(..., min_length=1, description="List of permission UUIDs to remove")

    @validator('permission_ids')
    def validate_permission_ids(cls, v):
        """Ensure permission IDs are unique"""
        if len(v) != len(set(v)):
            raise ValueError('Duplicate permission IDs found')
        return v
