"""
Communication Provider Settings Models

Pydantic models for managing communication provider configurations
(SMS, Email, Push, WhatsApp)
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class CommunicationProviderType(str, Enum):
    """Types of communication providers"""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    WHATSAPP = "whatsapp"


class ProviderSettingsCreate(BaseModel):
    """Model for creating a provider configuration"""
    provider_type: CommunicationProviderType = Field(..., description="Type of provider")
    provider_name: str = Field(..., min_length=1, max_length=100, description="Display name")
    provider_code: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[A-Z0-9_]+$",
        description="Unique code (uppercase, underscores allowed)"
    )

    api_base_url: Optional[str] = Field(None, max_length=500, description="API base URL")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted)")
    api_secret: Optional[str] = Field(None, description="API secret (will be encrypted)")

    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration"
    )

    is_active: bool = Field(True, description="Whether provider is active")
    is_default: bool = Field(False, description="Whether this is the default provider for its type")
    rate_limit_per_minute: int = Field(100, ge=1, le=10000, description="Rate limit per minute")
    retry_attempts: int = Field(3, ge=0, le=10, description="Number of retry attempts")
    timeout_seconds: int = Field(30, ge=5, le=120, description="Request timeout in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "provider_type": "sms",
                "provider_name": "Infobip",
                "provider_code": "INFOBIP_SMS",
                "api_base_url": "https://y45e8g.api.infobip.com",
                "api_key": "your-api-key",
                "config": {
                    "sender_id": "Facil",
                    "sms_endpoint": "/sms/2/text/advanced"
                },
                "is_active": True,
                "is_default": True,
                "rate_limit_per_minute": 100,
                "retry_attempts": 3,
                "timeout_seconds": 30
            }
        }


class ProviderSettingsUpdate(BaseModel):
    """Model for updating a provider configuration"""
    provider_name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_base_url: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = Field(None, description="New API key (will be encrypted)")
    api_secret: Optional[str] = Field(None, description="New API secret (will be encrypted)")
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    retry_attempts: Optional[int] = Field(None, ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=120)


class ProviderSettingsResponse(BaseModel):
    """Response model for provider configuration"""
    id: int
    provider_type: CommunicationProviderType
    provider_name: str
    provider_code: str

    api_base_url: Optional[str]
    has_api_key: bool = Field(description="Whether API key is configured")
    has_api_secret: bool = Field(description="Whether API secret is configured")

    config: Dict[str, Any]

    is_active: bool
    is_default: bool
    rate_limit_per_minute: int
    retry_attempts: int
    timeout_seconds: int

    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class ProviderSettingsListResponse(BaseModel):
    """Response model for listing provider configurations"""
    providers: list[ProviderSettingsResponse]
    total: int


class ProviderTestRequest(BaseModel):
    """Request to test a provider connection"""
    provider_code: str = Field(..., description="Provider code to test")
    test_recipient: Optional[str] = Field(
        None,
        description="Test recipient (phone for SMS, email for Email)"
    )


class ProviderTestResponse(BaseModel):
    """Response from provider connection test"""
    success: bool
    provider_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    tested_at: datetime = Field(default_factory=datetime.utcnow)


class SmsProviderConfig(BaseModel):
    """SMS provider specific configuration"""
    sender_id: str = Field("Facil", description="SMS sender ID")
    sms_endpoint: str = Field("/sms/2/text/advanced", description="SMS send endpoint")
    delivery_report_endpoint: str = Field("/sms/1/reports", description="Delivery report endpoint")
    balance_endpoint: str = Field("/account/1/balance", description="Balance check endpoint")
    supports_unicode: bool = Field(True, description="Whether provider supports Unicode")
    max_segments: int = Field(10, description="Maximum SMS segments")
    country_code: str = Field("+240", description="Default country code")


class EmailProviderConfig(BaseModel):
    """Email provider specific configuration"""
    from_email: str = Field(..., description="Default from email")
    from_name: str = Field("Facil", description="Default from name")
    send_endpoint: str = Field("/mail/send", description="Email send endpoint")
    templates_enabled: bool = Field(True, description="Whether templates are enabled")
    tracking_enabled: bool = Field(True, description="Whether tracking is enabled")


class PushProviderConfig(BaseModel):
    """Push notification provider specific configuration"""
    project_id: str = Field(..., description="Firebase project ID")
    send_endpoint: str = Field(..., description="Push send endpoint")
    platforms: list[str] = Field(
        default=["android", "ios", "web"],
        description="Supported platforms"
    )
    priority: str = Field("high", description="Default notification priority")


class WhatsAppProviderConfig(BaseModel):
    """WhatsApp provider specific configuration"""
    phone_number_id: str = Field(..., description="WhatsApp phone number ID")
    business_account_id: str = Field(..., description="Business account ID")
    send_endpoint: str = Field("/messages", description="Message send endpoint")
    templates_endpoint: str = Field("/message_templates", description="Templates endpoint")
    webhook_verify_token: str = Field(..., description="Webhook verification token")
