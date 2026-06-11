"""
Declaration Service for TaxasGE Backend
Business logic layer for tax declarations

Author: Claude Code
Date: 2025-11-22
"""

from typing import Optional
from datetime import datetime
from loguru import logger
import asyncpg

from app.modules.declarations.repositories.declaration_repository import DeclarationRepository
from app.modules.declarations.models.declaration import (
    DeclarationWorkflowStatus,
    WorkflowStage,
    DeclarationStatus,
)


class DeclarationService:
    """
    Service for tax declaration business logic

    **Architecture**: 3-tier (Routes → Services → Repositories)
    **Responsibility**: Business rules, workflow logic, orchestration
    """

    def __init__(self, repository: Optional[DeclarationRepository] = None):
        """
        Initialize declaration service

        Args:
            repository: Optional declaration repository (for testing/DI)
        """
        self.repository = repository or DeclarationRepository()
        logger.info("DeclarationService initialized")

    async def get_workflow_status(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
    ) -> Optional[DeclarationWorkflowStatus]:
        """
        Get workflow status for a declaration with business logic

        **Business Logic**:
        - Determines current stage based on declaration status
        - Calculates completion for each workflow stage
        - Provides available actions based on current state

        **Workflow Stages**:
        1. Draft → User is editing
        2. Submitted → Waiting for agent assignment
        3. Processing → Agent is reviewing
        4. Accepted/Rejected → Final decision made

        Args:
            conn: Database connection
            declaration_id: Declaration UUID

        Returns:
            DeclarationWorkflowStatus: Workflow status with stages and next actions

        Raises:
            ValueError: If declaration not found
        """
        try:
            # Get declaration from repository
            declaration = await self.repository.get_by_id(conn, declaration_id)

            if not declaration:
                raise ValueError(f"Declaration {declaration_id} not found")

            # Extract status and timestamps
            status = DeclarationStatus(declaration["status"])
            submitted_at = declaration.get("submitted_at")
            processed_at = declaration.get("processed_at")
            processed_by = declaration.get("processed_by")

            # Determine current stage
            if status == DeclarationStatus.DRAFT:
                current_stage = "draft"
            elif status == DeclarationStatus.SUBMITTED:
                current_stage = "submitted"
            elif status == DeclarationStatus.PROCESSING:
                current_stage = "processing"
            elif status == DeclarationStatus.ACCEPTED:
                current_stage = "accepted"
            elif status == DeclarationStatus.REJECTED:
                current_stage = "rejected"
            elif status == DeclarationStatus.AMENDED:
                current_stage = "amended"
            else:
                current_stage = "unknown"

            # Define workflow stages with completion status
            stages = [
                WorkflowStage(
                    stage="draft",
                    name="Brouillon",
                    completed=(status != DeclarationStatus.DRAFT)
                ),
                WorkflowStage(
                    stage="submitted",
                    name="Soumise",
                    completed=(submitted_at is not None)
                ),
                WorkflowStage(
                    stage="processing",
                    name="En traitement",
                    completed=(
                        status in [
                            DeclarationStatus.PROCESSING,
                            DeclarationStatus.ACCEPTED,
                            DeclarationStatus.REJECTED
                        ]
                    )
                ),
                WorkflowStage(
                    stage="completed",
                    name="Finalisée",
                    completed=(
                        status in [DeclarationStatus.ACCEPTED, DeclarationStatus.REJECTED]
                        and processed_at is not None
                    )
                ),
            ]

            # Determine next actions based on current status
            next_actions = self._get_next_actions(status, processed_by)

            # Build workflow status
            workflow_status = DeclarationWorkflowStatus(
                declaration_id=declaration_id,
                current_stage=current_stage,
                stages=stages,
                next_actions=next_actions,
                status=status,
                submitted_at=submitted_at,
                processed_at=processed_at,
                processed_by=processed_by,
            )

            logger.debug(f"Workflow status calculated for declaration {declaration_id}: {current_stage}")
            return workflow_status

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error getting workflow status for declaration {declaration_id}: {str(e)}")
            raise

    def _get_next_actions(
        self,
        status: DeclarationStatus,
        processed_by: Optional[str],
    ) -> list[str]:
        """
        Determine available next actions based on declaration status

        **Business Rules**:
        - DRAFT: Can submit, edit, delete
        - SUBMITTED: Can assign to agent, cancel
        - PROCESSING: Can approve, reject, request more info
        - ACCEPTED/REJECTED: Can create amended declaration

        Args:
            status: Current declaration status
            processed_by: Processor UUID (if assigned)

        Returns:
            List of available action identifiers
        """
        if status == DeclarationStatus.DRAFT:
            return ["submit", "edit", "delete"]

        elif status == DeclarationStatus.SUBMITTED:
            if processed_by:
                # Already assigned
                return ["approve", "reject", "request_documents"]
            else:
                # Not yet assigned
                return ["assign_agent", "cancel"]

        elif status == DeclarationStatus.PROCESSING:
            return ["approve", "reject", "request_documents", "reassign"]

        elif status == DeclarationStatus.ACCEPTED:
            return ["create_amendment", "view_receipt"]

        elif status == DeclarationStatus.REJECTED:
            return ["create_amendment", "appeal"]

        elif status == DeclarationStatus.AMENDED:
            return ["view_history"]

        else:
            return []


# Singleton instance
_declaration_service_instance: Optional[DeclarationService] = None


def get_declaration_service() -> DeclarationService:
    """
    Get declaration service singleton instance

    Returns:
        DeclarationService: Declaration service instance
    """
    global _declaration_service_instance

    if _declaration_service_instance is None:
        _declaration_service_instance = DeclarationService()

    return _declaration_service_instance
