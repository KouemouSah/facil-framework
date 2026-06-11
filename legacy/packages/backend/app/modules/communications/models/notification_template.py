"""
Notification Template Models

Pydantic models for notification template management
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class NotificationType(str, Enum):
    """Notification type enumeration"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NotificationPriority(str, Enum):
    """Notification priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationTemplateCreate(BaseModel):
    """Model for creating a notification template"""
    template_code: str = Field(..., min_length=1, max_length=100, description="Unique template code")

    # Multilingual names
    name_es: str = Field(..., min_length=1, max_length=255, description="Template name (Spanish)")
    name_fr: Optional[str] = Field(None, max_length=255, description="Template name (French)")
    name_en: Optional[str] = Field(None, max_length=255, description="Template name (English)")

    # Multilingual titles
    title_es: str = Field(..., min_length=1, max_length=255, description="Notification title (Spanish)")
    title_fr: Optional[str] = Field(None, max_length=255, description="Notification title (French)")
    title_en: Optional[str] = Field(None, max_length=255, description="Notification title (English)")

    # Multilingual bodies
    body_es: str = Field(..., min_length=1, description="Notification body (Spanish)")
    body_fr: Optional[str] = Field(None, description="Notification body (French)")
    body_en: Optional[str] = Field(None, description="Notification body (English)")

    # Notification settings
    icon: Optional[str] = Field(None, max_length=100, description="Lucide icon name")
    action_url: Optional[str] = Field(None, max_length=500, description="Action URL for notification")
    variables: List[Any] = Field(default_factory=list, description="Template variables: strings or objects {name, example, description}")
    notification_type: NotificationType = Field(default=NotificationType.INFO, description="Notification type")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Notification priority")
    is_active: bool = Field(default=True, description="Whether template is active")

    @field_validator('template_code')
    @classmethod
    def validate_template_code(cls, v: str) -> str:
        """Validate template code format"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Template code must contain only alphanumeric characters, hyphens, and underscores')
        return v.lower()

    @field_validator('variables')
    @classmethod
    def validate_variables(cls, v: List[Any]) -> List[Any]:
        """Validate variable entries (str or dict with 'name' key)"""
        for var in v:
            if isinstance(var, str):
                if not var.replace('_', '').isalnum():
                    raise ValueError(f'Variable name "{var}" must contain only alphanumeric characters and underscores')
            elif isinstance(var, dict):
                if 'name' not in var:
                    raise ValueError(f"Variable dict must have a 'name' key: {var}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "template_code": "payment_confirmation",
                "name_es": "Confirmación de Pago",
                "name_fr": "Confirmation de Paiement",
                "name_en": "Payment Confirmation",
                "title_es": "Pago recibido correctamente",
                "title_fr": "Paiement reçu avec succès",
                "title_en": "Payment received successfully",
                "body_es": "Hemos recibido su pago de {{amount}} para {{service_name}}",
                "body_fr": "Nous avons reçu votre paiement de {{amount}} pour {{service_name}}",
                "body_en": "We have received your payment of {{amount}} for {{service_name}}",
                "icon": "CheckCircle",
                "action_url": "/dashboard/payments/{{payment_id}}",
                "variables": ["amount", "service_name", "payment_id"],
                "notification_type": "success",
                "priority": "normal",
                "is_active": True
            }
        }


class NotificationTemplateUpdate(BaseModel):
    """Model for updating a notification template"""
    name_es: Optional[str] = Field(None, max_length=255)
    name_fr: Optional[str] = Field(None, max_length=255)
    name_en: Optional[str] = Field(None, max_length=255)

    title_es: Optional[str] = Field(None, max_length=255)
    title_fr: Optional[str] = Field(None, max_length=255)
    title_en: Optional[str] = Field(None, max_length=255)

    body_es: Optional[str] = Field(None)
    body_fr: Optional[str] = Field(None)
    body_en: Optional[str] = Field(None)

    icon: Optional[str] = Field(None, max_length=100)
    action_url: Optional[str] = Field(None, max_length=500)
    variables: Optional[List[Any]] = Field(None)
    notification_type: Optional[NotificationType] = Field(None)
    priority: Optional[NotificationPriority] = Field(None)
    is_active: Optional[bool] = Field(None)

    @field_validator('variables')
    @classmethod
    def validate_variables(cls, v: Optional[List[Any]]) -> Optional[List[Any]]:
        """Validate variable entries"""
        if v is not None:
            for var in v:
                if isinstance(var, str) and not var.replace('_', '').isalnum():
                    raise ValueError(f'Variable name "{var}" must contain only alphanumeric characters and underscores')
                elif isinstance(var, dict) and 'name' not in var:
                    raise ValueError(f"Variable dict must have a 'name' key: {var}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "title_es": "Pago procesado exitosamente",
                "body_es": "Su pago de {{amount}} ha sido procesado",
                "is_active": True
            }
        }


class NotificationTemplateResponse(BaseModel):
    """Model for notification template response"""
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

    icon: Optional[str]
    action_url: Optional[str]
    variables: List[Any]
    notification_type: NotificationType
    priority: NotificationPriority
    is_active: bool

    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "template_code": "payment_confirmation",
                "name_es": "Confirmación de Pago",
                "name_fr": "Confirmation de Paiement",
                "name_en": "Payment Confirmation",
                "title_es": "Pago recibido correctamente",
                "title_fr": "Paiement reçu avec succès",
                "title_en": "Payment received successfully",
                "body_es": "Hemos recibido su pago de {{amount}} para {{service_name}}",
                "body_fr": "Nous avons reçu votre paiement de {{amount}} pour {{service_name}}",
                "body_en": "We have received your payment of {{amount}} for {{service_name}}",
                "icon": "CheckCircle",
                "action_url": "/dashboard/payments/{{payment_id}}",
                "variables": ["amount", "service_name", "payment_id"],
                "notification_type": "success",
                "priority": "normal",
                "is_active": True,
                "created_at": "2025-12-12T10:00:00Z",
                "updated_at": "2025-12-12T10:00:00Z",
                "created_by": 1
            }
        }


class NotificationTemplateListResponse(BaseModel):
    """Model for paginated notification template list response"""
    templates: List[NotificationTemplateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "templates": [],
                "total": 50,
                "page": 1,
                "page_size": 20,
                "total_pages": 3
            }
        }


class NotificationPreviewRequest(BaseModel):
    """Model for previewing a notification with variables"""
    template_id: int = Field(..., description="Template ID to preview")
    language: str = Field("es", pattern="^(es|fr|en)$", description="Language for preview")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variable values for preview")

    class Config:
        json_schema_extra = {
            "example": {
                "template_id": 1,
                "language": "es",
                "variables": {
                    "amount": "5000 XAF",
                    "service_name": "Nota de Ingreso",
                    "payment_id": "PAY-12345"
                }
            }
        }


class NotificationPreviewResponse(BaseModel):
    """Model for notification preview response"""
    title: str
    body: str
    icon: Optional[str]
    action_url: Optional[str]
    notification_type: NotificationType
    priority: NotificationPriority

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Pago recibido correctamente",
                "body": "Hemos recibido su pago de 5000 XAF para Nota de Ingreso",
                "icon": "CheckCircle",
                "action_url": "/dashboard/payments/PAY-12345",
                "notification_type": "success",
                "priority": "normal"
            }
        }
