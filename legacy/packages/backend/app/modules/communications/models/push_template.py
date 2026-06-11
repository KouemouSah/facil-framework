"""
Push Template Models - Pydantic models for push notification templates

Used for:
- Push notification template CRUD operations
- FCM (Firebase Cloud Messaging) integration
- Multi-language support (es/fr/en)
- Platform-specific templates (iOS, Android, Web)

Module: Communications
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime


class PlatformEnum(str, Enum):
    """Supported push notification platforms"""
    ALL = "all"
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class PushTemplateCreate(BaseModel):
    """Request model for creating push templates"""
    template_code: str = Field(..., min_length=1, max_length=100, description="Unique template code")
    name_es: str = Field(..., min_length=1, max_length=255, description="Template name (Spanish)")
    name_fr: Optional[str] = Field(None, max_length=255, description="Template name (French)")
    name_en: Optional[str] = Field(None, max_length=255, description="Template name (English)")

    title_es: str = Field(..., min_length=1, max_length=100, description="Notification title (Spanish)")
    title_fr: Optional[str] = Field(None, max_length=100, description="Notification title (French)")
    title_en: Optional[str] = Field(None, max_length=100, description="Notification title (English)")

    body_es: str = Field(..., min_length=1, max_length=240, description="Notification body (Spanish)")
    body_fr: Optional[str] = Field(None, max_length=240, description="Notification body (French)")
    body_en: Optional[str] = Field(None, max_length=240, description="Notification body (English)")

    image_url: Optional[str] = Field(None, max_length=500, description="Image URL for rich notifications")
    icon_url: Optional[str] = Field(None, max_length=500, description="Icon URL")
    click_action: Optional[str] = Field(None, max_length=500, description="Deep link or URL")

    data_payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom data payload")
    variables: Optional[List[Any]] = Field(default_factory=list, description="Template variables: strings or objects {name, example, description}")

    platform: PlatformEnum = Field(default=PlatformEnum.ALL, description="Target platform")
    ttl_seconds: int = Field(default=86400, ge=0, le=2419200, description="Time to live in seconds (max 28 days)")
    is_active: bool = Field(default=True, description="Active status")

    @validator('title_es', 'title_fr', 'title_en')
    def validate_title_length(cls, v):
        """Validate title length (recommended max 65 chars)"""
        if v and len(v) > 65:
            raise ValueError('Title should not exceed 65 characters for optimal display')
        return v

    @validator('body_es', 'body_fr', 'body_en')
    def validate_body_length(cls, v):
        """Validate body length (max 240 chars)"""
        if v and len(v) > 240:
            raise ValueError('Body must not exceed 240 characters')
        return v

    @validator('template_code')
    def validate_template_code(cls, v):
        """Validate template code format"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Template code must contain only alphanumeric characters, hyphens, and underscores')
        return v.upper()

    class Config:
        json_schema_extra = {
            "example": {
                "template_code": "PAYMENT_RECEIVED",
                "name_es": "Pago Recibido",
                "name_fr": "Paiement Reçu",
                "name_en": "Payment Received",
                "title_es": "Pago Confirmado",
                "title_fr": "Paiement Confirmé",
                "title_en": "Payment Confirmed",
                "body_es": "Tu pago de {amount} XAF ha sido recibido exitosamente.",
                "body_fr": "Votre paiement de {amount} XAF a été reçu avec succès.",
                "body_en": "Your payment of {amount} XAF has been received successfully.",
                "image_url": "https://example.com/payment-success.png",
                "icon_url": "https://example.com/icon.png",
                "click_action": "/dashboard/payments",
                "data_payload": {"type": "payment", "action": "view"},
                "variables": ["amount", "payment_id"],
                "platform": "all",
                "ttl_seconds": 86400,
                "is_active": True
            }
        }


class PushTemplateUpdate(BaseModel):
    """Request model for updating push templates"""
    name_es: Optional[str] = Field(None, max_length=255)
    name_fr: Optional[str] = Field(None, max_length=255)
    name_en: Optional[str] = Field(None, max_length=255)

    title_es: Optional[str] = Field(None, max_length=100)
    title_fr: Optional[str] = Field(None, max_length=100)
    title_en: Optional[str] = Field(None, max_length=100)

    body_es: Optional[str] = Field(None, max_length=240)
    body_fr: Optional[str] = Field(None, max_length=240)
    body_en: Optional[str] = Field(None, max_length=240)

    image_url: Optional[str] = Field(None, max_length=500)
    icon_url: Optional[str] = Field(None, max_length=500)
    click_action: Optional[str] = Field(None, max_length=500)

    data_payload: Optional[Dict[str, Any]] = None
    variables: Optional[List[Any]] = None

    platform: Optional[PlatformEnum] = None
    ttl_seconds: Optional[int] = Field(None, ge=0, le=2419200)
    is_active: Optional[bool] = None

    @validator('title_es', 'title_fr', 'title_en')
    def validate_title_length(cls, v):
        if v and len(v) > 65:
            raise ValueError('Title should not exceed 65 characters for optimal display')
        return v

    @validator('body_es', 'body_fr', 'body_en')
    def validate_body_length(cls, v):
        if v and len(v) > 240:
            raise ValueError('Body must not exceed 240 characters')
        return v


class PushTemplateResponse(BaseModel):
    """Response model for push template data"""
    id: int
    template_code: str

    name_es: str
    name_fr: Optional[str]
    name_en: Optional[str]

    title_es: str
    title_fr: Optional[str]
    title_en: Optional[str]

    body_es: str
    body_fr: Optional[str]
    body_en: Optional[str]

    image_url: Optional[str]
    icon_url: Optional[str]
    click_action: Optional[str]

    data_payload: Dict[str, Any]
    variables: List[Any]  # Can be List[str] or List[Dict] (mixed format in DB)

    platform: PlatformEnum
    ttl_seconds: int
    is_active: bool

    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "template_code": "PAYMENT_RECEIVED",
                "name_es": "Pago Recibido",
                "name_fr": "Paiement Reçu",
                "name_en": "Payment Received",
                "title_es": "Pago Confirmado",
                "title_fr": "Paiement Confirmé",
                "title_en": "Payment Confirmed",
                "body_es": "Tu pago de {amount} XAF ha sido recibido.",
                "body_fr": "Votre paiement de {amount} XAF a été reçu.",
                "body_en": "Your payment of {amount} XAF has been received.",
                "image_url": "https://example.com/payment.png",
                "icon_url": "https://example.com/icon.png",
                "click_action": "/dashboard/payments",
                "data_payload": {"type": "payment"},
                "variables": ["amount", "payment_id"],
                "platform": "all",
                "ttl_seconds": 86400,
                "is_active": True,
                "created_at": "2025-12-12T10:00:00Z",
                "updated_at": "2025-12-12T10:00:00Z",
                "created_by": 1
            }
        }


class PushTemplateListResponse(BaseModel):
    """Response model for list of push templates"""
    templates: List[PushTemplateResponse]
    total: int
    page: int
    page_size: int

    class Config:
        json_schema_extra = {
            "example": {
                "templates": [],
                "total": 10,
                "page": 1,
                "page_size": 20
            }
        }


class PushNotificationPreview(BaseModel):
    """Model for previewing how push notification will look"""
    title: str
    body: str
    image_url: Optional[str]
    icon_url: Optional[str]
    platform: PlatformEnum
    variables_used: Dict[str, str]

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Pago Confirmado",
                "body": "Tu pago de 50000 XAF ha sido recibido.",
                "image_url": "https://example.com/payment.png",
                "icon_url": "https://example.com/icon.png",
                "platform": "all",
                "variables_used": {
                    "amount": "50000",
                    "payment_id": "PAY-12345"
                }
            }
        }
