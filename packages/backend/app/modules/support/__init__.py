"""
Support Module

A complete support ticketing system for:
- Users to request help and report issues
- Agents to request technical support from administration
- Admins to manage and respond to support tickets

Components:
- Categories: Organize tickets by type (technical, billing, general, etc.)
- Tickets: Main support requests with lifecycle management
- Messages: Conversation thread within tickets
- Attachments: File uploads (future feature)
"""

from app.modules.support.api import router
from app.modules.support.models import (
    TicketPriority,
    TicketStatus,
    TargetRole,
    SupportCategoryCreate,
    SupportCategoryUpdate,
    SupportCategoryResponse,
    SupportTicketCreate,
    SupportTicketUpdate,
    SupportTicketResponse,
    SupportTicketListResponse,
    SupportMessageCreate,
    SupportMessageResponse,
    SupportStatsResponse,
)
from app.modules.support.services import SupportService
from app.modules.support.repositories import SupportRepository

__all__ = [
    # Router
    "router",
    # Enums
    "TicketPriority",
    "TicketStatus",
    "TargetRole",
    # Models
    "SupportCategoryCreate",
    "SupportCategoryUpdate",
    "SupportCategoryResponse",
    "SupportTicketCreate",
    "SupportTicketUpdate",
    "SupportTicketResponse",
    "SupportTicketListResponse",
    "SupportMessageCreate",
    "SupportMessageResponse",
    "SupportStatsResponse",
    # Services
    "SupportService",
    # Repositories
    "SupportRepository",
]
