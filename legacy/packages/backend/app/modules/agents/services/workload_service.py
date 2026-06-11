"""
Workload Service - Workload Balancing and Performance Business Logic

Service for workload management, balancing, and performance tracking
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime, timedelta
from decimal import Decimal

from app.modules.agents.models import WorkloadStatus, AgentAvailability


class WorkloadService:
    """Service for workload and performance business logic"""

    def calculate_workload_status(
        self,
        current_assignments: int,
        max_concurrent: int,
    ) -> WorkloadStatus:
        """
        Calculate workload status based on capacity

        Args:
            current_assignments: Current assignment count
            max_concurrent: Maximum concurrent assignments

        Returns:
            Workload status enum
        """
        if max_concurrent == 0:
            return WorkloadStatus.UNAVAILABLE

        capacity_ratio = current_assignments / max_concurrent

        if capacity_ratio >= 1.0:
            return WorkloadStatus.OVERLOADED
        elif capacity_ratio >= 0.8:
            return WorkloadStatus.BUSY
        elif capacity_ratio >= 0.5:
            return WorkloadStatus.NORMAL
        else:
            return WorkloadStatus.AVAILABLE

    def calculate_capacity_percentage(
        self,
        current_assignments: int,
        max_concurrent: int,
    ) -> Decimal:
        """
        Calculate capacity percentage

        Args:
            current_assignments: Current assignment count
            max_concurrent: Maximum concurrent assignments

        Returns:
            Capacity percentage (0-100+)
        """
        if max_concurrent == 0:
            return Decimal("100")

        percentage = (Decimal(str(current_assignments)) / Decimal(str(max_concurrent))) * 100
        return round(percentage, 2)

    def recommend_workload_rebalancing(
        self,
        agents: List[Dict[str, Any]],
        threshold_percentage: Decimal = Decimal("80"),
    ) -> Dict[str, Any]:
        """
        Recommend workload rebalancing actions

        Args:
            agents: List of agents with workload data
            threshold_percentage: Capacity threshold for rebalancing

        Returns:
            {
                "needs_rebalancing": bool,
                "overloaded_agents": List[Dict],
                "available_agents": List[Dict],
                "recommendations": List[Dict]
            }
        """
        overloaded = []
        available = []

        for agent in agents:
            capacity = agent.get("capacity_percentage", 0)
            availability = agent.get("availability", "unavailable")

            if capacity >= threshold_percentage or agent.get("workload_status") == WorkloadStatus.OVERLOADED.value:
                overloaded.append(agent)
            elif capacity < 60 and availability == AgentAvailability.AVAILABLE.value:
                available.append(agent)

        recommendations = []
        for overloaded_agent in overloaded:
            # Find assignments that can be reassigned
            current = overloaded_agent.get("current_assignments", 0)
            max_concurrent = overloaded_agent.get("max_concurrent_assignments", 20)
            excess = current - int(max_concurrent * 0.8)

            if excess > 0 and available:
                # Sort available agents by capacity (lowest first)
                sorted_available = sorted(available, key=lambda a: a.get("capacity_percentage", 0))
                target_agent = sorted_available[0]

                recommendations.append({
                    "from_agent_id": overloaded_agent.get("agent_id"),
                    "to_agent_id": target_agent.get("agent_id"),
                    "assignments_to_move": min(excess, 3),  # Move max 3 at a time
                    "reason": "workload_imbalance",
                    "from_capacity": overloaded_agent.get("capacity_percentage"),
                    "to_capacity": target_agent.get("capacity_percentage"),
                })

        needs_rebalancing = len(recommendations) > 0

        logger.info(
            f"Workload rebalancing check: needs={needs_rebalancing}, "
            f"overloaded={len(overloaded)}, available={len(available)}, "
            f"recommendations={len(recommendations)}"
        )

        return {
            "needs_rebalancing": needs_rebalancing,
            "overloaded_agents": overloaded,
            "available_agents": available,
            "recommendations": recommendations,
        }

    def calculate_agent_efficiency(
        self,
        performance_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate agent efficiency metrics

        Args:
            performance_stats: Agent performance statistics

        Returns:
            Efficiency metrics
        """
        processed = performance_stats.get("current_month_processed", 0)
        approved = performance_stats.get("current_month_approved", 0)
        rejected = performance_stats.get("current_month_rejected", 0)
        escalated = performance_stats.get("current_month_escalated", 0)

        # Approval rate
        approval_rate = (approved / processed * 100) if processed > 0 else 0

        # Rejection rate
        rejection_rate = (rejected / processed * 100) if processed > 0 else 0

        # Escalation rate
        escalation_rate = (escalated / processed * 100) if processed > 0 else 0

        # Processing speed score (lower minutes = higher score)
        avg_minutes = performance_stats.get("avg_processing_minutes", 0)
        speed_score = max(0, 100 - (avg_minutes / 6))  # 100 at 0min, 0 at 600min

        # SLA compliance
        sla_percentage = performance_stats.get("sla_respect_percentage", 0)

        # Overall efficiency score (weighted average)
        efficiency_score = (
            (approval_rate * 0.3) +
            (speed_score * 0.25) +
            (sla_percentage * 0.35) +
            ((100 - escalation_rate) * 0.1)
        )

        metrics = {
            "efficiency_score": round(efficiency_score, 2),
            "approval_rate": round(approval_rate, 2),
            "rejection_rate": round(rejection_rate, 2),
            "escalation_rate": round(escalation_rate, 2),
            "speed_score": round(speed_score, 2),
            "sla_compliance": round(sla_percentage, 2),
            "processed_count": processed,
        }

        logger.debug(f"Agent efficiency metrics: {metrics}")

        return metrics

    def identify_training_needs(
        self,
        performance_stats: Dict[str, Any],
        workload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Identify agent training needs based on performance

        Args:
            performance_stats: Agent performance statistics
            workload: Agent workload data

        Returns:
            List of training recommendations
        """
        recommendations = []

        # Low SLA compliance
        sla_percentage = performance_stats.get("sla_respect_percentage", 100)
        if sla_percentage < 70:
            recommendations.append({
                "area": "time_management",
                "priority": "high",
                "reason": f"SLA compliance at {sla_percentage}%",
                "suggested_training": "Time management and prioritization",
            })

        # High rejection rate
        processed = performance_stats.get("current_month_processed", 0)
        rejected = performance_stats.get("current_month_rejected", 0)
        if processed > 10 and (rejected / processed) > 0.3:
            recommendations.append({
                "area": "quality_control",
                "priority": "high",
                "reason": f"High rejection rate: {rejected}/{processed}",
                "suggested_training": "Quality standards and verification procedures",
            })

        # High escalation rate
        escalated = performance_stats.get("current_month_escalated", 0)
        if processed > 10 and (escalated / processed) > 0.2:
            recommendations.append({
                "area": "decision_making",
                "priority": "medium",
                "reason": f"High escalation rate: {escalated}/{processed}",
                "suggested_training": "Decision making authority and guidelines",
            })

        # Slow processing
        avg_minutes = performance_stats.get("avg_processing_minutes", 0)
        if avg_minutes > 240:  # > 4 hours
            recommendations.append({
                "area": "efficiency",
                "priority": "medium",
                "reason": f"Average processing time: {avg_minutes} minutes",
                "suggested_training": "Process optimization and system tools",
            })

        # Low quality score
        quality_avg = workload.get("quality_score_avg", 100)
        if quality_avg < 70:
            recommendations.append({
                "area": "quality",
                "priority": "high",
                "reason": f"Quality score: {quality_avg}%",
                "suggested_training": "Quality assurance and best practices",
            })

        logger.info(f"Identified {len(recommendations)} training needs")

        return recommendations

    def predict_capacity_needs(
        self,
        workloads: List[Dict[str, Any]],
        forecast_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Predict capacity needs for ministry

        Args:
            workloads: List of agent workloads
            forecast_days: Days to forecast

        Returns:
            Capacity prediction
        """
        total_capacity = 0
        total_current = 0
        total_agents = len(workloads)
        available_agents = 0

        for workload in workloads:
            total_capacity += workload.get("max_concurrent_assignments", 20)
            total_current += workload.get("current_assignments", 0)
            if workload.get("availability") == AgentAvailability.AVAILABLE.value:
                available_agents += 1

        # Current utilization
        current_utilization = (total_current / total_capacity * 100) if total_capacity > 0 else 0

        # Calculate trend (mock - would use historical data)
        avg_daily_completions = sum(
            w.get("avg_daily_completions", 0) for w in workloads
        ) / total_agents if total_agents > 0 else 0

        # Predict needs
        needs_more_agents = current_utilization > 80
        can_handle_more = current_utilization < 60

        prediction = {
            "current_utilization": round(current_utilization, 2),
            "total_capacity": total_capacity,
            "total_current": total_current,
            "available_capacity": total_capacity - total_current,
            "total_agents": total_agents,
            "available_agents": available_agents,
            "avg_daily_completions": round(avg_daily_completions, 2),
            "forecast_days": forecast_days,
            "needs_more_agents": needs_more_agents,
            "can_handle_more": can_handle_more,
            "recommendation": self._get_capacity_recommendation(current_utilization),
        }

        logger.info(f"Capacity prediction: {prediction}")

        return prediction

    def _get_capacity_recommendation(self, utilization: float) -> str:
        """Get capacity recommendation based on utilization"""
        if utilization >= 90:
            return "URGENT: Hire additional agents immediately"
        elif utilization >= 80:
            return "HIGH: Plan to onboard more agents soon"
        elif utilization >= 70:
            return "MEDIUM: Monitor closely, prepare recruitment"
        elif utilization >= 50:
            return "NORMAL: Current capacity is adequate"
        elif utilization >= 30:
            return "LOW: Capacity underutilized, consider workload distribution"
        else:
            return "VERY LOW: Significant excess capacity"

    def generate_performance_summary(
        self,
        performance_stats: List[Dict[str, Any]],
        workloads: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate ministry-wide performance summary

        Args:
            performance_stats: List of agent performance stats
            workloads: List of agent workloads

        Returns:
            Performance summary
        """
        if not performance_stats:
            return {"total_agents": 0}

        total_agents = len(performance_stats)
        total_processed = sum(s.get("current_month_processed", 0) for s in performance_stats)
        total_approved = sum(s.get("current_month_approved", 0) for s in performance_stats)
        total_rejected = sum(s.get("current_month_rejected", 0) for s in performance_stats)
        total_escalated = sum(s.get("current_month_escalated", 0) for s in performance_stats)

        # Average metrics
        avg_processing_minutes = sum(
            s.get("avg_processing_minutes", 0) for s in performance_stats
        ) / total_agents

        avg_sla_compliance = sum(
            s.get("sla_respect_percentage", 0) for s in performance_stats
        ) / total_agents

        # Workload metrics
        avg_capacity = sum(
            w.get("capacity_percentage", 0) for w in workloads
        ) / len(workloads) if workloads else 0

        avg_quality = sum(
            w.get("quality_score_avg", 0) for w in workloads
        ) / len(workloads) if workloads else 0

        summary = {
            "total_agents": total_agents,
            "total_processed": total_processed,
            "total_approved": total_approved,
            "total_rejected": total_rejected,
            "total_escalated": total_escalated,
            "approval_rate": round((total_approved / total_processed * 100) if total_processed > 0 else 0, 2),
            "rejection_rate": round((total_rejected / total_processed * 100) if total_processed > 0 else 0, 2),
            "escalation_rate": round((total_escalated / total_processed * 100) if total_processed > 0 else 0, 2),
            "avg_processing_minutes": round(avg_processing_minutes, 2),
            "avg_sla_compliance": round(avg_sla_compliance, 2),
            "avg_capacity_utilization": round(avg_capacity, 2),
            "avg_quality_score": round(avg_quality, 2),
        }

        logger.info(f"Performance summary generated: {summary}")

        return summary
