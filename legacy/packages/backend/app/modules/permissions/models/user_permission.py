"""
UserPermission Models - User-specific permission overrides
"""
from typing import Optional
from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, Field, validator


class UserPermissionBase(BaseModel):
    """Base user-permission model"""
    user_id: UUID = Field(..., description="User UUID")
    permission_id: UUID = Field(..., description="Permission UUID")
    granted: bool = Field(True, description="True to grant, False to deny")
    expires_at: Optional[datetime] = Field(None, description="Expiration date for temporary permissions (NULL for permanent)")
    reason: Optional[str] = Field(None, description="Reason for granting/denying this permission (for audit)")


class UserPermissionCreate(UserPermissionBase):
    """Schema for creating a new user permission override"""

    @validator('expires_at')
    def validate_expires_at(cls, v):
        """Ensure expiration date is in the future"""
        if v is not None and v <= datetime.now(timezone.utc):
            raise ValueError('Expiration date must be in the future')
        return v


class UserPermissionUpdate(BaseModel):
    """Schema for updating an existing user permission"""
    granted: Optional[bool] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None

    @validator('expires_at')
    def validate_expires_at(cls, v):
        """Ensure expiration date is in the future or NULL"""
        if v is not None and v <= datetime.now(timezone.utc):
            raise ValueError('Expiration date must be in the future or NULL to remove expiration')
        return v


class UserPermissionResponse(UserPermissionBase):
    """Schema for user permission response"""
    granted_by: Optional[UUID] = Field(None, description="Admin user ID who granted this permission")
    granted_at: datetime
    is_expired: bool = Field(..., description="True if permission has expired")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "user-uuid-123",
                "permission_id": "perm-uuid-456",
                "granted": True,
                "granted_by": "admin-uuid-789",
                "granted_at": "2025-11-17T10:00:00Z",
                "expires_at": "2025-11-24T10:00:00Z",
                "reason": "Permiso temporal para emergencia",
                "is_expired": False
            }
        }


class UserPermissionWithDetails(BaseModel):
    """Schema for user permission with full details"""
    user_id: UUID
    user_email: str
    user_full_name: str
    permission_id: UUID
    permission_name: str
    permission_resource: str
    permission_action: str
    permission_is_critical: bool
    granted: bool
    granted_by: Optional[UUID]
    granted_by_name: Optional[str]
    granted_at: datetime
    expires_at: Optional[datetime]
    reason: Optional[str]
    is_expired: bool

    class Config:
        from_attributes = True


class UserPermissionListResponse(BaseModel):
    """Schema for paginated user permission list"""
    permissions: list[UserPermissionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class GrantPermissionToUserRequest(BaseModel):
    """Schema for granting a permission to a user"""
    user_id: UUID = Field(..., description="Target user UUID")
    permission_id: UUID = Field(..., description="Permission UUID to grant")
    expires_at: Optional[datetime] = Field(None, description="Expiration date (NULL for permanent)")
    reason: Optional[str] = Field(None, description="Reason for granting (for audit)")

    @validator('expires_at')
    def validate_expires_at(cls, v):
        """Ensure expiration date is in the future"""
        if v is not None and v <= datetime.now(timezone.utc):
            raise ValueError('Expiration date must be in the future')
        return v


class RevokePermissionFromUserRequest(BaseModel):
    """Schema for revoking a permission from a user"""
    user_id: UUID = Field(..., description="Target user UUID")
    permission_id: UUID = Field(..., description="Permission UUID to revoke")
    reason: Optional[str] = Field(None, description="Reason for revoking (for audit)")


class UserPermissionsSummary(BaseModel):
    """Summary of user's permissions (role + overrides)"""
    user_id: UUID
    user_email: str
    role_code: Optional[str] = None
    role_name: Optional[str] = None
    role_permissions_count: int = 0
    user_overrides_count: int = 0
    total_permissions: int = 0
    has_expired_permissions: bool = False
