"""
DynamicAnalystService — Single dynamic agent class that loads tools from ToolRegistry.

Replaces the need for N hardcoded *AnalystService classes. Given an agent_type
and entity context, it loads the correct functions, prompt, and artifacts builder
from the ToolRegistry.

For A2A (agent-to-agent) orchestrator pattern:
  - Sub-agent meta-functions are generated dynamically as Gemini FunctionDeclarations
  - Each meta-function delegates to a sub-agent DynamicAnalystService instance
  - The orchestrator synthesizes sub-agent responses into a consolidated analysis

Usage:
    service = create_analyst("treasury", entity_context)
    result = await service.process_question(db, "Ingresos del mes?", context=ctx)
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.core.jsonb import ensure_list
from app.modules.shared.services.base_analyst_service import (
    BaseAnalystService,
    DAYS_ES,
    VERTEX_AI_AVAILABLE,
)
from app.modules.shared.services.tool_registry import (
    ToolSet,
    SubAgentConfig,
    tool_registry,
)

if VERTEX_AI_AVAILABLE:
    from vertexai.generative_models import FunctionDeclaration


# Agent types that use IntentCategory ML classification
_ML_INTENT_AGENT_TYPES = frozenset({"treasury", "admin"})

# Alias for backward compatibility within this module
_DAYS_ES = DAYS_ES


class DynamicAnalystService(BaseAnalystService):
    """Dynamic agent that loads configuration from ToolRegistry at instantiation.

    Supports 3 modes:
      1. Direct: agent_type with SQL functions (treasury, admin, supervisor)
      2. A2A: orchestrator with sub-agent meta-functions
      3. Mixed: direct functions + sub-agent delegation (future)
    """

    def __init__(
        self,
        agent_type: str,
        entity_context: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            agent_type: Registered agent type (treasury, admin, supervisor, orchestrator).
            entity_context: Optional dict with entity-specific data for prompt templates:
                - entity_name: str
                - site_name: str
                - city: str
                - workflow_codes: list[str]
                - agent_count: int
                - available_count: int
                - entity_code: str
                - entity_location_id: str
                - is_main_office: bool
        """
        super().__init__()
        self._agent_type = agent_type
        self._entity_ctx = entity_context or {}
        self._tool_set: ToolSet = tool_registry.get(agent_type)

        # For A2A: build meta-functions if sub_agents are configured
        self._a2a_function_declarations: List[Any] = []
        self._a2a_function_map: Dict[str, Callable] = {}
        if self._tool_set.sub_agents:
            self._build_a2a_functions()

    # ── BaseAnalystService interface ──────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        """Return system prompt, using prompt_fn or template with entity context."""
        ts = self._tool_set

        # Priority 1: prompt_fn (complex prompt generation, e.g. treasury date injection)
        if ts.prompt_fn is not None:
            return ts.prompt_fn(self._entity_ctx)

        # Priority 2: template with placeholders
        template = ts.prompt_template
        if not template:
            return f"You are an AI assistant for agent type '{self._agent_type}'."

        # Inject current date into all templates
        now = datetime.now(timezone.utc)
        ctx = {
            "current_date": now.strftime("%Y-%m-%d"),
            "day_of_week": _DAYS_ES[now.weekday()],
            **self._entity_ctx,
        }

        # Format workflow_list from workflow_codes array
        if "workflow_list" not in ctx and "workflow_codes" in ctx:
            codes = ctx.get("workflow_codes", [])
            ctx["workflow_list"] = "\n".join(f"  - {code}" for code in codes) if codes else "  (ninguno)"

        # Safe format: ignore missing placeholders
        try:
            return template.format(**ctx)
        except KeyError as e:
            logger.warning(f"DynamicAnalystService: prompt template missing key {e}")
            # Fallback: fill missing with defaults
            for key in ("entity_name", "site_name", "city", "workflow_list",
                        "agent_count", "available_count"):
                ctx.setdefault(key, "N/A")
            try:
                return template.format(**ctx)
            except Exception:
                return template

    def _get_function_declarations(self) -> list:
        """Return Gemini FunctionDeclaration list from registry + A2A meta-functions."""
        direct_decls = self._tool_set.function_declarations or []
        return direct_decls + self._a2a_function_declarations

    def _get_function_map(self) -> Dict[str, Callable]:
        """Return function dispatch map from registry + A2A meta-functions."""
        direct_map = dict(self._tool_set.function_map)  # Copy to avoid mutation
        direct_map.update(self._a2a_function_map)
        return direct_map

    def _get_agent_type(self) -> str:
        """Return agent type for query logging."""
        return self._agent_type

    def _get_service_name(self) -> str:
        """Human-readable name for logging."""
        return self._tool_set.agent_type_label or f"Dynamic({self._agent_type})"

    def _get_max_tool_rounds(self) -> int:
        return min(self._tool_set.max_tool_rounds, 3)

    def _is_thinking_enabled(self) -> bool:
        return self._tool_set.thinking_enabled

    def _is_self_reflection_enabled(self) -> bool:
        return self._tool_set.self_reflection_enabled

    def _get_second_call_max_tokens(self) -> int:
        return self._tool_set.second_call_max_tokens

    def _build_artifacts(self, tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Delegate to registry's artifacts builder if available."""
        if self._tool_set.artifacts_builder:
            try:
                return self._tool_set.artifacts_builder(tool_results)
            except Exception as exc:
                logger.warning(f"DynamicAnalystService: artifacts build failed: {exc}")
        return []

    @property
    def uses_ml_intent(self) -> bool:
        """Whether this agent type uses IntentCategory ML classification."""
        return self._agent_type in _ML_INTENT_AGENT_TYPES

    # ── A2A: Agent-to-Agent meta-function generation ─────────────────────────

    def _build_a2a_functions(self) -> None:
        """Generate Gemini FunctionDeclarations and callables for sub-agent delegation.

        For each sub-agent in the ToolSet, creates:
          1. A FunctionDeclaration for Gemini (name, description, parameters)
          2. An async callable that instantiates a sub-agent and delegates the question
        """
        if not VERTEX_AI_AVAILABLE:
            return

        for fn_name, sub_config in self._tool_set.sub_agents.items():
            # Build FunctionDeclaration
            params = {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "La pregunta a enviar al sub-agente especializado.",
                    },
                },
                "required": ["question"],
            }
            if sub_config.requires_entity_code:
                params["properties"]["entity_code"] = {
                    "type": "string",
                    "description": (
                        "Código de la entidad a consultar. "
                        "Ejemplos: CNEDOGE_PASAPORTE, DGT, MINFP, ONRC, POLICIA, OFIVE, ITV."
                    ),
                }
                params["required"].append("entity_code")

            decl = FunctionDeclaration(
                name=fn_name,
                description=sub_config.description,
                parameters=params,
            )
            self._a2a_function_declarations.append(decl)

            # Build async callable (closure captures sub_config)
            self._a2a_function_map[fn_name] = self._make_a2a_handler(
                fn_name, sub_config
            )

        logger.debug(
            f"DynamicAnalystService(orchestrator): built {len(self._a2a_function_declarations)} "
            f"A2A meta-functions: {list(self._tool_set.sub_agents.keys())}"
        )

    def _make_a2a_handler(
        self, fn_name: str, sub_config: SubAgentConfig
    ) -> Callable:
        """Create an async handler that delegates to a sub-agent.

        The handler:
          1. Creates a DynamicAnalystService for the target agent_type
          2. Calls process_question with the sub-question
          3. Returns the sub-agent's answer + data as a dict (for Gemini to synthesize)
        """
        async def _handler(db, question: str = "", entity_code: str = "", **kwargs) -> Dict[str, Any]:
            """A2A delegation handler — calls sub-agent and returns its response."""
            target_type = sub_config.target_agent_type

            # Build entity context for the sub-agent
            sub_entity_ctx = dict(self._entity_ctx)  # Inherit orchestrator context
            if entity_code:
                # Override entity context for entity-specific sub-agents
                sub_entity_ctx = await _load_entity_context(db, entity_code)
                if not sub_entity_ctx:
                    return {
                        "error": f"Entidad '{entity_code}' no encontrada.",
                        "answer": f"No se encontró la entidad con código '{entity_code}'.",
                    }

            try:
                # Create sub-agent dynamically
                sub_agent = DynamicAnalystService(target_type, sub_entity_ctx)

                # Build sub-agent context
                sub_context: Dict[str, Any] = {}
                if sub_entity_ctx.get("entity_code"):
                    sub_context["entity_code"] = sub_entity_ctx["entity_code"]
                if sub_entity_ctx.get("entity_location_id"):
                    sub_context["entity_location_id"] = sub_entity_ctx["entity_location_id"]
                if sub_entity_ctx.get("is_main_office") is not None:
                    sub_context["is_main_office"] = sub_entity_ctx["is_main_office"]

                # Delegate question
                result = await sub_agent.process_question(db, question, context=sub_context)

                return {
                    "agent": target_type,
                    "entity_code": entity_code or sub_entity_ctx.get("entity_code", "N/A"),
                    "answer": result.get("answer", "Sin respuesta"),
                    "tools_used": result.get("tools_used", []),
                    "data_summary": _summarize_data(result.get("data", {})),
                }

            except Exception as exc:
                logger.error(f"A2A delegation to {target_type} failed: {exc}")
                return {
                    "error": str(exc),
                    "answer": f"Error al consultar al agente {target_type}: {exc}",
                }

        return _handler


# ── Helper: Load entity context from DB ──────────────────────────────────────

async def _load_entity_context(db, entity_code: str) -> Optional[Dict[str, Any]]:
    """Load entity context from DB for a given entity_code.

    Used by A2A orchestrator to build context for entity-specific sub-agents.
    Includes agent_count and available_count for accurate prompt rendering.
    """
    try:
        row = await db.fetchrow("""
            SELECT e.id, e.code, e.name, e.workflow_codes
            FROM entities e
            WHERE e.code = $1 AND e.is_active = true
        """, entity_code)

        if not row:
            return None

        # Count agents for this entity (for supervisor prompt accuracy)
        counts = await db.fetchrow("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (
                       WHERE aw.availability = 'available' OR aw.availability IS NULL
                   ) AS available
            FROM agent_profiles ap
            LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
            WHERE ap.entity_id = $1 AND ap.is_active = true
        """, row["id"])

        now = datetime.now(timezone.utc)
        return {
            "entity_code": row["code"],
            "entity_name": row["name"],
            "workflow_codes": ensure_list(row["workflow_codes"]),
            "site_name": "Todos los sitios",
            "city": "",
            "is_main_office": True,  # Orchestrator = global view
            "agent_count": counts["total"] or 0,
            "available_count": counts["available"] or 0,
            "current_date": now.strftime("%Y-%m-%d"),
            "day_of_week": _DAYS_ES[now.weekday()],
        }
    except Exception as exc:
        logger.warning(f"_load_entity_context({entity_code}) failed: {exc}")
        return None


def _summarize_data(data: Dict[str, Any]) -> str:
    """Create a brief text summary of sub-agent data for the orchestrator.

    Keeps it short — the orchestrator only needs key figures, not raw tables.
    """
    if not data:
        return "Sin datos"

    parts = []
    for key, value in list(data.items())[:5]:  # Cap at 5 tool results
        if isinstance(value, dict):
            # Extract key metrics
            metrics = []
            for k, v in list(value.items())[:8]:
                if isinstance(v, (int, float)):
                    metrics.append(f"{k}={v}")
                elif isinstance(v, str) and len(v) < 50:
                    metrics.append(f"{k}={v}")
            if metrics:
                parts.append(f"{key}: {', '.join(metrics)}")
        elif isinstance(value, list):
            parts.append(f"{key}: {len(value)} items")
    return "; ".join(parts) if parts else "Datos disponibles"


# ── Factory function ─────────────────────────────────────────────────────────

def create_analyst(
    agent_type: str,
    entity_context: Optional[Dict[str, Any]] = None,
) -> DynamicAnalystService:
    """Factory: create a DynamicAnalystService for the given agent_type.

    Args:
        agent_type: One of 'treasury', 'admin', 'supervisor', 'orchestrator'.
        entity_context: Entity-specific context for prompt templates.

    Returns:
        DynamicAnalystService ready to call process_question().

    Raises:
        KeyError: If agent_type is not registered in the ToolRegistry.
    """
    return DynamicAnalystService(agent_type, entity_context)
