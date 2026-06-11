"""
Authentication models for TaxasGE Backend
Session and refresh token models for authentication management
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TokenType(str, Enum):
    """Token type enumeration"""
    access = "access"
    refresh = "refresh"


class SessionStatus(str, Enum):
    """Session status enumeration"""
    active = "active"
    expired = "expired"
    revoked = "revoked"


class Session(BaseModel):
    """User session model"""
    id: str = Field(..., description="Session ID (UUID)")
    user_id: str = Field(..., description="User ID")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    status: SessionStatus = Field(default=SessionStatus.active, description="Session status")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    expires_at: datetime = Field(..., description="Session expiration time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    revoked_at: Optional[datetime] = Field(None, description="Revocation timestamp")


class SessionCreate(BaseModel):
    """Model for creating a new session"""
    user_id: str = Field(..., description="User ID")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    expires_at: datetime = Field(..., description="Session expiration time")


class SessionResponse(BaseModel):
    """Model for session response"""
    id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    access_token: str = Field(..., description="Access token (for current session identification)")
    status: SessionStatus = Field(..., description="Session status")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    expires_at: datetime = Field(..., description="Session expiration time")


class RefreshToken(BaseModel):
    """Refresh token model"""
    id: str = Field(..., description="Refresh token ID (UUID)")
    token: str = Field(..., description="Refresh token value (hashed)")
    user_id: str = Field(..., description="User ID")
    session_id: str = Field(..., description="Associated session ID")
    is_revoked: bool = Field(default=False, description="Revocation status")
    expires_at: datetime = Field(..., description="Token expiration time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Token creation time")
    revoked_at: Optional[datetime] = Field(None, description="Revocation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last use timestamp")


class RefreshTokenCreate(BaseModel):
    """Model for creating a new refresh token"""
    token: str = Field(..., description="Refresh token value")
    user_id: str = Field(..., description="User ID")
    session_id: str = Field(..., description="Associated session ID")
    expires_at: datetime = Field(..., description="Token expiration time")


class RefreshTokenResponse(BaseModel):
    """Model for refresh token response"""
    id: str = Field(..., description="Refresh token ID")
    user_id: str = Field(..., description="User ID")
    session_id: str = Field(..., description="Associated session ID")
    is_revoked: bool = Field(..., description="Revocation status")
    expires_at: datetime = Field(..., description="Token expiration time")
    created_at: datetime = Field(..., description="Token creation time")
    last_used_at: Optional[datetime] = Field(None, description="Last use timestamp")


class TokenRefreshRequest(BaseModel):
    """Model for token refresh request"""
    refresh_token: str = Field(..., description="Refresh token")


class TokenRefreshResponse(BaseModel):
    """Model for token refresh response"""
    access_token: str = Field(..., description="New access token")
    refresh_token: str = Field(..., description="New refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    # User data so frontend can update role_code/permissions after token refresh
    user: Optional[dict] = Field(None, description="Updated user data with role_code")


class LogoutRequest(BaseModel):
    """Model for logout request"""
    refresh_token: Optional[str] = Field(None, description="Refresh token to revoke")
    all_sessions: bool = Field(default=False, description="Revoke all user sessions")


class LogoutResponse(BaseModel):
    """Model for logout response"""
    message: str = Field(..., description="Logout message")
    sessions_revoked: int = Field(..., description="Number of sessions revoked")
