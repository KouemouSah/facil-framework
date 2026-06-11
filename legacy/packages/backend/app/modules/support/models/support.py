"""
Support Module Models

Pydantic models for support ticket management
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class TicketPriority(str, Enum):
    """Ticket priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, Enum):
    """Ticket status enumeration"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TargetRole(str, Enum):
    """Target role for support categories"""
    ADMIN = "admin"
    AGENT = "agent"
    ALL = "all"


# ===========================================================================
# SUPPORT CATEGORY MODELS
# ===========================================================================

class SupportCategoryCreate(BaseModel):
    """Model for creating a support category"""
    code: str = Field(..., min_length=1, max_length=50, description="Unique category code")
    name_es: str = Field(..., min_length=1, max_length=255, description="Category name (Spanish)")
    name_fr: Optional[str] = Field(None, max_length=255, description="Category name (French)")
    name_en: Optional[str] = Field(None, max_length=255, description="Category name (English)")
    description_es: Optional[str] = Field(None, description="Category description (Spanish)")
    description_fr: Optional[str] = Field(None, description="Category description (French)")
    description_en: Optional[str] = Field(None, description="Category description (English)")
    target_role: TargetRole = Field(default=TargetRole.ADMIN, description="Target role for this category")
    icon: Optional[str] = Field(None, max_length=100, description="Lucide icon name")
    is_active: bool = Field(default=True, description="Whether category is active")
    sort_order: int = Field(default=0, description="Display order")

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate category code format"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Category code must contain only alphanumeric characters, hyphens, and underscores')
        return v.lower()

    class Config:
        json_schema_extra = {
            "example": {
                "code": "technical_issue",
                "name_es": "Problema técnico",
                "name_fr": "Problème technique",
                "name_en": "Technical issue",
                "description_es": "Problemas con la plataforma",
                "target_role": "admin",
                "icon": "Wrench",
                "is_active": True,
                "sort_order": 1
            }
        }


class SupportCategoryUpdate(BaseModel):
    """Model for updating a support category"""
    name_es: Optional[str] = Field(None, max_length=255)
    name_fr: Optional[str] = Field(None, max_length=255)
    name_en: Optional[str] = Field(None, max_length=255)
    description_es: Optional[str] = Field(None)
    description_fr: Optional[str] = Field(None)
    description_en: Optional[str] = Field(None)
    target_role: Optional[TargetRole] = Field(None)
    icon: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = Field(None)
    sort_order: Optional[int] = Field(None)


class SupportCategoryResponse(BaseModel):
    """Model for support category response"""
    id: int
    code: str
    name_es: str
    name_fr: Optional[str]
    name_en: Optional[str]
    description_es: Optional[str]
    description_fr: Optional[str]
    description_en: Optional[str]
    target_role: TargetRole
    icon: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===========================================================================
# SUPPORT TICKET MODELS
# ===========================================================================

class SupportTicketCreate(BaseModel):
    """Model for creating a support ticket"""
    category_id: int = Field(..., description="Category ID")
    subject: str = Field(..., min_length=5, max_length=255, description="Ticket subject")
    description: str = Field(..., min_length=10, description="Detailed description of the issue")
    priority: TicketPriority = Field(default=TicketPriority.NORMAL, description="Ticket priority")

    class Config:
        json_schema_extra = {
            "example": {
                "category_id": 1,
                "subject": "Unable to submit declaration",
                "description": "When I try to submit my IVA declaration, I get an error message 'Server error'. This has been happening since yesterday.",
                "priority": "normal"
            }
        }


class SupportTicketUpdate(BaseModel):
    """Model for updating a support ticket (admin)"""
    category_id: Optional[int] = Field(None)
    subject: Optional[str] = Field(None, max_length=255)
    priority: Optional[TicketPriority] = Field(None)
    status: Optional[TicketStatus] = Field(None)
    assigned_to: Optional[UUID] = Field(None, description="User ID to assign ticket to")


class SupportTicketResponse(BaseModel):
    """Model for support ticket response"""
    id: int
    ticket_number: str
    category_id: Optional[int] = None  # Database allows NULL
    category_name: Optional[str] = None
    subject: str
    description: str
    priority: TicketPriority = TicketPriority.NORMAL  # Default to normal
    status: TicketStatus = TicketStatus.OPEN  # Default to open
    created_by: UUID
    created_by_name: Optional[str] = None
    assigned_to: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None  # Database allows NULL
    message_count: int = 0

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "ticket_number": "SUP-20251217-0001",
                "category_id": 1,
                "category_name": "Problema técnico",
                "subject": "Unable to submit declaration",
                "description": "When I try to submit...",
                "priority": "normal",
                "status": "open",
                "created_by": 1,
                "created_by_name": "Juan Pérez",
                "assigned_to": 5,
                "assigned_to_name": "Admin User",
                "resolved_at": None,
                "closed_at": None,
                "created_at": "2025-12-17T10:00:00Z",
                "updated_at": "2025-12-17T10:00:00Z",
                "message_count": 3
            }
        }


class SupportTicketListResponse(BaseModel):
    """Model for paginated ticket list response"""
    tickets: List[SupportTicketResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "tickets": [],
                "total": 50,
                "page": 1,
                "page_size": 20,
                "total_pages": 3
            }
        }


# ===========================================================================
# SUPPORT MESSAGE MODELS
# ===========================================================================

class SupportMessageCreate(BaseModel):
    """Model for creating a support message"""
    content: str = Field(..., min_length=1, description="Message content")
    is_internal: bool = Field(default=False, description="Internal admin note (not visible to user)")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Thank you for contacting support. We are investigating your issue.",
                "is_internal": False
            }
        }


class SupportMessageResponse(BaseModel):
    """Model for support message response"""
    id: int
    ticket_id: int
    sender_id: UUID
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    content: str
    is_internal: bool
    created_at: datetime
    attachments: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ===========================================================================
# SUPPORT ATTACHMENT MODELS
# ===========================================================================

class SupportAttachmentCreate(BaseModel):
    """Model for creating a support attachment"""
    file_name: str = Field(..., max_length=255, description="Original file name")
    file_path: str = Field(..., max_length=500, description="Storage path")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, max_length=100, description="MIME type")


class SupportAttachmentResponse(BaseModel):
    """Model for support attachment response"""
    id: int
    message_id: int
    file_name: str
    file_path: str
    file_size: Optional[int]
    mime_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ===========================================================================
# STATISTICS MODELS
# ===========================================================================

class SupportStatsResponse(BaseModel):
    """Model for support statistics response"""
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    tickets_by_priority: Dict[str, int]
    tickets_by_category: Dict[str, int]
    average_resolution_time_hours: Optional[float]

    class Config:
        json_schema_extra = {
            "example": {
                "total_tickets": 150,
                "open_tickets": 25,
                "in_progress_tickets": 15,
                "resolved_tickets": 80,
                "closed_tickets": 30,
                "tickets_by_priority": {
                    "low": 20,
                    "normal": 100,
                    "high": 25,
                    "urgent": 5
                },
                "tickets_by_category": {
                    "technical_issue": 50,
                    "payment_issue": 40,
                    "general_inquiry": 60
                },
                "average_resolution_time_hours": 24.5
            }
        }
