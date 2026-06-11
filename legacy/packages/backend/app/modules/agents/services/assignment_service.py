"""
Assignment Service - DEPRECATED & COMMENTED OUT

SUPERSEDED BY: app.modules.assignment.services.assignment_service
which uses DB-driven priority/SLA from workflows.priority_weight (migration 131).

DO NOT USE THIS MODULE FOR NEW CODE.
Import from app.modules.assignment.services instead.

The code below is preserved as reference for future migration of:
- should_escalate() → urgency classification (critical/high/normal)
- calculate_priority_score() → amount-based and age-based scoring
- validate_reassignment() → cooldown + same-agent guard
- calculate_sla_deadline() → priority-level SLA adjustment
These functions have NO equivalent in the modern module yet.
"""

# ============================================================================
# COMMENTED OUT — Original legacy code preserved for reference
# ============================================================================

# from typing import Dict, Any, Optional, List
# from loguru import logger
# from datetime import datetime, timedelta
# from decimal import Decimal
#
# from app.modules.agents.models import AssignmentMethod, AssignmentStatus
#
#
# class AssignmentService:
#     """Service for assignment and work queue business logic"""
#
#     def calculate_priority_score(
#         self,
#         declaration_type: str,
#         amount: Optional[Decimal] = None,
#         age_hours: float = 0,
#         is_escalated: bool = False,
#     ) -> Decimal:
#         """
#         Calculate priority score for work queue item.
#
#         NOTE: Modern equivalent is agent_queue_service._calculate_priority()
#         but it LACKS amount-based and age-based scoring factors.
#         These should be ported to the modern module when declarations
#         are re-enabled.
#
#         Args:
#             declaration_type: Type of declaration
#             amount: Declaration amount
#             age_hours: Hours since creation
#             is_escalated: Whether item is escalated
#
#         Returns:
#             Priority score (higher = more urgent)
#         """
#         score = Decimal("0")
#
#         # Base priority by type
#         # NOTE: These types are OLD declaration types, not workflow codes
#         type_priorities = {
#             "tax_income": 50,
#             "tax_property": 40,
#             "tax_business": 45,
#             "tax_vat": 55,
#             "customs": 60,
#             "fine": 70,
#             "appeal": 80,
#         }
#         base_priority = type_priorities.get(declaration_type, 30)
#         score += Decimal(str(base_priority))
#
#         # Amount factor (higher amounts = higher priority)
#         # GAP: This logic is NOT in the modern module
#         if amount:
#             if amount >= Decimal("1000000"):  # 1M+
#                 score += Decimal("30")
#             elif amount >= Decimal("500000"):  # 500K+
#                 score += Decimal("20")
#             elif amount >= Decimal("100000"):  # 100K+
#                 score += Decimal("10")
#
#         # Age factor (older = higher priority)
#         # GAP: This logic is NOT in the modern module
#         if age_hours > 72:  # > 3 days
#             score += Decimal("25")
#         elif age_hours > 48:  # > 2 days
#             score += Decimal("15")
#         elif age_hours > 24:  # > 1 day
#             score += Decimal("10")
#
#         # Escalation bonus
#         if is_escalated:
#             score += Decimal("40")
#
#         logger.debug(
#             f"Priority score for {declaration_type}: {score} "
#             f"(amount: {amount}, age: {age_hours}h, escalated: {is_escalated})"
#         )
#
#         return score
#
#     def calculate_sla_deadline(
#         self,
#         declaration_type: str,
#         priority_level: Optional[str] = None,
#         created_at: Optional[datetime] = None,
#     ) -> datetime:
#         """
#         Calculate SLA deadline for declaration.
#
#         NOTE: Modern equivalent is agent_queue_service._calculate_sla_deadline()
#         but it LACKS priority-level adjustment (urgent/high/low modifiers).
#
#         Args:
#             declaration_type: Type of declaration
#             priority_level: Priority level (urgent, high, normal, low)
#             created_at: Creation time (defaults to now)
#
#         Returns:
#             SLA deadline datetime
#         """
#         if created_at is None:
#             created_at = datetime.now(timezone.utc)
#
#         # Base SLA hours by type
#         # NOTE: These are OLD types. Modern uses workflows.sla_hours from DB
#         base_sla_hours = {
#             "appeal": 48,      # 2 days
#             "fine": 72,        # 3 days
#             "customs": 96,     # 4 days
#             "tax_vat": 120,    # 5 days
#             "tax_business": 168,  # 7 days
#             "tax_income": 240,    # 10 days
#             "tax_property": 240,  # 10 days
#         }
#         hours = base_sla_hours.get(declaration_type, 168)
#
#         # Adjust for priority
#         # GAP: This logic is NOT in the modern module
#         if priority_level == "urgent":
#             hours = hours // 2
#         elif priority_level == "high":
#             hours = int(hours * 0.75)
#         elif priority_level == "low":
#             hours = int(hours * 1.5)
#
#         deadline = created_at + timedelta(hours=hours)
#
#         logger.info(
#             f"SLA deadline for {declaration_type} ({priority_level}): "
#             f"{deadline} ({hours}h from {created_at})"
#         )
#
#         return deadline
#
#     def check_sla_status(
#         self,
#         sla_deadline: datetime,
#         current_time: Optional[datetime] = None,
#     ) -> str:
#         """
#         Check SLA status.
#
#         NOTE: Modern equivalent is agent_queue_service.check_sla_status()
#         which uses SLA_WARNING_HOURS from settings instead of 25% threshold.
#         """
#         if current_time is None:
#             current_time = datetime.now(timezone.utc)
#
#         if current_time > sla_deadline:
#             return "violated"
#
#         time_remaining = (sla_deadline - current_time).total_seconds() / 3600
#         time_total = (sla_deadline - (sla_deadline - timedelta(hours=168))).total_seconds() / 3600
#
#         # At risk if less than 25% of time remaining
#         if time_remaining < (time_total * 0.25):
#             return "at_risk"
#
#         return "on_track"
#
#     def should_escalate(
#         self,
#         assignment: Dict[str, Any],
#         current_time: Optional[datetime] = None,
#     ) -> Dict[str, Any]:
#         """
#         Check if assignment should be escalated.
#
#         GAP: This ENTIRE function has NO equivalent in the modern module.
#         The outbox health check handles SLA violations but lacks:
#         - Urgency classification (critical/high/normal)
#         - Processing duration monitoring (>24h)
#         - Status-stuck detection (pending_review >12h)
#
#         Should be ported to the modern module as a cron job or
#         integrated into the outbox health check.
#
#         Args:
#             assignment: Assignment data
#             current_time: Current time (defaults to now)
#
#         Returns:
#             {"should_escalate": bool, "reason": Optional[str], "urgency": str}
#         """
#         if current_time is None:
#             current_time = datetime.now(timezone.utc)
#
#         reasons = []
#         urgency = "normal"
#
#         # Check SLA
#         deadline = assignment.get("deadline")
#         if deadline:
#             if current_time > deadline:
#                 reasons.append("SLA deadline violated")
#                 urgency = "critical"
#             else:
#                 time_remaining = (deadline - current_time).total_seconds() / 3600
#                 if time_remaining < 6:  # Less than 6 hours
#                     reasons.append("Approaching SLA deadline")
#                     urgency = "high"
#
#         # Check processing duration
#         started_at = assignment.get("started_at")
#         if started_at:
#             hours_elapsed = (current_time - started_at).total_seconds() / 3600
#             if hours_elapsed > 24:
#                 reasons.append(f"Processing for {hours_elapsed:.1f} hours")
#                 urgency = "high"
#
#         # Check if stuck in same status
#         status = assignment.get("status")
#         updated_at = assignment.get("updated_at")
#         if status == AssignmentStatus.PENDING_REVIEW and updated_at:
#             hours_pending = (current_time - updated_at).total_seconds() / 3600
#             if hours_pending > 12:
#                 reasons.append("Pending review for too long")
#                 urgency = "high"
#
#         should_escalate = len(reasons) > 0
#
#         logger.debug(
#             f"Assignment {assignment.get('id')} escalation check: "
#             f"should_escalate={should_escalate}, urgency={urgency}, reasons={reasons}"
#         )
#
#         return {
#             "should_escalate": should_escalate,
#             "reason": "; ".join(reasons) if reasons else None,
#             "urgency": urgency,
#         }
#
#     def select_best_agent(
#         self,
#         agents: List[Dict[str, Any]],
#         agent_scores: Dict[str, Dict[str, Any]],
#     ) -> Optional[Dict[str, Any]]:
#         """
#         Select best agent from candidates.
#
#         NOTE: Modern equivalent is rules_engine.select_best_agent()
#         which is MORE flexible (rule-based with JSONB conditions).
#         """
#         if not agents:
#             logger.warning("No agents available for assignment")
#             return None
#
#         eligible_agents = [
#             agent for agent in agents
#             if agent_scores.get(agent["id"], {}).get("is_eligible", False)
#         ]
#
#         if not eligible_agents:
#             logger.warning("No eligible agents found")
#             return None
#
#         best_agent = max(
#             eligible_agents,
#             key=lambda a: agent_scores.get(a["id"], {}).get("score", Decimal("0"))
#         )
#
#         best_score = agent_scores.get(best_agent["id"], {})
#         logger.info(
#             f"Selected agent {best_agent['id']} with score {best_score.get('score')}"
#         )
#
#         return best_agent
#
#     def validate_reassignment(
#         self,
#         assignment: Dict[str, Any],
#         new_agent_id: str,
#         reason: str,
#     ) -> Dict[str, Any]:
#         """
#         Validate reassignment request.
#
#         GAP: This function has NO equivalent in the modern module.
#         The modern reassign() in assignment_repository does a raw UPDATE
#         without any of these guards:
#         - Same-agent validation
#         - 1-hour cooldown between reassignments
#         - Reason validation
#
#         Should be ported to the modern assignment_service.
#
#         Returns:
#             {"is_valid": bool, "errors": List[str]}
#         """
#         errors = []
#
#         if assignment.get("status") == AssignmentStatus.COMPLETED:
#             errors.append("Cannot reassign completed assignment")
#
#         if assignment.get("agent_id") == new_agent_id:
#             errors.append("Cannot reassign to the same agent")
#
#         reassigned_at = assignment.get("reassigned_at")
#         if reassigned_at:
#             hours_since = (datetime.now(timezone.utc) - reassigned_at).total_seconds() / 3600
#             if hours_since < 1:
#                 errors.append("Assignment was recently reassigned (wait 1 hour)")
#
#         valid_reasons = [
#             "workload_imbalance",
#             "agent_unavailable",
#             "specialization_mismatch",
#             "quality_issue",
#             "deadline_missed",
#             "agent_request",
#             "supervisor_decision",
#             "complexity_change",
#         ]
#         if reason not in valid_reasons:
#             errors.append(f"Invalid reason: {reason}")
#
#         is_valid = len(errors) == 0
#
#         logger.debug(
#             f"Reassignment validation for {assignment.get('id')}: "
#             f"valid={is_valid}, errors={errors}"
#         )
#
#         return {
#             "is_valid": is_valid,
#             "errors": errors,
#         }
#
#     def calculate_processing_metrics(
#         self,
#         assignment: Dict[str, Any],
#     ) -> Dict[str, Any]:
#         """
#         Calculate processing metrics for assignment.
#
#         NOTE: Modern equivalent is assignment_repository.get_agent_stats()
#         which does this in SQL (more efficient for batch).
#         """
#         assigned_at = assignment.get("assigned_at")
#         started_at = assignment.get("started_at")
#         completed_at = assignment.get("completed_at")
#         deadline = assignment.get("deadline")
#
#         metrics = {
#             "assignment_to_start_hours": None,
#             "processing_duration_hours": None,
#             "total_duration_hours": None,
#             "deadline_met": None,
#             "sla_status": None,
#         }
#
#         if not assigned_at:
#             return metrics
#
#         if started_at:
#             metrics["assignment_to_start_hours"] = (
#                 (started_at - assigned_at).total_seconds() / 3600
#             )
#
#         if started_at and completed_at:
#             metrics["processing_duration_hours"] = (
#                 (completed_at - started_at).total_seconds() / 3600
#             )
#
#         if completed_at:
#             metrics["total_duration_hours"] = (
#                 (completed_at - assigned_at).total_seconds() / 3600
#             )
#
#         if deadline and completed_at:
#             metrics["deadline_met"] = completed_at <= deadline
#             metrics["sla_status"] = "met" if metrics["deadline_met"] else "violated"
#         elif deadline:
#             metrics["sla_status"] = self.check_sla_status(deadline)
#
#         logger.debug(f"Assignment {assignment.get('id')} metrics: {metrics}")
#
#         return metrics
#
#     def generate_assignment_report(
#         self,
#         assignments: List[Dict[str, Any]],
#     ) -> Dict[str, Any]:
#         """
#         Generate assignment summary report.
#
#         NOTE: Modern equivalent is assignment_repository.get_agent_stats()
#         + get_supervisor_stats() which do this in SQL (more efficient).
#         """
#         if not assignments:
#             return {
#                 "total": 0,
#                 "by_status": {},
#                 "by_method": {},
#                 "avg_processing_hours": 0,
#                 "sla_compliance_rate": 0,
#             }
#
#         by_status = {}
#         for assignment in assignments:
#             status = assignment.get("status", "unknown")
#             by_status[status] = by_status.get(status, 0) + 1
#
#         by_method = {}
#         for assignment in assignments:
#             method = assignment.get("assignment_method", "unknown")
#             by_method[method] = by_method.get(method, 0) + 1
#
#         processing_hours = [
#             a.get("processing_duration_hours")
#             for a in assignments
#             if a.get("processing_duration_hours") is not None
#         ]
#         avg_processing = sum(processing_hours) / len(processing_hours) if processing_hours else 0
#
#         deadline_checks = [
#             a.get("deadline_met")
#             for a in assignments
#             if a.get("deadline_met") is not None
#         ]
#         sla_compliance = (
#             sum(1 for met in deadline_checks if met) / len(deadline_checks) * 100
#             if deadline_checks else 0
#         )
#
#         report = {
#             "total": len(assignments),
#             "by_status": by_status,
#             "by_method": by_method,
#             "avg_processing_hours": round(avg_processing, 2),
#             "sla_compliance_rate": round(sla_compliance, 2),
#             "completed": by_status.get(AssignmentStatus.COMPLETED.value, 0),
#             "in_progress": by_status.get(AssignmentStatus.IN_PROGRESS.value, 0),
#             "pending_review": by_status.get(AssignmentStatus.PENDING_REVIEW.value, 0),
#         }
#
#         logger.info(f"Assignment report generated: {report}")
#
#         return report
