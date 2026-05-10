"""Agent services

NOTE: AssignmentService and AutoAssignmentService are DEPRECATED in this module.
Use app.modules.assignment.services instead (entity_code routing, migration 131).
The legacy code is COMMENTED OUT in the source files (not deleted).
"""

from app.modules.agents.services.agent_service import AgentService
from app.modules.agents.services.workload_service import WorkloadService

# DEPRECATED: AssignmentService is commented out in assignment_service.py
# DEPRECATED: AutoAssignmentService is commented out in auto_assignment_service.py
# Import from app.modules.assignment.services instead.

__all__ = ["AgentService", "WorkloadService"]
