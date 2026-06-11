"""
Assignment Feedback Service — Records completion/escalation outcomes.

Updates agent_workflow_proficiency (per-workflow metrics) and
agent_workloads (global metrics). Auto-manages specializations
based on completion thresholds.

Called by agent_queue_service after complete_item / escalate_item.
All operations are non-blocking: callers wrap in try/except.
"""

import json
from typing import Optional, Union
from uuid import UUID

from loguru import logger


class AssignmentFeedbackService:
    """Records assignment outcomes and updates proficiency metrics."""

    async def record_completion(
        self,
        db,
        agent_profile_id: Union[UUID, str],
        workflow_code: str,
        processing_hours: float,
    ) -> Optional[dict]:
        """
        Record a successful completion for an agent on a workflow.

        1. UPSERT agent_workflow_proficiency (per-workflow metrics)
        2. UPDATE agent_workloads (global rolling metrics)
        3. Auto-add specialization if threshold met
        """
        if not agent_profile_id or not workflow_code:
            return None

        # Cap processing_hours to reasonable bounds (avoid outliers skewing avg)
        processing_hours = max(0.0, min(processing_hours, 720.0))  # 0 to 30 days

        # 1. UPSERT proficiency
        proficiency = await db.fetchrow("""
            INSERT INTO agent_workflow_proficiency (
                agent_profile_id, workflow_code,
                completions_total, escalations_total,
                success_rate, avg_processing_hours,
                last_completed_at, updated_at
            ) VALUES ($1, $2, 1, 0, 100.0, $3, NOW(), NOW())
            ON CONFLICT (agent_profile_id, workflow_code) DO UPDATE SET
                completions_total = agent_workflow_proficiency.completions_total + 1,
                success_rate = (
                    (agent_workflow_proficiency.completions_total + 1)::numeric
                    / NULLIF(
                        agent_workflow_proficiency.completions_total + 1
                        + agent_workflow_proficiency.escalations_total, 0
                    )
                ) * 100,
                avg_processing_hours = CASE
                    WHEN agent_workflow_proficiency.completions_total = 0 THEN $3
                    ELSE (
                        agent_workflow_proficiency.avg_processing_hours
                        * agent_workflow_proficiency.completions_total + $3
                    ) / (agent_workflow_proficiency.completions_total + 1)
                END,
                last_completed_at = NOW(),
                updated_at = NOW()
            RETURNING *
        """, agent_profile_id, workflow_code, processing_hours)

        # 2. Update global agent_workloads metrics
        await self._update_global_workload_metrics(db, agent_profile_id)

        # 3. Auto-specialization check
        if proficiency:
            await self._check_add_specialization(
                db, agent_profile_id, workflow_code,
                proficiency["completions_total"],
                proficiency["success_rate"],
            )

        logger.debug(
            f"Feedback: completion recorded agent={agent_profile_id} "
            f"workflow={workflow_code} hours={processing_hours:.1f} "
            f"total={proficiency['completions_total'] if proficiency else '?'}"
        )
        return dict(proficiency) if proficiency else None

    async def record_escalation(
        self,
        db,
        agent_profile_id: Union[UUID, str],
        workflow_code: str,
    ) -> Optional[dict]:
        """
        Record an escalation (agent could not complete the item).

        1. UPSERT agent_workflow_proficiency
        2. UPDATE agent_workloads (global)
        3. Auto-remove specialization if performance drops below threshold
        """
        if not agent_profile_id or not workflow_code:
            return None

        # 1. UPSERT proficiency
        proficiency = await db.fetchrow("""
            INSERT INTO agent_workflow_proficiency (
                agent_profile_id, workflow_code,
                completions_total, escalations_total,
                success_rate, avg_processing_hours,
                last_escalated_at, updated_at
            ) VALUES ($1, $2, 0, 1, 0.0, 0.0, NOW(), NOW())
            ON CONFLICT (agent_profile_id, workflow_code) DO UPDATE SET
                escalations_total = agent_workflow_proficiency.escalations_total + 1,
                success_rate = (
                    agent_workflow_proficiency.completions_total::numeric
                    / NULLIF(
                        agent_workflow_proficiency.completions_total
                        + agent_workflow_proficiency.escalations_total + 1, 0
                    )
                ) * 100,
                last_escalated_at = NOW(),
                updated_at = NOW()
            RETURNING *
        """, agent_profile_id, workflow_code)

        # 2. Update global agent_workloads metrics
        await self._update_global_workload_metrics(db, agent_profile_id)

        # 3. Check if specialization should be removed
        if proficiency:
            await self._check_remove_specialization(
                db, agent_profile_id, workflow_code,
                proficiency["completions_total"],
                proficiency["success_rate"],
            )

        logger.debug(
            f"Feedback: escalation recorded agent={agent_profile_id} "
            f"workflow={workflow_code} "
            f"escalations={proficiency['escalations_total'] if proficiency else '?'}"
        )
        return dict(proficiency) if proficiency else None

    async def _update_global_workload_metrics(self, db, agent_profile_id: str):
        """
        Recalculate global success_rate and avg_processing_time_hours
        on agent_workloads from agent_workflow_proficiency aggregates.
        """
        await db.execute("""
            UPDATE agent_workloads SET
                success_rate = COALESCE(agg.global_success_rate, 0),
                avg_processing_time_hours = COALESCE(agg.global_avg_hours, 0),
                last_updated_at = NOW()
            FROM (
                SELECT
                    agent_profile_id,
                    CASE
                        WHEN SUM(completions_total) + SUM(escalations_total) = 0 THEN 0
                        ELSE (SUM(completions_total)::numeric
                              / (SUM(completions_total) + SUM(escalations_total))) * 100
                    END AS global_success_rate,
                    CASE
                        WHEN SUM(completions_total) = 0 THEN 0
                        ELSE SUM(avg_processing_hours * completions_total)
                             / SUM(completions_total)
                    END AS global_avg_hours
                FROM agent_workflow_proficiency
                WHERE agent_profile_id = $1
                GROUP BY agent_profile_id
            ) agg
            WHERE agent_workloads.agent_profile_id = $1
        """, agent_profile_id)

    async def _check_add_specialization(
        self, db, agent_profile_id: str, workflow_code: str,
        completions_total: int, success_rate: float,
    ):
        """Auto-add workflow to agent specializations if threshold met."""
        from app.config import get_settings
        settings = get_settings()

        if completions_total < settings.SPECIALIZATION_THRESHOLD:
            return

        row = await db.fetchrow(
            "SELECT specializations FROM agent_profiles WHERE id = $1",
            agent_profile_id,
        )
        if not row:
            return

        raw = row["specializations"]
        specs = _parse_specializations(raw)

        if workflow_code not in specs:
            specs.append(workflow_code)
            await db.execute(
                "UPDATE agent_profiles SET specializations = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps(specs), agent_profile_id,
            )
            logger.info(
                f"Auto-specialization: agent {agent_profile_id} gained "
                f"'{workflow_code}' (completions={completions_total})"
            )

    async def _check_remove_specialization(
        self, db, agent_profile_id: str, workflow_code: str,
        completions_total: int, success_rate: float,
    ):
        """Auto-remove workflow from specializations if performance drops."""
        from app.config import get_settings
        settings = get_settings()

        # Only remove if agent has enough data AND success rate is poor
        if completions_total < settings.ESCALATION_PREDICTIVE_MIN_COMPLETIONS:
            return
        if success_rate >= settings.SPECIALIZATION_REMOVE_THRESHOLD:
            return

        row = await db.fetchrow(
            "SELECT specializations FROM agent_profiles WHERE id = $1",
            agent_profile_id,
        )
        if not row:
            return

        raw = row["specializations"]
        specs = _parse_specializations(raw)

        if workflow_code in specs:
            specs.remove(workflow_code)
            await db.execute(
                "UPDATE agent_profiles SET specializations = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps(specs), agent_profile_id,
            )
            logger.warning(
                f"Auto-specialization removed: agent {agent_profile_id} lost "
                f"'{workflow_code}' (success_rate={success_rate:.1f}%, "
                f"threshold={settings.SPECIALIZATION_REMOVE_THRESHOLD}%)"
            )


def _parse_specializations(raw) -> list:
    """Parse specializations from JSONB (handles str, list, None)."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(raw, list):
        return list(raw)  # Copy to avoid mutation
    return []


# Singleton
feedback_service = AssignmentFeedbackService()
