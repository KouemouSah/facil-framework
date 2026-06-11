"""
Auto Assignment Service - Automatic assignment of items to agents

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: assignments (Migration 053)
- Uses agent_profile_id instead of agent_id
- Uses item_id + item_type instead of declaration_id + declaration_type

Handles:
- Automatic assignment based on rules
- Load balancing across agents
- Specialization-based assignment
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import Depends
from loguru import logger

from app.config import get_settings

from app.modules.assignment.models.assignment_history import (
    Assignment,
    AssignmentCreate,
    AssignmentMethod,
)
from app.modules.assignment.models.agent_workload import AgentWorkload
from app.modules.assignment.repositories.assignment_repository import (
    AssignmentRepository,
    get_assignment_repository,
)
from app.modules.assignment.repositories.workload_repository import (
    WorkloadRepository,
    get_workload_repository,
)
from app.modules.assignment.repositories.rules_repository import (
    RulesRepository,
    get_rules_repository,
)
from app.modules.assignment.services.rules_engine import (
    RulesEngine,
    get_rules_engine,
)


class AutoAssignmentService:
    """Service for automatic assignment operations"""

    def __init__(
        self,
        assignment_repository: Optional[AssignmentRepository] = None,
        workload_repository: Optional[WorkloadRepository] = None,
        rules_repository: Optional[RulesRepository] = None,
        rules_engine: Optional[RulesEngine] = None
    ):
        self.assignment_repository = assignment_repository or AssignmentRepository()
        self.workload_repository = workload_repository or WorkloadRepository()
        self.rules_repository = rules_repository or RulesRepository()
        self.rules_engine = rules_engine or RulesEngine()
        logger.info("AutoAssignmentService initialized")

    async def auto_assign_item(
        self,
        db,
        item_id: UUID,
        item_type: str,
        item_data: Dict[str, Any],
        entity_type: str = "ministry",
        entity_id: Optional[str] = None,
        priority_level: int = 5,
        workflow_code: Optional[str] = None,
        entity_code: Optional[str] = None,
        entity_location_id: Optional[UUID] = None,
        complexity_score: Optional[int] = None,
    ) -> Optional[Assignment]:
        """Automatically assign an item to the best available agent

        Args:
            db: Database connection
            item_id: UUID of the item (tax_declaration, service_request, etc.)
            item_type: Type of item (declaration type or workflow code)
            item_data: Item data for rule evaluation
            entity_type: Entity type for filtering agents
            entity_id: Entity ID (UUID) for filtering agents by entity
            priority_level: Priority 1-10 (default 5)
            workflow_code: Workflow code to determine entity (fallback if no entity_code)
            entity_code: Entity code for deterministic routing (preferred over workflow_code)
            entity_location_id: Specific site UUID for location-based routing (migration 104)
            complexity_score: Computed complexity 0-100 (migration 136). Used for predictive escalation.

        Returns:
            Assignment or None if no agent available

        Note:
            CRITICAL: Prefer entity_code over workflow_code for routing.
            For multi-entity workflows (RESIDENCIA handled by EXTRANJERIA + CNEDOGE),
            workflow_code lookup is nondeterministic. entity_code is authoritative.
        """
        # Get active rules for this entity
        rules = await self.rules_repository.get_active_rules(
            db, entity_type=entity_type, entity_id=entity_id
        )

        # Convert entity_id string to UUID if needed
        entity_uuid = None
        if entity_id:
            try:
                entity_uuid = UUID(entity_id) if isinstance(entity_id, str) else entity_id
            except (ValueError, TypeError):
                logger.warning(f"Invalid entity_id format: {entity_id}")

        # Resolve entity: entity_code (deterministic) > workflow_code (nondeterministic)
        if not entity_uuid and entity_code:
            entity_uuid = await self.workload_repository._get_entity_id_by_code(db, entity_code)
            if entity_uuid:
                logger.info(f"Resolved entity_code '{entity_code}' to entity_id '{entity_uuid}'")

        # Fallback to workflow_code if no entity resolved yet
        effective_workflow = workflow_code or item_type

        # Get available agents filtered by entity + location
        available_agents = await self.workload_repository.get_available_agents(
            db,
            max_workload_pct=get_settings().QUEUE_MAX_WORKLOAD_PCT,
            entity_id=entity_uuid,
            workflow_code=effective_workflow if not entity_uuid else None,
            entity_location_id=entity_location_id,
        )

        if not available_agents:
            logger.warning(f"No available agents for item {item_id}")
            return None

        # Use rules engine first (explicit rules take precedence)
        selected_agent_profile_id = await self.rules_engine.select_best_agent(
            db=db,
            item_type=item_type,
            item_data=item_data,
            rules=rules,
            available_agents=available_agents,
            priority_level=priority_level
        )

        if not selected_agent_profile_id:
            # Multi-criteria scoring (Phase 2 Intelligence)
            # Use complexity_score if available; fallback to priority_level * 10
            effective_complexity = complexity_score if complexity_score is not None else priority_level * 10
            selected_agent_profile_id = await self._score_and_select(
                db=db,
                agents=available_agents,
                workflow_code=effective_workflow,
                entity_location_id=entity_location_id,
                complexity_score=effective_complexity,
                item_id=item_id,
                entity_code=entity_code,
                priority_level=priority_level,
            )

        if not selected_agent_profile_id:
            logger.warning(f"Could not select agent for item {item_id}")
            return None

        # Create assignment with auto method
        assignment_data = AssignmentCreate(
            item_id=item_id,
            item_type=item_type,
            agent_profile_id=selected_agent_profile_id,
            assignment_method=AssignmentMethod.AUTO,
            priority_level=priority_level
        )

        assignment = await self.assignment_repository.create(db, assignment_data, None)
        logger.info(f"Auto-assigned item {item_id} to agent_profile {selected_agent_profile_id}")
        return assignment

    async def _score_and_select(
        self,
        db,
        agents: List[AgentWorkload],
        workflow_code: Optional[str] = None,
        entity_location_id: Optional[UUID] = None,
        complexity_score: int = 50,
        item_id: Optional[UUID] = None,
        entity_code: Optional[str] = None,
        priority_level: int = 5,
    ) -> Optional[UUID]:
        """Multi-criteria scoring: select the most ADAPTED agent, not just least loaded.

        Criteria (configurable weights):
          1. Workload    (30%) — lower capacity_percentage = higher score
          2. Success     (25%) — higher success_rate for this workflow = higher score
          3. Specialization (20%) — workflow in agent.specializations = bonus
          4. Site match  (15%) — matching entity_location_id = bonus
          5. Speed       (10%) — lower avg_processing_hours = higher score

        For new agents with no proficiency data, defaults to neutral scores
        so they still receive assignments and build up history.

        Predictive escalation: for complex items (high complexity_score),
        agents with low success_rate on the workflow get a penalty.
        complexity_score is computed from real signals (workflow weight,
        doc count, payment amount) — NOT from administrative priority_level.
        """
        if not agents:
            return None

        # Single agent: skip scoring overhead
        if len(agents) == 1:
            return agents[0].agent_profile_id

        settings = get_settings()

        agent_ids = [a.agent_profile_id for a in agents]

        # Batch-fetch proficiency data for all agents + this workflow
        prof_map: Dict[UUID, Any] = {}
        if workflow_code:
            proficiencies = await db.fetch("""
                SELECT agent_profile_id, success_rate, avg_processing_hours,
                       completions_total, escalations_total
                FROM agent_workflow_proficiency
                WHERE workflow_code = $1 AND agent_profile_id = ANY($2::uuid[])
            """, workflow_code, agent_ids)
            prof_map = {row["agent_profile_id"]: row for row in proficiencies}

        # Batch-fetch actual entity_location_id for site match scoring
        location_match_set: set = set()
        if entity_location_id:
            matched = await db.fetch("""
                SELECT id FROM agent_profiles
                WHERE id = ANY($1::uuid[])
                  AND entity_location_id = $2
            """, agent_ids, entity_location_id)
            location_match_set = {row["id"] for row in matched}

        scores = []
        for agent in agents:
            prof = prof_map.get(agent.agent_profile_id)

            # 1. Workload (lower capacity = higher score, 0-100 range)
            w_score = (1.0 - min(agent.capacity_percentage, 100.0) / 100.0) * 100.0

            # 2. Success rate for this workflow (0-100)
            if prof and (prof["completions_total"] + prof["escalations_total"]) > 0:
                s_score = float(prof["success_rate"])
            else:
                # New agent: neutral score (doesn't penalize, doesn't boost)
                s_score = settings.SCORING_NEW_AGENT_DEFAULT

            # 3. Specialization: workflow in agent's specializations list
            specs = agent.specializations or []
            spec_score = 100.0 if (workflow_code and workflow_code in specs) else 0.0

            # 4. Site match: agent at the requested location
            if entity_location_id:
                site_score = settings.SCORING_SITE_MATCH if agent.agent_profile_id in location_match_set else 0.0
            else:
                site_score = settings.SCORING_SITE_NEUTRAL  # No location preference — neutral

            # 5. Speed: lower avg_processing_hours = faster = higher score
            if prof and prof["avg_processing_hours"] and prof["completions_total"] > 0:
                avg_h = float(prof["avg_processing_hours"])
            else:
                avg_h = settings.SCORING_SPEED_DEFAULT_HOURS
            speed_max = settings.SCORING_SPEED_MAX_HOURS
            speed_score = max(0.0, (1.0 - min(avg_h, speed_max) / speed_max)) * 100.0

            # Weighted total
            total = (
                settings.SCORING_WEIGHT_WORKLOAD * w_score
                + settings.SCORING_WEIGHT_SUCCESS * s_score
                + settings.SCORING_WEIGHT_SPECIALIZATION * spec_score
                + settings.SCORING_WEIGHT_SITE * site_score
                + settings.SCORING_WEIGHT_SPEED * speed_score
            )

            # Predictive escalation penalty: complex items should avoid
            # agents with low success rate on this workflow.
            # complexity_score (0-100) computed from real signals (migration 136)
            # replaces priority_level which was administrative, not complexity.
            if (
                prof
                and complexity_score >= settings.ESCALATION_PREDICTIVE_COMPLEXITY_THRESHOLD
                and prof["completions_total"] >= settings.ESCALATION_PREDICTIVE_MIN_COMPLETIONS
                and float(prof["success_rate"]) < settings.ESCALATION_PREDICTIVE_SUCCESS_THRESHOLD
            ):
                total *= settings.ANOMALY_UNDERPERFORMER_PENALTY

            scores.append((agent.agent_profile_id, total, agent.current_assignments))

        # Best score wins. Tie-breaker: lowest current_assignments
        scores.sort(key=lambda x: (-x[1], x[2]))

        if not scores:
            return None

        winner = scores[0]

        # LLM-augmented routing: when top candidates are close,
        # use Gemini to break ties with contextual reasoning.
        if (
            settings.FEATURE_LLM_ROUTING_ENABLED
            and len(scores) >= 2
            and item_id is not None
        ):
            gap = scores[0][1] - scores[1][1]
            if gap < settings.LLM_ROUTING_SCORE_GAP_THRESHOLD:
                llm_pick = await self._invoke_llm_routing(
                    db=db,
                    item_id=item_id,
                    workflow_code=workflow_code,
                    entity_code=entity_code or "",
                    complexity_score=complexity_score,
                    priority_level=priority_level,
                    scores=scores,
                    agents=agents,
                    prof_map=prof_map,
                    location_match_set=location_match_set,
                    settings=settings,
                )
                if llm_pick:
                    return llm_pick

        logger.info(
            f"Multi-criteria scoring: selected agent {winner[0]} "
            f"(score={winner[1]:.1f}, assignments={winner[2]}) "
            f"from {len(agents)} candidates for workflow={workflow_code}"
        )
        return winner[0]

    async def _invoke_llm_routing(
        self,
        db,
        item_id: UUID,
        workflow_code: Optional[str],
        entity_code: str,
        complexity_score: int,
        priority_level: int,
        scores: List,
        agents: List[AgentWorkload],
        prof_map: Dict[UUID, Any],
        location_match_set: set,
        settings,
    ) -> Optional[UUID]:
        """Invoke Gemini LLM to break ties between close-scoring candidates.

        Returns selected agent_profile_id if LLM confidence >= threshold,
        otherwise None (caller falls back to deterministic #1).
        """
        from app.modules.assignment.services.llm_routing_service import (
            LLMRoutingCandidate,
            LLMRoutingContext,
            llm_routing_service,
        )

        # Fetch SR metadata for prompt context
        sr_meta = await db.fetchrow("""
            SELECT reference, workflow_code, document_count, payment_amount
            FROM service_requests
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as document_count
                FROM service_request_documents
                WHERE service_request_id = service_requests.id
            ) docs ON true
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(total_amount), 0) as payment_amount
                FROM service_payments
                WHERE service_request_id = service_requests.id
            ) pay ON true
            WHERE service_requests.id = $1
        """, item_id)

        if not sr_meta:
            logger.warning(f"LLM routing: SR {item_id} not found, skipping")
            return None

        context = LLMRoutingContext(
            service_request_id=item_id,
            reference=sr_meta["reference"] or str(item_id)[:8],
            workflow_code=workflow_code or "",
            entity_code=entity_code,
            complexity_score=complexity_score,
            priority_level=priority_level,
            document_count=int(sr_meta["document_count"] or 0),
            payment_amount=float(sr_meta["payment_amount"] or 0),
        )

        # Build candidate list from top-N scored agents
        agent_map = {a.agent_profile_id: a for a in agents}
        top_n = scores[: settings.LLM_ROUTING_MAX_CANDIDATES]
        candidates = []
        for rank, (agent_id, score, assignments) in enumerate(top_n, 1):
            agent = agent_map.get(agent_id)
            if not agent:
                continue
            prof = prof_map.get(agent_id)
            candidate = LLMRoutingCandidate(
                agent_profile_id=agent_id,
                agent_name=agent.agent_name or "Agent",
                deterministic_score=score,
                deterministic_rank=rank,
                current_assignments=assignments,
                max_concurrent_assignments=agent.max_concurrent_assignments or 10,
                capacity_percentage=agent.capacity_percentage,
                specializations=agent.specializations or [],
                site_match=agent_id in location_match_set,
            )
            if prof:
                candidate.workflow_success_rate = float(prof["success_rate"])
                candidate.workflow_completions = int(prof["completions_total"])
                candidate.workflow_escalations = int(prof["escalations_total"])
                if prof["avg_processing_hours"]:
                    candidate.workflow_avg_hours = float(
                        prof["avg_processing_hours"]
                    )
            candidates.append(candidate)

        if len(candidates) < 2:
            return None

        decision = await llm_routing_service.select_agent(context, candidates)

        # Store audit trail regardless of outcome
        await self._store_llm_routing_audit(db, item_id, decision)

        if decision.fallback_used:
            logger.info(
                f"LLM routing fallback for SR {context.reference}: "
                f"{decision.reasoning}"
            )
            return None  # Let caller use deterministic pick

        if decision.confidence < settings.LLM_ROUTING_CONFIDENCE_THRESHOLD:
            logger.info(
                f"LLM routing low confidence ({decision.confidence:.2f}) "
                f"for SR {context.reference}, using deterministic pick"
            )
            return None

        logger.info(
            f"LLM routing override for SR {context.reference}: "
            f"agent={decision.selected_agent_profile_id} "
            f"confidence={decision.confidence:.2f} "
            f"agreed={decision.llm_agreed_with_deterministic}"
        )
        return decision.selected_agent_profile_id

    async def _store_llm_routing_audit(
        self, db, item_id: UUID, decision
    ) -> None:
        """Store LLM routing decision in service_request_history for A/B analysis."""
        try:
            import json

            audit_data = {
                "llm_routing": {
                    "selected_agent_profile_id": str(
                        decision.selected_agent_profile_id
                    ),
                    "reasoning": decision.reasoning,
                    "confidence": decision.confidence,
                    "factors_considered": decision.factors_considered,
                    "llm_agreed_with_deterministic": (
                        decision.llm_agreed_with_deterministic
                    ),
                    "model_used": decision.model_used,
                    "latency_ms": decision.latency_ms,
                    "tokens_input": decision.tokens_input,
                    "tokens_output": decision.tokens_output,
                    "fallback_used": decision.fallback_used,
                }
            }
            await db.execute(
                """
                INSERT INTO service_request_history
                (service_request_id, action, comment, details)
                VALUES ($1, 'assigned', 'LLM routing decision', $2::jsonb)
                """,
                item_id,
                json.dumps(audit_data),
            )
        except Exception as e:
            # Audit failure must never block assignment
            logger.error(f"Failed to store LLM routing audit: {e}")

    def _select_by_load_balance(
        self,
        available_agents: List[AgentWorkload]
    ) -> Optional[UUID]:
        """Select agent with lowest workload (simple fallback).

        Used only when _score_and_select is not applicable.
        """
        if not available_agents:
            return None

        sorted_agents = sorted(
            available_agents,
            key=lambda a: a.current_assignments
        )
        return sorted_agents[0].agent_profile_id

    async def auto_assign(
        self,
        db,
        item_id: UUID,
        item_type: str,
        priority_level: int = 5,
        workflow_code: Optional[str] = None
    ) -> Optional[Assignment]:
        """Simple auto-assign without rule evaluation (backward compatible)

        Args:
            db: Database connection
            item_id: UUID of the item
            item_type: Type of item
            priority_level: Priority 1-10
            workflow_code: Workflow code for entity-based routing

        Note:
            For service_requests, item_type is usually the workflow_code.
            The workflow_code is used to determine which entity's agents
            should receive the assignment (e.g., PASAPORTE_NUEVO -> CNEDOGE_PASAPORTE)
        """
        return await self.auto_assign_item(
            db=db,
            item_id=item_id,
            item_type=item_type,
            item_data={},
            priority_level=priority_level,
            workflow_code=workflow_code or item_type  # Use item_type as fallback
        )

    async def rebalance_assignments(
        self,
        db,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None
    ) -> int:
        """Rebalance workload across agents.

        Delegates to workload_rebalance_service which handles:
        - Overloaded/underloaded detection per entity
        - Mobility scoring (lowest-priority items moved first)
        - Specialization-aware target selection
        - Proper DB updates (assignments + service_requests + history)

        Args:
            db: Database connection
            entity_type: Filter by entity type (optional)
            entity_id: Filter by entity ID (optional)

        Returns:
            Number of assignments rebalanced
        """
        from app.modules.assignment.services.workload_rebalance_service import (
            rebalance_entity_workload,
        )

        entity_uuid = None
        if entity_id:
            try:
                entity_uuid = UUID(entity_id)
            except (ValueError, TypeError):
                pass

        result = await rebalance_entity_workload(
            entity_id=entity_uuid,
            db=db,
            performed_by=None,
        )
        return result["reassignments_made"]


def get_auto_assignment_service(
    assignment_repo: AssignmentRepository = Depends(get_assignment_repository),
    workload_repo: WorkloadRepository = Depends(get_workload_repository),
    rules_repo: RulesRepository = Depends(get_rules_repository),
    rules_engine: RulesEngine = Depends(get_rules_engine)
) -> AutoAssignmentService:
    """Dependency injection for AutoAssignmentService"""
    return AutoAssignmentService(assignment_repo, workload_repo, rules_repo, rules_engine)
