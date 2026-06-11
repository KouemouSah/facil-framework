"""
Support Service

Business logic for support module
"""

import asyncpg
from typing import Optional, List, Tuple
from uuid import UUID
from fastapi import HTTPException, status
from loguru import logger

from app.modules.support.repositories.support_repository import SupportRepository
from app.modules.support.models.support import (
    SupportCategoryCreate,
    SupportCategoryUpdate,
    SupportCategoryResponse,
    SupportTicketCreate,
    SupportTicketUpdate,
    SupportTicketResponse,
    SupportMessageCreate,
    SupportMessageResponse,
    SupportStatsResponse,
    TicketStatus,
)


class SupportService:
    """
    Service for support module business logic.

    Orchestrates:
    - Category management (admin)
    - Ticket lifecycle
    - Message handling
    - Permission checks
    """

    def __init__(self):
        self.repository = SupportRepository()

    # ===========================================================================
    # CATEGORY OPERATIONS
    # ===========================================================================

    async def create_category(
        self,
        db: asyncpg.Connection,
        data: SupportCategoryCreate
    ) -> SupportCategoryResponse:
        """Create a new support category"""
        # Check if code already exists
        existing = await self.repository.get_category_by_code(db, data.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with code '{data.code}' already exists"
            )

        category = await self.repository.create_category(
            db,
            code=data.code,
            name_es=data.name_es,
            name_fr=data.name_fr,
            name_en=data.name_en,
            description_es=data.description_es,
            description_fr=data.description_fr,
            description_en=data.description_en,
            target_role=data.target_role.value,
            icon=data.icon,
            is_active=data.is_active,
            sort_order=data.sort_order
        )

        logger.info(f"Support category created: {data.code}")
        return SupportCategoryResponse(**category)

    async def get_category(
        self,
        db: asyncpg.Connection,
        category_id: int
    ) -> SupportCategoryResponse:
        """Get category by ID"""
        category = await self.repository.get_category_by_id(db, category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )
        return SupportCategoryResponse(**category)

    async def list_categories(
        self,
        db: asyncpg.Connection,
        is_active: Optional[bool] = None,
        target_role: Optional[str] = None
    ) -> List[SupportCategoryResponse]:
        """List all categories with optional filters"""
        categories = await self.repository.list_categories(
            db, is_active=is_active, target_role=target_role
        )
        return [SupportCategoryResponse(**c) for c in categories]

    async def update_category(
        self,
        db: asyncpg.Connection,
        category_id: int,
        data: SupportCategoryUpdate
    ) -> SupportCategoryResponse:
        """Update a category"""
        # Ensure category exists
        existing = await self.repository.get_category_by_id(db, category_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )

        updates = {}
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                if field == 'target_role':
                    updates[field] = value.value
                else:
                    updates[field] = value

        category = await self.repository.update_category(db, category_id, updates)
        logger.info(f"Support category updated: {category_id}")
        return SupportCategoryResponse(**category)

    async def delete_category(
        self,
        db: asyncpg.Connection,
        category_id: int
    ) -> bool:
        """Delete a category"""
        existing = await self.repository.get_category_by_id(db, category_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )

        result = await self.repository.delete_category(db, category_id)
        logger.info(f"Support category deleted: {category_id}")
        return result

    # ===========================================================================
    # TICKET OPERATIONS
    # ===========================================================================

    async def create_ticket(
        self,
        db: asyncpg.Connection,
        data: SupportTicketCreate,
        user_id: UUID
    ) -> SupportTicketResponse:
        """Create a new support ticket"""
        # Validate category exists
        category = await self.repository.get_category_by_id(db, data.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with ID {data.category_id} not found"
            )

        # Generate ticket number
        ticket_number = await self.repository.generate_ticket_number(db)

        # Create ticket
        ticket = await self.repository.create_ticket(
            db,
            ticket_number=ticket_number,
            category_id=data.category_id,
            subject=data.subject,
            description=data.description,
            priority=data.priority.value,
            created_by=user_id
        )

        # Create initial message with description
        await self.repository.create_message(
            db,
            ticket_id=ticket['id'],
            sender_id=user_id,
            content=data.description,
            is_internal=False
        )

        # Fetch full ticket with joins
        full_ticket = await self.repository.get_ticket_by_id(db, ticket['id'])

        logger.info(f"Support ticket created: {ticket_number} by user {user_id}")
        return SupportTicketResponse(**full_ticket)

    async def get_ticket(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        user_id: Optional[UUID] = None,
        is_admin: bool = False
    ) -> SupportTicketResponse:
        """Get ticket by ID with permission check"""
        ticket = await self.repository.get_ticket_by_id(db, ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found"
            )

        # Permission check: users can only see their own tickets
        # Convert both to string for comparison (user_id may be str from UserResponse.id)
        if not is_admin and user_id and str(ticket['created_by']) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this ticket"
            )

        return SupportTicketResponse(**ticket)

    async def get_ticket_by_number(
        self,
        db: asyncpg.Connection,
        ticket_number: str,
        user_id: Optional[UUID] = None,
        is_admin: bool = False
    ) -> SupportTicketResponse:
        """Get ticket by ticket number"""
        ticket = await self.repository.get_ticket_by_number(db, ticket_number)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_number} not found"
            )

        # Permission check
        # Convert both to string for comparison (user_id may be str from UserResponse.id)
        if not is_admin and user_id and str(ticket['created_by']) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this ticket"
            )

        return SupportTicketResponse(**ticket)

    async def list_tickets(
        self,
        db: asyncpg.Connection,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category_id: Optional[int] = None,
        created_by: Optional[UUID] = None,
        assigned_to: Optional[UUID] = None,
        search: Optional[str] = None
    ) -> Tuple[List[SupportTicketResponse], int, int]:
        """List tickets with pagination and filters"""
        logger.debug(f"list_tickets called: page={page}, page_size={page_size}, status={status}, priority={priority}")

        tickets, total = await self.repository.list_tickets(
            db,
            page=page,
            page_size=page_size,
            status=status,
            priority=priority,
            category_id=category_id,
            created_by=created_by,
            assigned_to=assigned_to,
            search=search
        )

        logger.debug(f"Repository returned {len(tickets)} tickets, total={total}")

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        # Convert to response models with error handling
        response_tickets = []
        for t in tickets:
            try:
                response_tickets.append(SupportTicketResponse(**t))
            except Exception as e:
                logger.error(f"Failed to convert ticket to response: {e}, data: {t}")
                raise

        return response_tickets, total, total_pages

    async def list_my_tickets(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[SupportTicketResponse], int, int]:
        """List tickets created by a specific user"""
        return await self.list_tickets(
            db,
            page=page,
            page_size=page_size,
            status=status,
            created_by=user_id
        )

    async def update_ticket(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        data: SupportTicketUpdate,
        user_id: UUID,
        is_admin: bool = False
    ) -> SupportTicketResponse:
        """Update a ticket"""
        ticket = await self.repository.get_ticket_by_id(db, ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found"
            )

        # Only admins can update all fields
        # Users can only update subject (limited)
        if not is_admin:
            # Convert both to string for comparison (user_id may be str from UserResponse.id)
            if str(ticket['created_by']) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to update this ticket"
                )
            # Users can only update subject
            data = SupportTicketUpdate(subject=data.subject)

        updates = {}
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                if field in ['priority', 'status']:
                    updates[field] = value.value
                else:
                    updates[field] = value

        updated_ticket = await self.repository.update_ticket(db, ticket_id, updates)

        logger.info(f"Support ticket updated: {ticket_id} by user {user_id}")
        return SupportTicketResponse(**await self.repository.get_ticket_by_id(db, ticket_id))

    async def close_ticket(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        user_id: UUID,
        is_admin: bool = False
    ) -> SupportTicketResponse:
        """Close a ticket"""
        ticket = await self.repository.get_ticket_by_id(db, ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found"
            )

        # Users can close their own resolved tickets
        if not is_admin:
            # Convert both to string for comparison (user_id may be str from UserResponse.id)
            if str(ticket['created_by']) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to close this ticket"
                )
            if ticket['status'] not in ['resolved', 'pending_user']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only resolved or pending tickets can be closed by users"
                )

        await self.repository.update_ticket(db, ticket_id, {'status': 'closed'})

        logger.info(f"Support ticket closed: {ticket_id} by user {user_id}")
        return SupportTicketResponse(**await self.repository.get_ticket_by_id(db, ticket_id))

    # ===========================================================================
    # MESSAGE OPERATIONS
    # ===========================================================================

    async def add_message(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        data: SupportMessageCreate,
        user_id: UUID,
        is_admin: bool = False
    ) -> SupportMessageResponse:
        """Add a message to a ticket"""
        ticket = await self.repository.get_ticket_by_id(db, ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found"
            )

        # Permission check
        # Convert both to string for comparison (user_id may be str from UserResponse.id)
        if not is_admin and str(ticket['created_by']) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to add messages to this ticket"
            )

        # Only admins can create internal messages
        if data.is_internal and not is_admin:
            data.is_internal = False

        # Ticket must not be closed
        if ticket['status'] == 'closed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add messages to a closed ticket"
            )

        message = await self.repository.create_message(
            db,
            ticket_id=ticket_id,
            sender_id=user_id,
            content=data.content,
            is_internal=data.is_internal
        )

        # Update ticket status based on who sent message
        if is_admin and ticket['status'] == 'open':
            await self.repository.update_ticket(db, ticket_id, {'status': 'in_progress'})
        elif not is_admin and ticket['status'] == 'pending_user':
            await self.repository.update_ticket(db, ticket_id, {'status': 'in_progress'})

        # Fetch full message with sender info
        full_message = await self.repository.get_message_by_id(db, message['id'])

        logger.info(f"Message added to ticket {ticket_id} by user {user_id}")
        return SupportMessageResponse(**full_message)

    async def list_messages(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        user_id: UUID,
        is_admin: bool = False
    ) -> List[SupportMessageResponse]:
        """List all messages for a ticket"""
        ticket = await self.repository.get_ticket_by_id(db, ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found"
            )

        # Permission check
        # Convert both to string for comparison (user_id may be str from UserResponse.id)
        if not is_admin and str(ticket['created_by']) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this ticket's messages"
            )

        # Only admins can see internal messages
        messages = await self.repository.list_messages(
            db, ticket_id, include_internal=is_admin
        )

        return [SupportMessageResponse(**m) for m in messages]

    # ===========================================================================
    # STATISTICS
    # ===========================================================================

    async def get_stats(self, db: asyncpg.Connection) -> SupportStatsResponse:
        """Get support statistics (admin only)"""
        stats = await self.repository.get_stats(db)
        return SupportStatsResponse(**stats)
