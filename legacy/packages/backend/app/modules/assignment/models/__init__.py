"""
Assignment Models - Pydantic schemas for assignment operations
"""

from app.modules.assignment.models.assignment_history import (
    Assignment,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentStatus,
    ReassignmentCreate,
    ReassignmentReason,
    AssignmentStats,
    AssignmentBulkReassign,
    BulkReassignResult,
)
from app.modules.assignment.models.agent_workload import (
    AgentWorkload,
    AgentWorkloadStats,
    AgentPerformanceMetrics,
    WorkloadBalanceReport,
    AgentCapacityForecast,
)
from app.modules.assignment.models.assignment_rule import (
    AssignmentRule,
    AssignmentRuleCreate,
    AssignmentRuleUpdate,
)

__all__ = [
    "Assignment",
    "AssignmentCreate",
    "AssignmentUpdate",
    "AssignmentStatus",
    "ReassignmentCreate",
    "ReassignmentReason",
    "AssignmentStats",
    "AssignmentBulkReassign",
    "BulkReassignResult",
    "AgentWorkload",
    "AgentWorkloadStats",
    "AgentPerformanceMetrics",
    "WorkloadBalanceReport",
    "AgentCapacityForecast",
    "AssignmentRule",
    "AssignmentRuleCreate",
    "AssignmentRuleUpdate",
]
