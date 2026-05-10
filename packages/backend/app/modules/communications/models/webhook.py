"""
Pydantic models for webhook configurations
"""
from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class WebhookType(str, Enum):
    """Webhook type enumeration"""
    whatsapp = "whatsapp"
    custom = "custom"


class HttpMethod(str, Enum):
    """HTTP method enumeration"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class AuthType(str, Enum):
    """Authentication type enumeration"""
    none = "none"
    api_key = "api_key"
    bearer = "bearer"
    basic = "basic"


class RetryConfig(BaseModel):
    """Retry configuration"""
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=1, le=3600)

    class Config:
        json_schema_extra = {
            "example": {
                "max_retries": 3,
                "retry_delay_seconds": 60
            }
        }


class AuthConfig(BaseModel):
    """Authentication configuration"""
    api_key: Optional[str] = None
    api_key_header: Optional[str] = Field(default="X-API-Key")
    bearer_token: Optional[str] = None
    basic_username: Optional[str] = None
    basic_password: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "api_key": "your-api-key",
                "api_key_header": "X-API-Key"
            }
        }


class WebhookBase(BaseModel):
    """Base webhook configuration model"""
    name: str = Field(..., min_length=1, max_length=255)
    webhook_type: WebhookType
    endpoint_url: str = Field(..., max_length=1000)
    http_method: HttpMethod = HttpMethod.POST
    headers: Dict[str, str] = Field(default_factory=dict)
    auth_type: AuthType = AuthType.none
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    payload_template: Optional[Dict[str, Any]] = None
    retry_config: RetryConfig = Field(default_factory=RetryConfig)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    events: List[str] = Field(default_factory=list)
    is_active: bool = True

    @field_validator('endpoint_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "WhatsApp Notifications",
                "webhook_type": "whatsapp",
                "endpoint_url": "https://api.whatsapp.com/v1/messages",
                "http_method": "POST",
                "headers": {"Content-Type": "application/json"},
                "auth_type": "bearer",
                "auth_config": {"bearer_token": "your-token"},
                "payload_template": {
                    "messaging_product": "whatsapp",
                    "to": "{{phone_number}}",
                    "type": "template",
                    "template": {
                        "name": "{{template_name}}",
                        "language": {"code": "es"}
                    }
                },
                "retry_config": {"max_retries": 3, "retry_delay_seconds": 60},
                "timeout_seconds": 30,
                "events": ["payment_received", "declaration_submitted"],
                "is_active": True
            }
        }


class WebhookCreate(WebhookBase):
    """Request model for creating webhook configurations"""
    pass


class WebhookUpdate(BaseModel):
    """Request model for updating webhook configurations"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    webhook_type: Optional[WebhookType] = None
    endpoint_url: Optional[str] = Field(None, max_length=1000)
    http_method: Optional[HttpMethod] = None
    headers: Optional[Dict[str, str]] = None
    auth_type: Optional[AuthType] = None
    auth_config: Optional[Dict[str, Any]] = None
    payload_template: Optional[Dict[str, Any]] = None
    retry_config: Optional[RetryConfig] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator('endpoint_url')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL format"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class WebhookResponse(WebhookBase):
    """Response model for webhook configurations"""
    id: int
    last_triggered_at: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class WebhookLogBase(BaseModel):
    """Base webhook log model"""
    webhook_id: int
    event_type: str
    request_payload: Dict[str, Any]
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class WebhookLogCreate(WebhookLogBase):
    """Request model for creating webhook logs"""
    pass


class WebhookLogResponse(WebhookLogBase):
    """Response model for webhook logs"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookTestRequest(BaseModel):
    """Request model for testing webhooks"""
    test_payload: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "test_payload": {
                    "phone_number": "+240222123456",
                    "template_name": "payment_confirmation",
                    "message": "Test message"
                }
            }
        }


class WebhookTestResponse(BaseModel):
    """Response model for webhook test results"""
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    duration_ms: int
    error_message: Optional[str] = None
    request_url: str
    request_method: str
    request_headers: Dict[str, str]
    request_payload: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "status_code": 200,
                "response_body": '{"status": "sent"}',
                "duration_ms": 245,
                "error_message": None,
                "request_url": "https://api.whatsapp.com/v1/messages",
                "request_method": "POST",
                "request_headers": {"Authorization": "Bearer ***"},
                "request_payload": {"to": "+240222123456"}
            }
        }


class WebhookListResponse(BaseModel):
    """Response model for webhook list with pagination"""
    webhooks: List[WebhookResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
