"""
LLM Routing Service — Gemini-augmented agent selection for ambiguous assignments.

Called by _score_and_select() when the gap between top candidates is below threshold.
Uses structured JSON output from Gemini to select among close-scoring agents.

Design principles:
- NEVER blocks if Gemini fails (graceful degradation to deterministic pick)
- NEVER overrides clear winners (only invoked when scores are close)
- Structured output (JSON) with schema validation
- Full audit trail in service_request_history.details JSONB
- Token tracking for cost monitoring
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from loguru import logger

from app.config import get_settings
from app.core.ai_telemetry import traced_generate_sync

from app.modules.shared.services.vertex_ai_manager import (
    VERTEX_AI_AVAILABLE,
    VertexAIManager,
)

if VERTEX_AI_AVAILABLE:
    from vertexai.generative_models import GenerationConfig


@dataclass
class LLMRoutingCandidate:
    """Data sent to LLM for each candidate agent."""

    agent_profile_id: UUID
    agent_name: str
    deterministic_score: float
    deterministic_rank: int
    current_assignments: int
    max_concurrent_assignments: int
    capacity_percentage: float
    specializations: List[str] = field(default_factory=list)
    workflow_success_rate: Optional[float] = None
    workflow_completions: Optional[int] = None
    workflow_escalations: Optional[int] = None
    workflow_avg_hours: Optional[float] = None
    site_match: bool = False


@dataclass
class LLMRoutingContext:
    """Service request context sent to LLM."""

    service_request_id: UUID
    reference: str
    workflow_code: str
    entity_code: str
    complexity_score: int = 50
    priority_level: int = 5
    document_count: int = 0
    payment_amount: float = 0.0


@dataclass
class LLMRoutingDecision:
    """Structured result from LLM routing."""

    selected_agent_profile_id: UUID
    reasoning: str
    confidence: float
    factors_considered: List[str] = field(default_factory=list)
    llm_agreed_with_deterministic: bool = True
    model_used: str = ""
    latency_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    fallback_used: bool = False


SYSTEM_PROMPT = """You are an agent assignment optimizer for a government fiscal services platform.
Your task: given a service request and a list of candidate agents with their metrics,
select the BEST agent for this specific request.

DECISION CRITERIA (in order of importance):
1. SPECIALIZATION MATCH: Agents who specialize in this workflow type should be preferred.
2. SUCCESS RATE: Higher success rate on this workflow = lower chance of escalation.
3. WORKLOAD BALANCE: Prefer agents with lower current capacity usage, but do NOT pick
   an agent solely because they are less busy if they lack specialization.
4. PROCESSING SPEED: Faster average processing = better citizen experience.
5. COMPLEXITY FIT: For high-complexity requests (complexity_score > 60), strongly prefer
   agents with proven track record (completions > 5, success_rate > 80%).

CONSTRAINTS:
- You MUST select one of the provided candidate agents (by their agent_profile_id).
- Do NOT invent agent IDs.
- Provide your reasoning in 1-3 sentences.
- Return confidence 0.0-1.0 (how certain you are this is the right choice).

RESPOND ONLY WITH VALID JSON matching this exact schema:
{
  "selected_agent_profile_id": "uuid-string",
  "reasoning": "Brief explanation of why this agent was selected.",
  "confidence": 0.85,
  "factors_considered": ["specialization_match", "high_success_rate", "low_workload"]
}"""


class LLMRoutingService:
    """Gemini-augmented agent selection service."""

    def __init__(self):
        self._model: Optional[GenerativeModel] = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of Gemini model via VertexAIManager singleton."""
        if self._initialized:
            return

        manager = VertexAIManager()
        if not manager.is_available:
            self._initialized = True
            return

        try:
            settings = get_settings()
            self._model = manager.create_model(settings.LLM_ROUTING_MODEL)
            self._initialized = True
            logger.info(
                f"LLM Routing Service initialized via VertexAIManager "
                f"(model={settings.LLM_ROUTING_MODEL})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM Routing Service: {e}")
            self._initialized = True

    async def select_agent(
        self,
        context: LLMRoutingContext,
        candidates: List[LLMRoutingCandidate],
    ) -> LLMRoutingDecision:
        """
        Ask Gemini to select the best agent from candidates.

        Returns LLMRoutingDecision. On any failure, returns decision with
        fallback_used=True pointing to the deterministic #1 pick.
        """
        self._ensure_initialized()
        settings = get_settings()
        start_time = time.monotonic()

        deterministic_pick = min(
            candidates, key=lambda c: c.deterministic_rank
        )

        if not self._model:
            return self._make_fallback(
                deterministic_pick, start_time, "Gemini model not available"
            )

        prompt = self._build_prompt(context, candidates)

        try:
            response = await asyncio.wait_for(
                traced_generate_sync(
                    self._model, prompt,
                    feature="routing",
                    generation_config=GenerationConfig(
                        temperature=settings.LLM_ROUTING_TEMPERATURE,
                        max_output_tokens=settings.LLM_ROUTING_MAX_TOKENS,
                        response_mime_type="application/json",
                    ),
                ),
                timeout=settings.LLM_ROUTING_TIMEOUT_SECONDS,
            )

            # Track token usage via centralized manager
            VertexAIManager().track_usage(response, "LLMRoutingService")
            VertexAIManager().track_success()

            decision = self._parse_response(
                response, candidates, deterministic_pick, start_time
            )

            logger.info(
                f"LLM routing: agent={decision.selected_agent_profile_id} "
                f"confidence={decision.confidence:.2f} "
                f"agreed={decision.llm_agreed_with_deterministic} "
                f"latency={decision.latency_ms}ms "
                f"tokens={decision.tokens_input}/{decision.tokens_output}"
            )
            return decision

        except asyncio.TimeoutError:
            VertexAIManager().track_failure()
            logger.warning(
                f"LLM routing timeout ({settings.LLM_ROUTING_TIMEOUT_SECONDS}s) "
                f"for SR {context.reference}"
            )
            return self._make_fallback(
                deterministic_pick, start_time, "Gemini timeout"
            )
        except Exception as e:
            VertexAIManager().track_failure()
            logger.error(
                f"LLM routing error for SR {context.reference}: {e}"
            )
            return self._make_fallback(
                deterministic_pick, start_time, f"Gemini error: {str(e)[:200]}"
            )

    def _build_prompt(
        self,
        context: LLMRoutingContext,
        candidates: List[LLMRoutingCandidate],
    ) -> str:
        """Build the routing prompt with context and candidates."""
        candidates_text = []
        for c in candidates:
            if c.workflow_completions is not None:
                prof_text = (
                    f"Workflow success rate: {c.workflow_success_rate:.1f}%, "
                    f"Completions: {c.workflow_completions}, "
                    f"Escalations: {c.workflow_escalations}, "
                    f"Avg processing: "
                    f"{c.workflow_avg_hours:.1f}h"
                    if c.workflow_avg_hours
                    else "N/A"
                )
            else:
                prof_text = "No workflow-specific data (new agent)"

            candidates_text.append(
                f"- Agent ID: {c.agent_profile_id}\n"
                f"  Name: {c.agent_name}\n"
                f"  Deterministic score: {c.deterministic_score:.1f} "
                f"(rank #{c.deterministic_rank})\n"
                f"  Current load: {c.current_assignments}/"
                f"{c.max_concurrent_assignments} "
                f"({c.capacity_percentage:.0f}%)\n"
                f"  Specializations: "
                f"{', '.join(c.specializations) if c.specializations else 'None'}\n"
                f"  Site match: {'Yes' if c.site_match else 'No'}\n"
                f"  {prof_text}"
            )

        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"SERVICE REQUEST:\n"
            f"- Reference: {context.reference}\n"
            f"- Workflow: {context.workflow_code}\n"
            f"- Entity: {context.entity_code}\n"
            f"- Complexity score: {context.complexity_score}/100\n"
            f"- Priority level: {context.priority_level}/10\n"
            f"- Documents uploaded: {context.document_count}\n"
            f"- Payment amount: {context.payment_amount:,.0f} XAF\n\n"
            f"CANDIDATE AGENTS ({len(candidates)}):\n"
            + "\n".join(candidates_text)
            + "\n\nSelect the best agent. Respond with JSON only."
        )

    def _parse_response(
        self,
        response,
        candidates: List[LLMRoutingCandidate],
        deterministic_pick: LLMRoutingCandidate,
        start_time: float,
    ) -> LLMRoutingDecision:
        """Parse and validate the Gemini JSON response."""
        latency_ms = int((time.monotonic() - start_time) * 1000)
        settings = get_settings()

        tokens_input = 0
        tokens_output = 0
        if hasattr(response, "usage_metadata"):
            um = response.usage_metadata
            tokens_input = getattr(um, "prompt_token_count", 0) or 0
            tokens_output = getattr(um, "candidates_token_count", 0) or 0

        try:
            result = json.loads(response.text)
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.warning(
                f"LLM returned non-JSON: {str(response.text)[:200]}"
            )
            return self._make_fallback(
                deterministic_pick, start_time, f"JSON parse error: {e}"
            )

        selected_id_str = result.get("selected_agent_profile_id")
        reasoning = result.get("reasoning", "No reasoning provided")
        confidence = float(result.get("confidence", 0.0))
        factors = result.get("factors_considered", [])

        if not selected_id_str:
            return self._make_fallback(
                deterministic_pick,
                start_time,
                "Missing selected_agent_profile_id",
            )

        try:
            selected_id = UUID(selected_id_str)
        except ValueError:
            return self._make_fallback(
                deterministic_pick,
                start_time,
                f"Invalid UUID: {selected_id_str}",
            )

        valid_ids = {c.agent_profile_id for c in candidates}
        if selected_id not in valid_ids:
            logger.warning(
                f"LLM selected agent {selected_id} not in candidates"
            )
            return self._make_fallback(
                deterministic_pick,
                start_time,
                f"Agent {selected_id} not in candidate set",
            )

        confidence = max(0.0, min(1.0, confidence))

        return LLMRoutingDecision(
            selected_agent_profile_id=selected_id,
            reasoning=reasoning,
            confidence=confidence,
            factors_considered=factors,
            llm_agreed_with_deterministic=(
                selected_id == deterministic_pick.agent_profile_id
            ),
            model_used=settings.LLM_ROUTING_MODEL,
            latency_ms=latency_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            fallback_used=False,
        )

    def _make_fallback(
        self,
        deterministic_pick: LLMRoutingCandidate,
        start_time: float,
        reason: str,
    ) -> LLMRoutingDecision:
        """Create a fallback decision using the deterministic #1 pick."""
        latency_ms = int((time.monotonic() - start_time) * 1000)
        settings = get_settings()
        return LLMRoutingDecision(
            selected_agent_profile_id=deterministic_pick.agent_profile_id,
            reasoning=f"Deterministic fallback: {reason}",
            confidence=0.0,
            factors_considered=["deterministic_fallback"],
            llm_agreed_with_deterministic=True,
            model_used=settings.LLM_ROUTING_MODEL,
            latency_ms=latency_ms,
            tokens_input=0,
            tokens_output=0,
            fallback_used=True,
        )


# Singleton
llm_routing_service = LLMRoutingService()
