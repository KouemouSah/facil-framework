"""
Support Module Models

Exports all support-related Pydantic models
"""

from app.modules.support.models.support import (
    # Enums
    TicketPriority,
    TicketStatus,
    TargetRole,
    # Category models
    SupportCategoryCreate,
    SupportCategoryUpdate,
    SupportCategoryResponse,
    # Ticket models
    SupportTicketCreate,
    SupportTicketUpdate,
    SupportTicketResponse,
    SupportTicketListResponse,
    # Message models
    SupportMessageCreate,
    SupportMessageResponse,
    # Attachment models
    SupportAttachmentCreate,
    SupportAttachmentResponse,
    # Stats models
    SupportStatsResponse,
)

__all__ = [
    # Enums
    "TicketPriority",
    "TicketStatus",
    "TargetRole",
    # Category models
    "SupportCategoryCreate",
    "SupportCategoryUpdate",
    "SupportCategoryResponse",
    # Ticket models
    "SupportTicketCreate",
    "SupportTicketUpdate",
    "SupportTicketResponse",
    "SupportTicketListResponse",
    # Message models
    "SupportMessageCreate",
    "SupportMessageResponse",
    # Attachment models
    "SupportAttachmentCreate",
    "SupportAttachmentResponse",
    # Stats models
    "SupportStatsResponse",
]
