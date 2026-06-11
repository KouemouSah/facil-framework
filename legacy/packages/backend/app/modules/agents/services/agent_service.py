"""
Agent Service - Ministry Agent Management Business Logic

Service for agent configuration, permissions, and availability management
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime, time, timezone
from decimal import Decimal


class AgentService:
    """Service for agent management business logic"""

    def validate_agent_permissions(
        self,
        agent: Dict[str, Any],
        required_approval_amount: Optional[Decimal] = None,
    ) -> Dict[str, bool]:
        """
        Validate agent permissions

        Args:
            agent: Agent data
            required_approval_amount: Amount requiring approval

        Returns:
            Dict of permission flags
        """
        permissions = {
            "can_approve": True,
            "can_escalate": agent.get("can_escalate", True),
            "can_assign": agent.get("can_assign_tasks", False),
            "approval_within_limit": True,
        }

        # Check approval amount limit
        if required_approval_amount is not None:
            if agent.get("can_approve_unlimited"):
                permissions["approval_within_limit"] = True
            else:
                max_amount = agent.get("max_approval_amount")
                if max_amount is not None:
                    permissions["approval_within_limit"] = required_approval_amount <= max_amount
                else:
                    permissions["approval_within_limit"] = False

        logger.debug(f"Agent {agent.get('id')} permissions: {permissions}")

        return permissions

    def check_working_hours(
        self,
        agent: Dict[str, Any],
        check_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Check if agent is within working hours

        Args:
            agent: Agent data
            check_time: Time to check (defaults to now)

        Returns:
            {
                "within_hours": bool,
                "reason": Optional[str]
            }
        """
        if check_time is None:
            check_time = datetime.now(timezone.utc)

        working_hours_start = agent.get("working_hours_start")
        working_hours_end = agent.get("working_hours_end")
        working_days = agent.get("working_days", [])

        # If no working hours set, assume 24/7 availability
        if not working_hours_start or not working_hours_end:
            return {"within_hours": True, "reason": None}

        # Check day of week
        current_day = check_time.strftime("%A")
        if working_days and current_day not in working_days:
            return {
                "within_hours": False,
                "reason": f"Agent does not work on {current_day}",
            }

        # Check time
        current_time = check_time.time()
        if not (working_hours_start <= current_time <= working_hours_end):
            return {
                "within_hours": False,
                "reason": f"Outside working hours ({working_hours_start}-{working_hours_end})",
            }

        return {"within_hours": True, "reason": None}

    def calculate_agent_score(
        self,
        agent: Dict[str, Any],
        workload: Dict[str, Any],
        declaration_type: str,
        required_amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Calculate agent assignment score based on multiple factors

        Args:
            agent: Agent data
            workload: Workload data
            declaration_type: Type of declaration
            required_amount: Amount requiring approval

        Returns:
            {
                "score": Decimal,
                "breakdown": Dict[str, Any],
                "is_eligible": bool,
                "reasons": List[str]
            }
        """
        score = Decimal("0")
        breakdown = {}
        reasons = []
        is_eligible = True

        # Check if agent is active
        if not agent.get("is_active"):
            is_eligible = False
            reasons.append("Agent is inactive")
            return {
                "score": score,
                "breakdown": breakdown,
                "is_eligible": is_eligible,
                "reasons": reasons,
            }

        # Check working hours
        working_hours_check = self.check_working_hours(agent)
        if not working_hours_check["within_hours"]:
            score -= Decimal("20")
            breakdown["working_hours_penalty"] = -20
            reasons.append(working_hours_check["reason"])

        # Check approval permissions
        if required_amount:
            permissions = self.validate_agent_permissions(agent, required_amount)
            if not permissions["approval_within_limit"]:
                is_eligible = False
                reasons.append(f"Amount {required_amount} exceeds approval limit")
                return {
                    "score": score,
                    "breakdown": breakdown,
                    "is_eligible": is_eligible,
                    "reasons": reasons,
                }

        # Capacity score (lower capacity = higher score)
        capacity = workload.get("capacity_percentage", 0)
        capacity_score = Decimal("100") - Decimal(str(capacity))
        score += capacity_score
        breakdown["capacity_score"] = float(capacity_score)

        # Quality score bonus
        quality_avg = workload.get("quality_score_avg", 0)
        quality_bonus = Decimal(str(quality_avg)) * Decimal("2")
        score += quality_bonus
        breakdown["quality_bonus"] = float(quality_bonus)

        # Success rate bonus
        success_rate = workload.get("success_rate", 0)
        success_bonus = Decimal(str(success_rate)) * Decimal("0.5")
        score += success_bonus
        breakdown["success_bonus"] = float(success_bonus)

        # Specialization bonus
        specializations = workload.get("active_specializations", [])
        if declaration_type in specializations:
            specialization_bonus = Decimal("20")
            score += specialization_bonus
            breakdown["specialization_bonus"] = float(specialization_bonus)

        # Preferred declaration type bonus
        preferred_types = workload.get("preferred_declaration_types", [])
        if declaration_type in preferred_types:
            preference_bonus = Decimal("15")
            score += preference_bonus
            breakdown["preference_bonus"] = float(preference_bonus)

        # Deadline compliance bonus
        compliance_rate = workload.get("deadline_compliance_rate", 0)
        compliance_bonus = Decimal(str(compliance_rate)) * Decimal("0.3")
        score += compliance_bonus
        breakdown["compliance_bonus"] = float(compliance_bonus)

        logger.info(
            f"Agent {agent.get('id')} score for {declaration_type}: {score} "
            f"(capacity: {capacity}%, eligible: {is_eligible})"
        )

        return {
            "score": score,
            "breakdown": breakdown,
            "is_eligible": is_eligible,
            "reasons": reasons,
        }

    def recommend_backup_agent(
        self,
        primary_agent: Dict[str, Any],
        backup_agents: List[Dict[str, Any]],
        workloads: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Recommend best backup agent

        Args:
            primary_agent: Primary agent data
            backup_agents: List of backup agents
            workloads: Dict of agent workloads keyed by agent_id

        Returns:
            Recommended backup agent or None
        """
        if not backup_agents:
            logger.warning(f"No backup agents for {primary_agent.get('id')}")
            return None

        # Score each backup agent
        scored_agents = []
        for backup in backup_agents:
            backup_id = backup.get("id")
            workload = workloads.get(backup_id, {})

            # Check availability
            availability = workload.get("availability", "unavailable")
            if availability != "available":
                continue

            # Check capacity
            capacity = workload.get("capacity_percentage", 100)
            if capacity >= 90:
                continue

            # Calculate score
            score = Decimal("100") - Decimal(str(capacity))
            quality_avg = workload.get("quality_score_avg", 0)
            score += Decimal(str(quality_avg)) * Decimal("2")

            scored_agents.append({
                "agent": backup,
                "workload": workload,
                "score": score,
            })

        if not scored_agents:
            logger.warning(f"No available backup agents for {primary_agent.get('id')}")
            return None

        # Return highest scoring agent
        best = max(scored_agents, key=lambda x: x["score"])
        logger.info(
            f"Recommended backup agent {best['agent'].get('id')} "
            f"with score {best['score']}"
        )

        return best["agent"]

    def validate_agent_assignment(
        self,
        agent: Dict[str, Any],
        declaration_type: str,
        amount: Optional[Decimal] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """
        Validate if agent can be assigned

        Args:
            agent: Agent data
            declaration_type: Type of declaration
            amount: Declaration amount
            priority: Priority level

        Returns:
            {
                "can_assign": bool,
                "reasons": List[str],
                "warnings": List[str]
            }
        """
        reasons = []
        warnings = []

        # Check if active
        if not agent.get("is_active"):
            reasons.append("Agent is inactive")

        # Check approval permissions
        if amount:
            permissions = self.validate_agent_permissions(agent, amount)
            if not permissions["approval_within_limit"]:
                reasons.append(f"Amount {amount} exceeds approval limit {agent.get('max_approval_amount')}")

        # Check working hours
        working_hours = self.check_working_hours(agent)
        if not working_hours["within_hours"]:
            warnings.append(working_hours["reason"])

        can_assign = len(reasons) == 0

        logger.debug(
            f"Agent {agent.get('id')} assignment validation: "
            f"can_assign={can_assign}, reasons={reasons}, warnings={warnings}"
        )

        return {
            "can_assign": can_assign,
            "reasons": reasons,
            "warnings": warnings,
        }

    def calculate_optimal_max_assignments(
        self,
        agent_performance: Dict[str, Any],
        declaration_type: str = "general",
    ) -> int:
        """
        Calculate optimal maximum concurrent assignments for agent

        Args:
            agent_performance: Agent performance stats
            declaration_type: Type of declarations

        Returns:
            Recommended max assignments
        """
        # Base capacity
        base_capacity = 20

        # Adjust based on quality score
        quality_avg = agent_performance.get("quality_score_avg", 0)
        if quality_avg >= 90:
            base_capacity = 25
        elif quality_avg >= 80:
            base_capacity = 22
        elif quality_avg < 60:
            base_capacity = 15

        # Adjust based on avg processing time
        avg_hours = agent_performance.get("avg_processing_minutes", 0) / 60
        if avg_hours > 4:
            base_capacity = max(10, base_capacity - 5)
        elif avg_hours < 1:
            base_capacity += 5

        # Adjust based on SLA respect
        sla_percentage = agent_performance.get("sla_respect_percentage", 100)
        if sla_percentage < 70:
            base_capacity = max(10, base_capacity - 5)

        logger.info(
            f"Calculated optimal max assignments: {base_capacity} "
            f"(quality: {quality_avg}, avg_hours: {avg_hours})"
        )

        return base_capacity
