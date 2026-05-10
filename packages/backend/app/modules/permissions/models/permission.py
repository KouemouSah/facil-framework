"""
Permission Models - Pydantic schemas for permissions
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator


class PermissionBase(BaseModel):
    """Base permission model with common fields"""
    name: str = Field(..., min_length=3, max_length=100, description="Unique permission name (format: resource.action)")
    resource: str = Field(..., min_length=2, max_length=50, description="Resource name (assignment, declaration, etc.)")
    action: str = Field(..., min_length=2, max_length=50, description="Action name (view, create, edit, delete, etc.)")
    description: Optional[str] = Field(None, description="Permission description in Spanish")
    is_critical: bool = Field(False, description="If true, UI will show warning when granting")
    module_name: Optional[str] = Field(None, max_length=50, description="Module that registered this permission")


class PermissionCreate(PermissionBase):
    """Schema for creating a new permission"""

    @validator('name')
    def validate_name_format(cls, v, values):
        """Validate permission name format: resource.action (for creation only)"""
        if '.' not in v:
            raise ValueError('Permission name must follow format: resource.action')

        parts = v.split('.')
        if len(parts) != 2:
            raise ValueError('Permission name must have exactly one dot separator')

        resource_part, action_part = parts
        if 'resource' in values and resource_part != values['resource']:
            raise ValueError('Permission name resource part must match resource field')
        if 'action' in values and action_part != values['action']:
            raise ValueError('Permission name action part must match action field')

        return v


class PermissionUpdate(BaseModel):
    """Schema for updating an existing permission"""
    description: Optional[str] = None
    is_critical: Optional[bool] = None
    module_name: Optional[str] = None


class PermissionResponse(PermissionBase):
    """Schema for permission responses"""
    id: UUID = Field(..., description="Permission UUID")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2 (was orm_mode in v1)
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "assignment.reassign_in_progress",
                "resource": "assignment",
                "action": "reassign_in_progress",
                "description": "Reasignar tarea EN CURSO (permiso crítico)",
                "is_critical": True,
                "module_name": "assignment",
                "created_at": "2025-11-17T10:00:00Z",
                "updated_at": "2025-11-17T10:00:00Z"
            }
        }


class PermissionListResponse(BaseModel):
    """Schema for paginated permission list"""
    permissions: list[PermissionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PermissionsByModuleResponse(BaseModel):
    """Schema for permissions grouped by module"""
    module_name: str
    permissions: list[PermissionResponse]
    total: int = Field(default=0, description="Total permissions in this module")
