"""
ToolRegistry — Dynamic agent tool configuration registry.

Architecture: ToolRegistry holds per-agent-type configurations (functions, prompts,
artifacts builders). DynamicAnalystService loads a ToolSet from the registry
at instantiation time, avoiding N hardcoded service classes.

Supports 3 dispatch patterns:
  1. Direct tools: agent_type -> ToolSet with SQL functions (treasury, admin, supervisor)
  2. Agent-to-Agent (A2A): orchestrator calls sub-agents via meta-functions
  3. Composite: mix of direct tools + sub-agent delegation

Registry is populated at module import time (lazy imports avoid circular deps).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


@dataclass
class ToolSet:
    """Configuration for a single agent type.

    Attributes:
        function_declarations: List of Gemini FunctionDeclaration objects.
        function_map: Dict mapping function names to async callables (db, **kwargs) -> dict.
        prompt_template: Static prompt string OR template with {placeholders} for dynamic agents.
        prompt_fn: Optional callable(entity_context) -> str for complex prompt generation.
            If provided, takes precedence over prompt_template.
        artifacts_builder: Optional callable(tool_results) -> List[dict] for rich data viz.
        max_tool_rounds: Maximum Gemini tool-calling rounds (default 2, max 3).
        second_call_max_tokens: Max output tokens for the analysis call.
        agent_type_label: Human-readable label for logging.
        sub_agents: Dict of sub-agent configs for A2A pattern.
            Each key = meta-function name, value = SubAgentConfig.
    """
    function_declarations: list = field(default_factory=list)
    function_map: Dict[str, Callable] = field(default_factory=dict)
    prompt_template: str = ""
    prompt_fn: Optional[Callable] = None
    artifacts_builder: Optional[Callable] = None
    max_tool_rounds: int = 2
    second_call_max_tokens: int = 2048
    agent_type_label: str = ""
    sub_agents: Dict[str, "SubAgentConfig"] = field(default_factory=dict)
    process_fn: Optional[Callable] = None  # async(question, context) -> dict
    # For agents without function-calling pattern (RAG, batch, briefing, routing).
    # If present, DynamicAnalystService/orchestrator can delegate via process_fn.
    thinking_enabled: bool = True  # Enable thinking budget on final round (disable for batch/routing)
    self_reflection_enabled: bool = False  # Self-evaluate response quality (enable for reasoning agents)


@dataclass
class SubAgentConfig:
    """Configuration for a sub-agent in A2A pattern.

    The orchestrator's meta-function delegates to a sub-agent by calling
    DynamicAnalystService(target_agent_type, entity_context).process_question().

    Attributes:
        target_agent_type: The agent_type to delegate to (must be registered).
        description: Description for Gemini FunctionDeclaration (routing hint).
        requires_entity_code: If True, Gemini must provide entity_code parameter.
    """
    target_agent_type: str
    description: str
    requires_entity_code: bool = False


class ToolRegistry:
    """Singleton registry of agent tool configurations.

    Process-safe: each uvicorn worker gets its own registry instance.
    Lazy loading: actual function imports happen on first access.
    Not thread-safe — relies on Python GIL + single-threaded asyncio event loop.
    """

    _instance: Optional["ToolRegistry"] = None
    _registry: Dict[str, ToolSet] = {}
    _initialized: bool = False

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, agent_type: str, tool_set: ToolSet) -> None:
        """Register a ToolSet for an agent type. Overwrites if exists."""
        self._registry[agent_type] = tool_set
        logger.debug(
            f"ToolRegistry: registered '{agent_type}' "
            f"({len(tool_set.function_declarations)} functions"
            f"{', ' + str(len(tool_set.sub_agents)) + ' sub-agents' if tool_set.sub_agents else ''})"
        )

    def get(self, agent_type: str) -> ToolSet:
        """Get ToolSet for an agent type. Raises KeyError if not found."""
        self._ensure_initialized()
        if agent_type not in self._registry:
            available = list(self._registry.keys())
            raise KeyError(
                f"Unknown agent_type '{agent_type}'. "
                f"Available: {available}"
            )
        return self._registry[agent_type]

    def list_agent_types(self) -> List[str]:
        """List all registered agent types."""
        self._ensure_initialized()
        return list(self._registry.keys())

    def has(self, agent_type: str) -> bool:
        """Check if an agent type is registered."""
        self._ensure_initialized()
        return agent_type in self._registry

    def _ensure_initialized(self) -> None:
        """Lazy initialization — register all agent types on first access."""
        if self._initialized:
            return
        self._initialized = True
        _register_all_agents(self)


# ── Module-level singleton ────────────────────────────────────────────────────

tool_registry = ToolRegistry()


# ── Lazy registration (avoids circular imports) ──────────────────────────────

def _register_all_agents(registry: ToolRegistry) -> None:
    """Register all known agent types. Called once on first registry access."""
    # Function-calling agents (BaseAnalystService pattern)
    _register_treasury(registry)
    _register_admin(registry)
    _register_supervisor(registry)
    _register_entity_agent(registry)
    _register_orchestrator(registry)
    # Non-function-calling agents (process_fn pattern)
    _register_chatbot_rag(registry)
    _register_document_processor(registry)
    _register_batch_classifier(registry)
    _register_enrichment(registry)
    _register_briefing(registry)
    _register_routing(registry)
    _register_company_classifier(registry)


def _register_treasury(registry: ToolRegistry) -> None:
    """Register treasury agent from existing TreasuryAnalystService constants."""
    try:
        from app.modules.service_requests.services.treasury_analyst_service import (
            FUNCTION_MAP as TREASURY_FUNCTION_MAP,
            _FUNC_DECLS as TREASURY_FUNC_DECLS,
            SYSTEM_PROMPT_TEMPLATE as TREASURY_PROMPT_TEMPLATE,
        )
        from datetime import datetime, timezone

        def treasury_prompt_fn(_ctx: dict) -> str:
            """Generate treasury prompt with current date (existing behavior)."""
            from app.modules.shared.services.base_analyst_service import DAYS_ES
            now = datetime.now(timezone.utc)
            return TREASURY_PROMPT_TEMPLATE.format(
                current_date=now.strftime("%Y-%m-%d"),
                day_of_week=DAYS_ES[now.weekday()],
            )

        # Import artifacts builder — use unbound method to avoid creating orphan instance
        artifacts_builder = None
        try:
            from app.modules.service_requests.services.treasury_analyst_service import (
                TreasuryAnalystService,
            )
            # _build_artifacts doesn't use self — call as unbound with None
            _unbound = TreasuryAnalystService._build_artifacts
            artifacts_builder = lambda tool_results: _unbound(None, tool_results)
        except Exception:
            pass

        registry.register("treasury", ToolSet(
            function_declarations=TREASURY_FUNC_DECLS,
            function_map=TREASURY_FUNCTION_MAP,
            prompt_fn=treasury_prompt_fn,
            artifacts_builder=artifacts_builder,
            max_tool_rounds=3,
            second_call_max_tokens=4096,
            agent_type_label="Treasury Analyst",
            self_reflection_enabled=True,
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: treasury registration failed: {e}")


def _register_admin(registry: ToolRegistry) -> None:
    """Register admin agent from existing AdminAssistantService constants."""
    try:
        from app.modules.agents.services.admin_assistant_service import (
            FUNCTION_MAP as ADMIN_FUNCTION_MAP,
            TOOL_FUNCTIONS as ADMIN_TOOL_FUNCTIONS,
            SYSTEM_PROMPT as ADMIN_SYSTEM_PROMPT,
        )

        # Merge admin tools + decision support tools (map + declarations).
        # IMPORTANT: do NOT iterate `_ADFD` and call `.name` on each item —
        # vertexai.generative_models.FunctionDeclaration is a proto-plus
        # wrapper that crashes with AttributeError on `.name` access in
        # some SDK versions. Use the BY_NAME dict (single source of truth)
        # for an O(1), introspection-free lookup instead.
        from app.modules.shared.services.agent_decision_tools import (
            DECISION_FUNCTION_MAP as _ADFM,
            DECISION_FUNC_DECLS_BY_NAME as _ADFD_BY_NAME,
        )
        admin_tools = ('get_system_health', 'optimize_workload')
        admin_merged_map = dict(ADMIN_FUNCTION_MAP)
        admin_merged_map.update({k: v for k, v in _ADFM.items() if k in admin_tools})
        admin_merged_decls = list(ADMIN_TOOL_FUNCTIONS) + [
            _ADFD_BY_NAME[name] for name in admin_tools if name in _ADFD_BY_NAME
        ]

        registry.register("admin", ToolSet(
            function_declarations=admin_merged_decls,
            function_map=admin_merged_map,
            prompt_template=ADMIN_SYSTEM_PROMPT,
            max_tool_rounds=2,
            second_call_max_tokens=2048,
            agent_type_label="Admin Assistant",
            self_reflection_enabled=True,
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: admin registration failed: {e}")


def _register_supervisor(registry: ToolRegistry) -> None:
    """Register supervisor agent with composable tools.

    Base: 10 supervisor tools (stats, SLA, agents, trends)
    + Inspection tools (5) for OMS/ITVE entities
    + License tools (4) for OMS entities
    + Appointment tools (3) for CNEDOGE/DGT entities

    All tools are registered together — the dynamic prompt guides Gemini
    to use only the relevant tools for each entity.
    """
    try:
        from app.modules.shared.services.supervisor_tools import (
            SUPERVISOR_FUNCTION_MAP,
            SUPERVISOR_FUNC_DECLS,
            SUPERVISOR_PROMPT_TEMPLATE,
            supervisor_build_artifacts,
        )
        from app.modules.shared.services.supervisor_extended_tools import (
            INSPECTION_FUNCTION_MAP, INSPECTION_FUNC_DECLS, INSPECTION_PROMPT_FRAGMENT,
            LICENSE_FUNCTION_MAP, LICENSE_FUNC_DECLS, LICENSE_PROMPT_FRAGMENT,
            APPOINTMENT_FUNCTION_MAP, APPOINTMENT_FUNC_DECLS, APPOINTMENT_PROMPT_FRAGMENT,
        )

        # Compose all tools
        all_func_decls = list(SUPERVISOR_FUNC_DECLS) + INSPECTION_FUNC_DECLS + LICENSE_FUNC_DECLS + APPOINTMENT_FUNC_DECLS
        all_func_map = {
            **SUPERVISOR_FUNCTION_MAP,
            **INSPECTION_FUNCTION_MAP,
            **LICENSE_FUNCTION_MAP,
            **APPOINTMENT_FUNCTION_MAP,
        }

        def composable_prompt_fn(ctx: dict) -> str:
            """Build supervisor prompt with entity-specific tool sections."""
            from datetime import datetime, timezone
            from app.modules.shared.services.base_analyst_service import DAYS_ES

            now = datetime.now(timezone.utc)
            workflow_codes = ctx.get("workflow_codes", [])
            wc_upper = [w.upper() for w in workflow_codes]

            # Start with base prompt
            prompt = SUPERVISOR_PROMPT_TEMPLATE
            if "{current_date}" in prompt:
                prompt = prompt.replace("{current_date}", now.strftime("%Y-%m-%d"))
            if "{day_of_week}" in prompt:
                prompt = prompt.replace("{day_of_week}", DAYS_ES[now.weekday()])

            # Append entity-specific tool sections
            has_inspections = any("INSPECCION" in w or "MATRICULACION" in w or "OMS" in w for w in wc_upper)
            has_licenses = any("LICENCIA" in w or "OMS" in w or "PATENTE" in w for w in wc_upper)
            has_appointments = any("PASAPORTE" in w or "RESIDENCIA" in w or "CONDUCIR" in w or "CARNET" in w for w in wc_upper)

            if has_inspections:
                prompt += INSPECTION_PROMPT_FRAGMENT
            if has_licenses:
                prompt += LICENSE_PROMPT_FRAGMENT
            if has_appointments:
                prompt += APPOINTMENT_PROMPT_FRAGMENT

            return prompt

        # Merge supervisor tools + decision support tools (map + declarations).
        # See _register_admin for why we use BY_NAME instead of .name access.
        from app.modules.shared.services.agent_decision_tools import (
            DECISION_FUNCTION_MAP as _DFM,
            DECISION_FUNC_DECLS_BY_NAME as _DFD_BY_NAME,
        )
        sup_tools = ('predict_sla_risk', 'suggest_reassignment')
        all_func_map.update({k: v for k, v in _DFM.items() if k in sup_tools})
        all_func_decls = all_func_decls + [
            _DFD_BY_NAME[name] for name in sup_tools if name in _DFD_BY_NAME
        ]

        registry.register("supervisor", ToolSet(
            function_declarations=all_func_decls,
            function_map=all_func_map,
            prompt_fn=composable_prompt_fn,
            artifacts_builder=supervisor_build_artifacts,
            max_tool_rounds=3,
            second_call_max_tokens=3072,
            agent_type_label="Supervisor Assistant (composable)",
            self_reflection_enabled=True,
        ))
        logger.info(
            f"ToolRegistry: supervisor registered with {len(all_func_decls)} tools "
            f"(10 base + {len(INSPECTION_FUNC_DECLS)} inspection + "
            f"{len(LICENSE_FUNC_DECLS)} license + {len(APPOINTMENT_FUNC_DECLS)} appointment)"
        )
    except ImportError as e:
        logger.warning(f"ToolRegistry: supervisor registration failed: {e}")
        registry.register("supervisor", ToolSet(
            function_declarations=[],
            function_map={},
            prompt_template="Supervisor agent tools not available.",
            agent_type_label="Supervisor Assistant (fallback)",
        ))


def _register_entity_agent(registry: ToolRegistry) -> None:
    """Register entity field agent (CNEDOGE, DGT, Extranjeria, etc.) with 10 business tools."""
    try:
        from app.modules.shared.services.entity_agent_tools import (
            ENTITY_AGENT_FUNCTION_MAP,
            ENTITY_AGENT_FUNC_DECLS,
            ENTITY_AGENT_PROMPT_TEMPLATE,
        )
        from datetime import datetime, timezone

        def entity_prompt_fn(ctx: dict) -> str:
            now = datetime.now(timezone.utc)
            return ENTITY_AGENT_PROMPT_TEMPLATE.format(
                entity_code=ctx.get("entity_code", "unknown"),
                current_date=now.strftime("%Y-%m-%d"),
            )

        # Merge entity agent tools + decision support tools (map + declarations).
        # See _register_admin for why we use BY_NAME instead of .name access.
        from app.modules.shared.services.agent_decision_tools import (
            DECISION_FUNCTION_MAP,
            DECISION_FUNC_DECLS_BY_NAME,
        )
        entity_tools = ('ai_decision_support', 'assess_request_risk', 'find_similar_cases', 'summarize_request')
        merged_map = dict(ENTITY_AGENT_FUNCTION_MAP)
        merged_map.update({k: v for k, v in DECISION_FUNCTION_MAP.items() if k in entity_tools})
        merged_decls = list(ENTITY_AGENT_FUNC_DECLS) + [
            DECISION_FUNC_DECLS_BY_NAME[name] for name in entity_tools if name in DECISION_FUNC_DECLS_BY_NAME
        ]

        registry.register("entity_agent", ToolSet(
            function_declarations=merged_decls,
            function_map=merged_map,
            prompt_fn=entity_prompt_fn,
            max_tool_rounds=3,
            second_call_max_tokens=2048,
            agent_type_label="Entity Field Agent Assistant",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: entity_agent registration failed: {e}")
        registry.register("entity_agent", ToolSet(
            function_declarations=[],
            function_map={},
            prompt_template="Entity agent tools not available.",
            agent_type_label="Entity Agent (fallback)",
        ))


def _register_orchestrator(registry: ToolRegistry) -> None:
    """Register orchestrator agent (A2A pattern — agent-of-agents).

    The orchestrator has 3 meta-functions that delegate to specialized sub-agents.
    This avoids giving Gemini 36+ functions to choose from (routing degrades >20).

    Instead, Gemini selects which SUB-AGENT to route to, and the sub-agent
    handles the actual data retrieval with its own specialized tools.
    """
    registry.register("orchestrator", ToolSet(
        function_declarations=[],  # Populated dynamically in DynamicAnalystService
        function_map={},           # Populated dynamically (requires DynamicAnalystService ref)
        prompt_template=(
            "Eres el Director General de la plataforma Facil (Gobierno de Guinea Ecuatorial).\n"
            "Tienes acceso a 3 agentes especializados que puedes consultar:\n\n"
            "1. **ask_treasury** — Analista Financiero del Tesoro Público.\n"
            "   Para preguntas sobre: ingresos, pagos, SLA de pagos, reconciliación bancaria,\n"
            "   tendencias financieras, anomalías de pago, previsiones.\n\n"
            "2. **ask_admin** — Asistente de Administración de Agentes.\n"
            "   Para preguntas sobre: disponibilidad de agentes, carga de trabajo,\n"
            "   rendimiento, anomalías cross-entidad, equilibrio de recursos.\n\n"
            "3. **ask_supervisor** — Supervisor de Entidad (requiere entity_code).\n"
            "   Para preguntas sobre: solicitudes de servicio de una entidad específica,\n"
            "   pipeline de workflows, SLA de procesamiento, agentes de la entidad.\n\n"
            "REGLAS:\n"
            "- Delega SIEMPRE a la función correcta. No respondas sin datos.\n"
            "- Para preguntas mixtas (ej: 'ingresos Y solicitudes'), llama AMBAS funciones.\n"
            "- Si el usuario pregunta sobre una entidad específica, usa ask_supervisor con su código.\n"
            "- Sintetiza las respuestas de los sub-agentes en un análisis consolidado.\n"
            "- Responde en español. Sé factual y conciso.\n"
            "- Fecha actual: {current_date} ({day_of_week}).\n"
        ),
        sub_agents={
            "ask_treasury": SubAgentConfig(
                target_agent_type="treasury",
                description=(
                    "Consultar al Analista Financiero del Tesoro sobre ingresos, pagos, "
                    "SLA de pagos, reconciliación bancaria, tendencias, anomalías y previsiones."
                ),
                requires_entity_code=False,
            ),
            "ask_admin": SubAgentConfig(
                target_agent_type="admin",
                description=(
                    "Consultar al Asistente de Administración sobre agentes, carga de trabajo, "
                    "rendimiento, anomalías cross-entidad y equilibrio de recursos."
                ),
                requires_entity_code=False,
            ),
            "ask_supervisor": SubAgentConfig(
                target_agent_type="supervisor",
                description=(
                    "Consultar al Supervisor de una entidad específica sobre solicitudes "
                    "de servicio, pipeline de workflows, SLA de procesamiento y agentes. "
                    "Requiere entity_code (ej: CNEDOGE_PASAPORTE, DGT, MINFP, ONRC)."
                ),
                requires_entity_code=True,
            ),
        },
        max_tool_rounds=3,  # Orchestrator may need multiple sub-agent calls
        second_call_max_tokens=4096,
        agent_type_label="Director General (Orchestrator)",
    ))


# ── Non-function-calling agents (process_fn pattern) ─────────────────────


def _register_chatbot_rag(registry: ToolRegistry) -> None:
    """Register chatbot RAG agent (citizen-facing, legislation + services)."""
    try:
        from app.modules.chatbot.services.chatbot_service_rag import chatbot_service_rag

        async def _process(question: str = "", context: dict = None, **kwargs) -> dict:
            ctx = context or {}
            language = ctx.get("language", "es")
            conversation_id = ctx.get("conversation_id")
            result = await chatbot_service_rag.chat(
                message=question,
                conversation_id=conversation_id,
                language=language,
            )
            return {"answer": result.get("message", ""), "sources": result.get("sources", [])}

        registry.register("chatbot_rag", ToolSet(
            process_fn=_process,
            agent_type_label="Chatbot RAG (Citizen)",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: chatbot_rag registration failed: {e}")


def _register_document_processor(registry: ToolRegistry) -> None:
    """Register Gemini document processor (OCR extraction + validation)."""
    try:
        from app.modules.service_requests.services.gemini_document_processor import (
            gemini_document_processor,
        )

        async def _process(question: str = "", context: dict = None, **kwargs) -> dict:
            return {"info": "Document processor requires file_id, use via batch_classifier or service_requests."}

        registry.register("document_processor", ToolSet(
            process_fn=_process,
            thinking_enabled=False,
            agent_type_label="Gemini Document Processor",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: document_processor registration failed: {e}")


def _register_batch_classifier(registry: ToolRegistry) -> None:
    """Register batch document classifier (3-phase: classify → match → extract)."""
    try:
        from app.modules.batch_requests.services.document_classifier import (
            batch_document_classifier,
        )

        async def _process(question: str = "", context: dict = None, **kwargs) -> dict:
            return {"info": "Batch classifier requires session_id and files, use via batch_requests API."}

        registry.register("batch_classifier", ToolSet(
            process_fn=_process,
            thinking_enabled=False,
            agent_type_label="Batch Document Classifier",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: batch_classifier registration failed: {e}")


def _register_enrichment(registry: ToolRegistry) -> None:
    """Register enrichment agent (service description generation)."""
    try:
        from app.modules.enrichment.services.enrichment_service import enrichment_service

        async def _process(question: str = "", context: dict = None, **kwargs) -> dict:
            return {"info": "Enrichment service processes batches via /enrichment/admin/ API."}

        registry.register("enrichment", ToolSet(
            process_fn=_process,
            agent_type_label="Enrichment Agent (Service Descriptions)",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: enrichment registration failed: {e}")


def _register_briefing(registry: ToolRegistry) -> None:
    """Register LLM briefing agent (NL summaries of admin alerts)."""
    try:
        from app.modules.agents.services.llm_briefing_service import llm_briefing_service

        async def _process(question: str = "", context: dict = None, **kwargs) -> dict:
            ctx = context or {}
            alerts_data = ctx.get("alerts_data")
            if not alerts_data:
                return {"info": "Briefing service requires alerts_data in context."}
            result = await llm_briefing_service.generate_briefing(alerts_data)
            return result or {"briefing": "No briefing generated."}

        registry.register("briefing", ToolSet(
            process_fn=_process,
            agent_type_label="LLM Briefing Service",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: briefing registration failed: {e}")


def _register_routing(registry: ToolRegistry) -> None:
    """Register LLM routing agent (intelligent agent selection)."""
    try:
        from app.modules.assignment.services.llm_routing_service import llm_routing_service

        async def _process(question: str = "", context: dict = None, **kwargs) -> dict:
            return {"info": "Routing service requires LLMRoutingContext, use via assignment API."}

        registry.register("routing", ToolSet(
            process_fn=_process,
            thinking_enabled=False,
            agent_type_label="LLM Routing Service",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: routing registration failed: {e}")


def _register_company_classifier(registry: ToolRegistry) -> None:
    """Register company classification agent (rules + LLM hybrid)."""
    try:
        from app.modules.companies.services.classification_agent import classification_agent

        async def _process(question: str = "", context: dict = None, **kwargs) -> dict:
            return {
                "info": "Company classifier requires company_data dict. "
                "Use via /companies/classification/ API endpoints."
            }

        registry.register("company_classifier", ToolSet(
            process_fn=_process,
            agent_type_label="Company Classification Agent",
        ))
    except ImportError as e:
        logger.warning(f"ToolRegistry: company_classifier registration failed: {e}")
