"""
Support API Routes - FastAPI endpoints for support ticketing system

Endpoints:
Categories:
- GET    /support/categories - List categories
- GET    /support/categories/{id} - Get category
- POST   /support/categories - Create category (admin)
- PUT    /support/categories/{id} - Update category (admin)
- DELETE /support/categories/{id} - Delete category (admin)

Tickets:
- GET    /support/tickets - List all tickets (admin)
- GET    /support/tickets/my - List user's tickets
- GET    /support/tickets/{id} - Get ticket detail
- POST   /support/tickets - Create ticket
- PUT    /support/tickets/{id} - Update ticket
- POST   /support/tickets/{id}/close - Close ticket

Messages:
- GET    /support/tickets/{id}/messages - List messages
- POST   /support/tickets/{id}/messages - Add message

Stats:
- GET    /support/stats - Get statistics (admin)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from uuid import UUID
import asyncpg
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import permission_required
from ..models.support import (
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
from ..services.support_service import SupportService

router = APIRouter(prefix="/support", tags=["Support"])
service = SupportService()


# =============================================================================
# CATEGORY ENDPOINTS
# =============================================================================


@router.get("/categories", response_model=list[SupportCategoryResponse])
async def list_categories(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    target_role: Optional[str] = Query(None, description="Filter by target role (admin, agent, all)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    List support categories

    - **is_active**: Optional filter for active/inactive categories
    - **target_role**: Optional filter for target role
    """
    return await service.list_categories(db, is_active=is_active, target_role=target_role)


@router.get("/categories/{category_id}", response_model=SupportCategoryResponse)
async def get_category(
    category_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get a support category by ID

    - **category_id**: Category ID
    """
    return await service.get_category(db, category_id)


@router.post(
    "/categories",
    response_model=SupportCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    category_data: SupportCategoryCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("support.manage")),
):
    """
    Create a new support category

    Requires permission: support.manage

    - **code**: Unique category code
    - **name_es**: Category name in Spanish (required)
    - **target_role**: Target role (admin, agent, all)
    """
    try:
        category = await service.create_category(db, category_data)
        logger.info(f"Support category created: {category.code} by user {current_user.id}")
        return category
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create support category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create support category",
        )


@router.put("/categories/{category_id}", response_model=SupportCategoryResponse)
async def update_category(
    category_id: int,
    category_data: SupportCategoryUpdate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("support.manage")),
):
    """
    Update a support category

    Requires permission: support.manage

    - **category_id**: Category ID to update
    """
    try:
        category = await service.update_category(db, category_id, category_data)
        logger.info(f"Support category updated: {category_id} by user {current_user.id}")
        return category
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update support category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update support category",
        )


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("support.manage")),
):
    """
    Delete a support category

    Requires permission: support.manage

    - **category_id**: Category ID to delete
    """
    try:
        await service.delete_category(db, category_id)
        logger.info(f"Support category deleted: {category_id} by user {current_user.id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete support category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete support category",
        )


# =============================================================================
# TICKET ENDPOINTS
# =============================================================================


@router.get("/tickets", response_model=SupportTicketListResponse)
async def list_all_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    ticket_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    assigned_to: Optional[UUID] = Query(None, description="Filter by assigned agent"),
    search: Optional[str] = Query(None, description="Search in ticket number, subject, description"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("support.view_all")),
):
    """
    List all support tickets (admin view)

    Requires permission: support.view_all

    - **status**: Filter by ticket status
    - **priority**: Filter by priority
    - **category_id**: Filter by category
    - **assigned_to**: Filter by assigned agent
    - **search**: Search in ticket number, subject, description
    """
    logger.info(f"list_all_tickets called by user {current_user.id} (role: {current_user.role})")

    try:
        tickets, total, total_pages = await service.list_tickets(
            db,
            page=page,
            page_size=page_size,
            status=ticket_status,
            priority=priority,
            category_id=category_id,
            assigned_to=assigned_to,
            search=search,
        )

        logger.info(f"Returning {len(tickets)} tickets (total: {total})")

        return SupportTicketListResponse(
            tickets=tickets,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Error in list_all_tickets: {e}")
        raise


@router.get("/tickets/my", response_model=SupportTicketListResponse)
async def list_my_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    ticket_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    List current user's support tickets

    - **status**: Filter by ticket status
    """
    tickets, total, total_pages = await service.list_my_tickets(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=ticket_status,
    )

    return SupportTicketListResponse(
        tickets=tickets,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def get_ticket(
    ticket_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get a support ticket by ID

    Users can only view their own tickets. Admins can view all tickets.

    - **ticket_id**: Ticket ID
    """
    is_admin = await _check_support_admin(db, current_user)
    return await service.get_ticket(
        db,
        ticket_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )


@router.get("/tickets/by-number/{ticket_number}", response_model=SupportTicketResponse)
async def get_ticket_by_number(
    ticket_number: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get a support ticket by ticket number

    - **ticket_number**: Ticket number (e.g., SUP-20251217-0001)
    """
    is_admin = await _check_support_admin(db, current_user)
    return await service.get_ticket_by_number(
        db,
        ticket_number,
        user_id=current_user.id,
        is_admin=is_admin,
    )


@router.post(
    "/tickets",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    ticket_data: SupportTicketCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Create a new support ticket

    - **category_id**: Support category ID
    - **subject**: Ticket subject
    - **description**: Detailed description
    - **priority**: Priority level (low, normal, high, urgent)
    """
    try:
        ticket = await service.create_ticket(db, ticket_data, current_user.id)
        logger.info(f"Support ticket created: {ticket.ticket_number} by user {current_user.id}")
        return ticket
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create support ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create support ticket",
        )


@router.put("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def update_ticket(
    ticket_id: int,
    ticket_data: SupportTicketUpdate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Update a support ticket

    Users can update subject of their own tickets.
    Admins can update all fields (status, priority, assigned_to).

    - **ticket_id**: Ticket ID to update
    """
    try:
        is_admin = await _check_support_admin(db, current_user)
        ticket = await service.update_ticket(
            db,
            ticket_id,
            ticket_data,
            current_user.id,
            is_admin=is_admin,
        )
        logger.info(f"Support ticket updated: {ticket_id} by user {current_user.id}")
        return ticket
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update support ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update support ticket",
        )


@router.post("/tickets/{ticket_id}/close", response_model=SupportTicketResponse)
async def close_ticket(
    ticket_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Close a support ticket

    Users can close their own resolved/pending tickets.
    Admins can close any ticket.

    - **ticket_id**: Ticket ID to close
    """
    try:
        is_admin = await _check_support_admin(db, current_user)
        ticket = await service.close_ticket(
            db,
            ticket_id,
            current_user.id,
            is_admin=is_admin,
        )
        logger.info(f"Support ticket closed: {ticket_id} by user {current_user.id}")
        return ticket
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close support ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to close support ticket",
        )


# =============================================================================
# MESSAGE ENDPOINTS
# =============================================================================


@router.get("/tickets/{ticket_id}/messages", response_model=list[SupportMessageResponse])
async def list_messages(
    ticket_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    List all messages for a ticket

    Users can only view messages for their own tickets.
    Admins can view all messages including internal notes.

    - **ticket_id**: Ticket ID
    """
    is_admin = await _check_support_admin(db, current_user)
    return await service.list_messages(
        db,
        ticket_id,
        current_user.id,
        is_admin=is_admin,
    )


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=SupportMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    ticket_id: int,
    message_data: SupportMessageCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Add a message to a ticket

    Users can add messages to their own tickets.
    Admins can add messages and internal notes to any ticket.

    - **ticket_id**: Ticket ID
    - **content**: Message content
    - **is_internal**: Mark as internal note (admin only)
    """
    try:
        is_admin = await _check_support_admin(db, current_user)
        message = await service.add_message(
            db,
            ticket_id,
            message_data,
            current_user.id,
            is_admin=is_admin,
        )
        logger.info(f"Message added to ticket {ticket_id} by user {current_user.id}")
        return message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add message to ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add message",
        )


# =============================================================================
# STATISTICS ENDPOINTS
# =============================================================================


@router.get("/stats", response_model=SupportStatsResponse)
async def get_stats(
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("support.view_all")),
):
    """
    Get support statistics

    Requires permission: support.view_all

    Returns counts by status, priority, category and average resolution time.
    """
    return await service.get_stats(db)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def _check_support_admin(db: asyncpg.Connection, current_user: UserResponse) -> bool:
    """Check if user has support admin permissions"""
    # Check if user has support.view_all or support.manage permission
    # For simplicity, check if role is admin or if they have the permission
    user_role = current_user.role or ""
    if user_role in ["admin", "superadmin"]:
        return True

    # Additional permission check could be added here
    # For now, check against a simple role-based approach
    return False
