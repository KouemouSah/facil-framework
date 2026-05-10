"""
RolePermission Models - Association between roles and permissions
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class RolePermissionBase(BaseModel):
    """Base role-permission association model"""
    role_id: UUID = Field(..., description="Role UUID")
    permission_id: UUID = Field(..., description="Permission UUID")
    granted: bool = Field(True, description="True if granted, False if explicitly denied")


class RolePermissionCreate(RolePermissionBase):
    """Schema for creating a new role-permission association"""
    pass


class RolePermissionResponse(RolePermissionBase):
    """Schema for role-permission response"""
    created_at: datetime
    created_by: Optional[UUID] = Field(None, description="User ID who created this association")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "role_id": "123e4567-e89b-12d3-a456-426614174000",
                "permission_id": "987e6543-e21b-12d3-a456-426614174999",
                "granted": True,
                "created_at": "2025-11-17T10:00:00Z",
                "created_by": "admin-user-id"
            }
        }


class RolePermissionWithDetails(BaseModel):
    """Schema for role-permission with full details"""
    role_id: UUID
    role_name: str
    role_code: str
    permission_id: UUID
    permission_name: str
    permission_resource: str
    permission_action: str
    permission_is_critical: bool
    granted: bool
    created_at: datetime

    class Config:
        from_attributes = True
