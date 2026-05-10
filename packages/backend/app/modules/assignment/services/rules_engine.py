"""
Rules Engine - Assignment rule evaluation and agent selection

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: assignment_rules (conditions, actions JSONB)
- Uses agent_profile_id for agent identification
- Uses item_type instead of declaration_type

Handles:
- Rule-based agent selection
- Load balancing
- Specialization matching
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import Depends
from loguru import logger

from app.config import get_settings
from app.modules.assignment.models.assignment_rule import AssignmentRule, RuleMatchResult
from app.modules.assignment.models.agent_workload import AgentWorkload
from app.modules.assignment.repositories.rules_repository import (
    RulesRepository,
    get_rules_repository,
)
from app.modules.assignment.repositories.workload_repository import (
    WorkloadRepository,
    get_workload_repository,
)


class RulesEngine:
    """Engine for evaluating assignment rules and selecting agents"""

    def __init__(
        self,
        rules_repository: Optional[RulesRepository] = None,
        workload_repository: Optional[WorkloadRepository] = None
    ):
        self.rules_repository = rules_repository or RulesRepository()
        self.workload_repository = workload_repository or WorkloadRepository()
        logger.info("RulesEngine initialized")

    async def select_best_agent(
        self,
        db,
        item_type: str,
        item_data: Dict[str, Any],
        rules: List[AssignmentRule],
        available_agents: List[AgentWorkload],
        priority_level: int = 5
    ) -> Optional[UUID]:
        """Select best agent for an item based on rules and scoring

        Args:
            db: Database connection
            item_type: Type of item (declaration type or workflow code)
            item_data: Item data for rule evaluation
            rules: List of active rules to evaluate
            available_agents: List of available AgentWorkload objects
            priority_level: Priority 1-10

        Returns:
            agent_profile_id of best agent or None
        """
        if not available_agents:
            return None

        if not rules:
            # No rules - use load balancing
            return self._select_by_load_balance(available_agents)

        # Evaluate each rule and collect results
        rule_matches: List[RuleMatchResult] = []
        for rule in sorted(rules, key=lambda r: r.priority, reverse=True):  # Higher priority first
            result = self._evaluate_rule(rule, item_type, item_data)
            if result.matched:
                rule_matches.append(result)
                logger.debug(f"Rule '{rule.name}' matched with score {result.score}")

        if not rule_matches:
            # No rules matched - use load balancing
            logger.debug("No rules matched, falling back to load balancing")
            # Track non-matching rules (times_applied increments)
            await self._track_rule_stats(db, rules, [], selected=None)
            return self._select_by_load_balance(available_agents)

        # Use best matching rule's actions to filter/score agents
        best_match = max(rule_matches, key=lambda r: r.score)

        # Apply rule actions to select agent
        selected = self._apply_rule_actions(
            best_match.actions,
            available_agents,
            item_type,
            priority_level
        )

        # Track rule effectiveness stats for all evaluated rules
        await self._track_rule_stats(db, rules, rule_matches, selected)

        return selected

    async def select_agent(
        self,
        db,
        item_type: str,
        priority_level: int
    ) -> Optional[UUID]:
        """Simple agent selection (backward compatible)

        Args:
            db: Database connection
            item_type: Type of item
            priority_level: Priority 1-10

        Returns:
            agent_profile_id or None
        """
        settings = get_settings()

        # Get active rules
        rules = await self.rules_repository.get_active_rules(db)

        if not rules:
            # Fallback to load balancing
            return await self._select_by_load_balance_from_db(db)

        # Get available agents
        available_agents = await self.workload_repository.get_available_agents(
            db, max_workload_pct=settings.QUEUE_MAX_WORKLOAD_PCT
        )

        if not available_agents:
            return None

        # Apply rules in priority order (higher first)
        for rule in sorted(rules, key=lambda r: r.priority, reverse=True):
            agent_profile_id = self._apply_rule_simple(rule, available_agents, item_type)
            if agent_profile_id:
                logger.info(f"Rule '{rule.name}' selected agent {agent_profile_id}")
                return agent_profile_id

        # Fallback to load balancing
        return self._select_by_load_balance(available_agents)

    async def _track_rule_stats(
        self,
        db,
        rules: List[AssignmentRule],
        rule_matches: List[RuleMatchResult],
        selected: Optional[UUID],
    ) -> None:
        """Track rule effectiveness: increment times_applied/matched/success for all rules."""
        matched_ids = {rm.rule_id for rm in rule_matches}
        for rule in rules:
            try:
                await self.rules_repository.increment_stats(
                    db=db,
                    rule_id=rule.id,
                    matched=rule.id in matched_ids,
                    successful=selected is not None,
                )
            except Exception as e:
                logger.warning(f"Failed to increment stats for rule {rule.id}: {e}")

    def _evaluate_rule(
        self,
        rule: AssignmentRule,
        item_type: str,
        item_data: Dict[str, Any]
    ) -> RuleMatchResult:
        """Evaluate a rule against item data

        Args:
            rule: AssignmentRule to evaluate
            item_type: Type of item
            item_data: Item data dictionary

        Returns:
            RuleMatchResult with match status and score
        """
        conditions = rule.conditions or {}
        matched = True
        score = 0.0

        # Evaluate type condition
        if "item_types" in conditions:
            allowed_types = conditions["item_types"]
            if item_type not in allowed_types:
                matched = False
            else:
                score += 10.0

        # Evaluate amount condition
        if matched and "min_amount" in conditions:
            amount = item_data.get("amount", 0)
            if amount < conditions["min_amount"]:
                matched = False
            else:
                score += 5.0

        if matched and "max_amount" in conditions:
            amount = item_data.get("amount", 0)
            if amount > conditions["max_amount"]:
                matched = False
            else:
                score += 5.0

        # Evaluate priority condition
        if matched and "min_priority" in conditions:
            priority = item_data.get("priority_level", 5)
            if priority < conditions["min_priority"]:
                matched = False
            else:
                score += 3.0

        # ── Treasury-specific conditions ──────────────────────────────────

        # Payment method filter
        if matched and "payment_methods" in conditions:
            payment_method = item_data.get("payment_method", "")
            if payment_method not in conditions["payment_methods"]:
                matched = False
            else:
                score += 8.0

        # Payment type filter
        if matched and "payment_types" in conditions:
            payment_type = item_data.get("payment_type", "")
            if payment_type not in conditions["payment_types"]:
                matched = False
            else:
                score += 6.0

        # Has penalties filter
        if matched and conditions.get("has_penalties"):
            penalties = item_data.get("penalties", 0)
            if not penalties or float(penalties) <= 0:
                matched = False
            else:
                score += 4.0

        # Entity location filter
        if matched and "entity_location_id" in conditions:
            item_location = item_data.get("entity_location_id", "")
            if item_location != conditions["entity_location_id"]:
                matched = False
            else:
                score += 3.0

        # Add base score from rule priority
        if matched:
            score += rule.priority / 10.0

        return RuleMatchResult(
            rule_id=rule.id,
            rule_name=rule.name,
            matched=matched,
            score=score,
            actions=rule.actions if matched else {},
            reason="Conditions matched" if matched else "Conditions not met"
        )

    def _apply_rule_actions(
        self,
        actions: Dict[str, Any],
        available_agents: List[AgentWorkload],
        item_type: str,
        priority_level: int
    ) -> Optional[UUID]:
        """Apply rule actions to select an agent

        Args:
            actions: Rule actions dictionary
            available_agents: List of available agents
            item_type: Type of item
            priority_level: Priority 1-10

        Returns:
            Selected agent_profile_id or None
        """
        if not available_agents:
            return None

        filtered_agents = available_agents.copy()

        # Filter by specialization if specified
        if "specializations" in actions:
            required_specs = actions["specializations"]
            filtered_agents = [
                a for a in filtered_agents
                if a.specializations and any(s in a.specializations for s in required_specs)
            ]

        # Filter by max workload if specified
        if "max_workload_pct" in actions:
            max_pct = actions["max_workload_pct"]
            filtered_agents = [
                a for a in filtered_agents
                if a.capacity_percentage <= max_pct
            ]

        # If no agents pass filters, use original list
        if not filtered_agents:
            filtered_agents = available_agents

        # Selection strategy
        strategy = actions.get("selection_strategy", "load_balance")

        if strategy == "round_robin":
            # Round-robin via least-assigned: pick the agent with fewest
            # current assignments. This is equivalent to true round-robin
            # over time and doesn't require external state (no Redis/BD counter).
            # Ties are broken by agent_profile_id for determinism.
            sorted_agents = sorted(
                filtered_agents,
                key=lambda a: (a.current_assignments or 0, str(a.agent_profile_id))
            )
            return sorted_agents[0].agent_profile_id
        elif strategy == "specialization":
            # Prefer agents with matching specialization
            for agent in filtered_agents:
                if agent.specializations and item_type in agent.specializations:
                    return agent.agent_profile_id
            # Fallback to load balance
            return self._select_by_load_balance(filtered_agents)
        else:  # load_balance (default)
            return self._select_by_load_balance(filtered_agents)

    def _apply_rule_simple(
        self,
        rule: AssignmentRule,
        available_agents: List[AgentWorkload],
        item_type: str
    ) -> Optional[UUID]:
        """Simple rule application without item data

        Args:
            rule: AssignmentRule to apply
            available_agents: List of available agents
            item_type: Type of item

        Returns:
            agent_profile_id or None if rule doesn't apply
        """
        conditions = rule.conditions or {}

        # Check if rule applies to this item type
        if "item_types" in conditions:
            if item_type not in conditions["item_types"]:
                return None

        # Apply actions
        return self._apply_rule_actions(
            rule.actions or {},
            available_agents,
            item_type,
            5  # default priority
        )

    def _select_by_load_balance(
        self,
        available_agents: List[AgentWorkload]
    ) -> Optional[UUID]:
        """Select agent with lowest workload

        Args:
            available_agents: List of AgentWorkload objects

        Returns:
            agent_profile_id of agent with lowest capacity_percentage
        """
        if not available_agents:
            return None

        # Return agent with lowest workload percentage
        best_agent = min(available_agents, key=lambda w: w.capacity_percentage)
        return best_agent.agent_profile_id

    async def _select_by_load_balance_from_db(self, db) -> Optional[UUID]:
        """Select agent with lowest workload (fetch from DB)

        Args:
            db: Database connection

        Returns:
            agent_profile_id or None
        """
        settings = get_settings()
        available_agents = await self.workload_repository.get_available_agents(
            db, max_workload_pct=settings.QUEUE_MAX_WORKLOAD_PCT
        )
        return self._select_by_load_balance(available_agents)


def get_rules_engine(
    rules_repo: RulesRepository = Depends(get_rules_repository),
    workload_repo: WorkloadRepository = Depends(get_workload_repository)
) -> RulesEngine:
    """Dependency injection for RulesEngine"""
    return RulesEngine(rules_repo, workload_repo)
