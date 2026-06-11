"""
Auto Assignment Service - DEPRECATED & COMMENTED OUT

SUPERSEDED BY: app.modules.assignment.services.auto_assignment_service
which uses entity_code routing (migration 131) instead of ministry_id.

All active callers (agent_queue_handler, payment_assignment_handler,
service_request_service, outbox_service) import from the assignment module.

DO NOT USE THIS MODULE FOR NEW CODE.
Import from app.modules.assignment.services instead.

The auto_assign() method below used ministry_id for routing.
The modern equivalent uses entity_code + entity_location_id (site-based).
"""

# ============================================================================
# COMMENTED OUT — Original legacy code preserved for reference
# ============================================================================

# from typing import Optional, List
# from uuid import UUID
# from fastapi import Depends
# from loguru import logger
#
# from app.modules.agents.models import Assignment, AssignmentCreate
# from app.modules.agents.repositories import (
#     AssignmentRepository,
#     WorkloadRepository,
# )
# from app.modules.agents.services.rules_engine import (
#     RulesEngine,
#     get_rules_engine,
# )
#
#
# class AutoAssignmentService:
#     """Service for automatic assignment operations.
#
#     DEPRECATED: Uses ministry_id routing (broken since entity migration).
#     Modern equivalent: app.modules.assignment.services.auto_assignment_service
#     which uses entity_code + entity_location_id for site-based routing.
#     """
#
#     def __init__(
#         self,
#         assignment_repository: Optional[AssignmentRepository] = None,
#         workload_repository: Optional[WorkloadRepository] = None,
#         rules_engine: Optional[RulesEngine] = None
#     ):
#         self.assignment_repository = assignment_repository or AssignmentRepository()
#         self.workload_repository = workload_repository or WorkloadRepository()
#         self.rules_engine = rules_engine or RulesEngine()
#         logger.info("AutoAssignmentService initialized")
#
#     async def auto_assign(
#         self,
#         db,
#         item_id: UUID,
#         item_type: str,
#         ministry_id: int,
#         priority: int = 5
#     ) -> Optional[Assignment]:
#         """Automatically assign an item to an agent profile.
#
#         DEPRECATED: Routes via ministry_id which is now nullable and
#         doesn't match the entity_code routing used by service_requests.
#
#         Modern equivalent: assignment.services.auto_assignment_service.auto_assign_item()
#         which routes via entity_code + entity_location_id.
#
#         Args:
#             item_id: UUID of the item
#             item_type: Type of item (declaration type or workflow_code)
#             ministry_id: Ministry ID for agent selection (DEPRECATED)
#             priority: Priority level (1-10)
#         """
#         # Get best agent_profile_id based on rules
#         agent_profile_id = await self.rules_engine.select_agent(
#             db, item_type, priority, ministry_id
#         )
#
#         if not agent_profile_id:
#             logger.warning(f"No available agent for {item_type} {item_id} in ministry {ministry_id}")
#             return None
#
#         # Create assignment
#         assignment_data = AssignmentCreate(
#             item_id=str(item_id),
#             item_type=item_type,
#             agent_profile_id=str(agent_profile_id),
#         )
#
#         return await self.assignment_repository.create_assignment(db, assignment_data)
#
#     async def rebalance_assignments(self, db) -> int:
#         """Rebalance workload across agents.
#
#         NOTE: Modern equivalent in assignment module also has this as a stub.
#         Neither implementation is functional.
#         """
#         logger.info("Rebalancing assignments across agents")
#         return 0
#
#
# # Singleton instance
# auto_assignment_service = AutoAssignmentService()
#
#
# def get_auto_assignment_service() -> AutoAssignmentService:
#     """Get singleton AutoAssignmentService instance"""
#     return auto_assignment_service
