"""
Base Analyst Service — Abstract base for Gemini function-calling agents.

Multi-round Gemini pattern used by TreasuryAnalystService and AdminAssistantService:
  Question → Gemini → tool selection → safe SQL → data
  → (optional round 2 if Gemini requests more tools)
  → Gemini → analysis

Subclasses override:
  - _get_system_prompt()
  - _get_function_declarations()
  - _get_function_map()
  - _get_service_name()  (logging label)

Optional overrides:
  - _get_model_name()          (default: gemini-2.0-flash)
  - _get_vertex_config()       (project/location)
  - _get_second_call_max_tokens()  (default: 2048)
  - _get_max_tool_rounds()     (default: 2, max: 3)

Design: LLM NEVER generates SQL. It routes to predefined safe functions.
Parallel execution uses separate pooled connections (asyncpg requirement).
Entity-scoped: all queries filtered by user's entity context.
"""

import abc
import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.config import get_settings
from app.core.ai_telemetry import traced_generate_sync

try:
    from vertexai.generative_models import (
        GenerativeModel,
        GenerationConfig,
        Tool,
        FunctionDeclaration,
        Part,
        Content,
    )
    import vertexai

    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("Vertex AI SDK not available - analyst services disabled")

# ToolConfig mode=ANY forces Gemini to always call at least one function on the first round.
# Degrades gracefully if the SDK version doesn't support it.
_TOOL_CONFIG_ANY = None
try:
    from vertexai.generative_models import ToolConfig as _ToolConfig  # type: ignore[attr-defined]
    _TOOL_CONFIG_ANY = _ToolConfig(
        function_calling_config=_ToolConfig.FunctionCallingConfig(
            mode=_ToolConfig.FunctionCallingConfig.Mode.ANY,
        )
    )
    logger.info("ToolConfig mode=ANY loaded — Gemini will always call a tool on first round")
except Exception:
    logger.warning("ToolConfig not available — Gemini may bypass function calling (mode=AUTO)")

# Days of week in Spanish (shared across all analyst services)
DAYS_ES = [
    "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo",
]

# Shared constants
GEMINI_TIMEOUT_FIRST_CALL = 25.0
GEMINI_TIMEOUT_SECOND_CALL = 30.0
GEMINI_TIMEOUT_EXTRA_ROUND = 20.0
MAX_INIT_RETRIES = 3
INIT_RETRY_DELAY = 2.0
FIRST_CALL_MAX_TOKENS = 1024  # Increased from 512: multi-tool selection needs more token budget
SECOND_CALL_MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 2  # Default; subclass can override up to 3


class BaseAnalystService(abc.ABC):
    """Abstract base for Gemini function-calling analyst agents."""

    def __init__(self):
        self._model: Optional[Any] = None
        self._initialized = False
        self._init_failures = 0

    # ---- Abstract interface ----

    @abc.abstractmethod
    def _get_system_prompt(self) -> str:
        """Return the system instruction for Gemini."""
        ...

    @abc.abstractmethod
    def _get_function_declarations(self) -> list:
        """Return list of FunctionDeclaration objects for Gemini tools."""
        ...

    @abc.abstractmethod
    def _get_function_map(self) -> Dict[str, Callable]:
        """Return mapping fn_name -> async callable(db, **kwargs)."""
        ...

    # ---- Optional overrides ----

    def _get_service_name(self) -> str:
        """Human-readable name for logging."""
        return self.__class__.__name__

    def _get_agent_type(self) -> Optional[str]:
        """Return agent type for query logging. Subclasses override: 'treasury' | 'admin'."""
        return None

    _INJECTION_PATTERNS = [
        'ignore previous', 'forget your instructions', 'disregard your',
        'override your', 'you are now', 'pretend you are', 'act as', 'roleplay',
        'show me your prompt', 'system prompt', 'reveal your',
        'ignora las instrucciones', 'olvida tus instrucciones', 'nuevas instrucciones',
        'muéstrame tu prompt', 'cuáles son tus instrucciones',
        'ignore les instructions', 'oublie tes instructions', 'montre-moi ton prompt',
    ]

    def _detect_injection(self, text: str) -> bool:
        """Detect prompt injection patterns with unicode normalization."""
        import unicodedata
        import re
        normalized = unicodedata.normalize('NFKC', text)
        normalized = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', normalized)
        msg_lower = normalized.lower()
        return any(p in msg_lower for p in self._INJECTION_PATTERNS)

    def _is_thinking_enabled(self) -> bool:
        """Whether to use thinking budget on final analysis round. Override in subclass."""
        return True

    def _is_self_reflection_enabled(self) -> bool:
        """Whether to self-evaluate response quality. Override in subclass."""
        return False

    def _get_model_name(self) -> str:
        """Gemini model name — uses GEMINI_CHAT_MODEL from settings (default: gemini-2.5-flash)."""
        settings = get_settings()
        return getattr(settings, "GEMINI_CHAT_MODEL", "gemini-2.5-flash")

    def _get_vertex_config(self) -> Dict[str, str]:
        """Return {project, location} for vertexai.init()."""
        settings = get_settings()
        project = (
            getattr(settings, "VERTEX_AI_PROJECT_ID", None)
            or getattr(settings, "GCP_PROJECT_ID", None)
            or getattr(settings, "GOOGLE_CLOUD_PROJECT", None)
        )
        location = (
            getattr(settings, "VERTEX_AI_LOCATION", None)
            or getattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")
        )
        return {"project": project, "location": location}

    def _get_second_call_max_tokens(self) -> int:
        """Max output tokens for the analysis call (second Gemini call)."""
        return SECOND_CALL_MAX_TOKENS

    def _get_max_tool_rounds(self) -> int:
        """Max rounds of tool calling before final analysis. Default 2, max 3.

        Round 1: Initial question → Gemini selects tools → execute
        Round 2+: Gemini sees results, may request MORE tools → execute
        Final: Gemini generates text analysis from all accumulated data
        """
        return MAX_TOOL_ROUNDS

    async def _log_query(
        self,
        session_id: Optional[str],
        question: str,
        slots: Any,                           # ExtractedSlots | None
        tools_used: List[str],
        response_time_ms: int,
        was_successful: bool,
    ) -> None:
        """
        Fire-and-forget query logger for ML training data collection.

        Derives ground_truth_intent from tools_used via FUNCTION_TO_INTENT.
        Also computes and stores Vertex AI embedding for pgvector similarity search.
        Never blocks the response — called via asyncio.create_task().
        All exceptions are swallowed.
        """
        agent_type = self._get_agent_type()
        if not agent_type:
            return  # subclass hasn't opted in — skip

        try:
            from app.modules.shared.services.nlp_preprocessor import FUNCTION_TO_INTENT
            from app.database.connection import db_manager
            import json

            # Derive ground truth: first recognized function → intent
            ground_truth: Optional[str] = None
            for fn in tools_used:
                if fn in FUNCTION_TO_INTENT:
                    ground_truth = FUNCTION_TO_INTENT[fn]
                    break

            probs_json: Optional[str] = None
            if slots is not None and getattr(slots, "intent_probabilities", None):
                probs_json = json.dumps(slots.intent_probabilities)

            # Compute embedding (fire-and-forget, non-blocking)
            embedding_str: Optional[str] = None
            try:
                from app.modules.shared.services.embedding_service import get_embedding
                embedding = await get_embedding(question)
                if embedding:
                    embedding_str = str(embedding)
            except Exception:
                pass  # Embedding failure never blocks logging

            async with db_manager.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_query_logs (
                        agent_type, session_id, question,
                        detected_intent, actual_functions_called, ground_truth_intent,
                        intent_confidence, intent_probabilities,
                        was_successful, response_time_ms,
                        entity_codes, time_period_days, metric,
                        embedding
                    ) VALUES (
                        $1, $2, $3,
                        $4, $5, $6,
                        $7, $8::jsonb,
                        $9, $10,
                        $11, $12, $13,
                        $14::vector
                    )
                    """,
                    agent_type,
                    session_id,
                    question[:2000],
                    slots.intent.value if slots else None,
                    tools_used or [],
                    ground_truth,
                    float(slots.confidence) if slots else None,
                    probs_json,
                    was_successful,
                    response_time_ms,
                    getattr(slots, "entity_codes", []) or [],
                    getattr(slots, "time_period_days", None) if slots else None,
                    getattr(slots, "metric", None) if slots else None,
                    embedding_str,
                )
        except Exception as exc:
            logger.debug(f"{self._get_service_name()} query log skipped: {exc}")

    def _build_artifacts(self, tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build typed artifacts from tool results. Override in subclass.

        Returns list of artifacts, each with a 'type' discriminator:
        - table: {"type": "table", "title": str, "headers": [...], "rows": [[...]], "alignments": [...]}
        - kpi_grid: {"type": "kpi_grid", "title": str, "metrics": [{"label": str, "value": str, ...}]}
        - summary: {"type": "summary", "title": str, "content": str, "severity": str|None}
        """
        return []

    # ---- Shared implementation ----

    def _ensure_initialized(self):
        """Lazy initialization with retry. Safe to call multiple times."""
        if self._initialized and self._model is not None:
            return

        if not VERTEX_AI_AVAILABLE:
            self._initialized = True
            return

        if self._init_failures >= MAX_INIT_RETRIES:
            return

        try:
            # Use centralized VertexAIManager for SDK init (called once per process)
            from app.modules.shared.services.vertex_ai_manager import VertexAIManager
            manager = VertexAIManager()
            manager.initialize()

            func_decls = self._get_function_declarations()
            tools = [Tool(function_declarations=func_decls)] if func_decls else None

            self._model = GenerativeModel(
                self._get_model_name(),
                system_instruction=self._get_system_prompt(),
                tools=tools,
            )
            self._initialized = True
            self._init_failures = 0
            logger.info(f"{self._get_service_name()} initialized successfully")
        except Exception as e:
            self._init_failures += 1
            logger.error(
                f"{self._get_service_name()} init failed "
                f"(attempt {self._init_failures}/{MAX_INIT_RETRIES}): {e}"
            )
            if self._init_failures < MAX_INIT_RETRIES:
                time.sleep(INIT_RETRY_DELAY)
                self._ensure_initialized()

    async def process_question(
        self,
        db,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a question using multi-round Gemini function-calling.

        Flow:
          Round 1: question → Gemini → tool selection → execute SQL
          Round 2+ (conditional): if Gemini requests MORE tools → execute
          Final: Gemini generates text analysis from all accumulated data

        Args:
            db: Database connection (fallback; parallel calls use pooled connections)
            question: User's natural language question
            context: Optional dict with:
                - entity_code: str — user's entity code (for data scoping)
                - entity_location_id: str — user's site UUID
                - is_supervisor: bool — True = global view, False = site-scoped
                - user_id: str — user UUID
                - previous_context: dict — previous question/tools for drill-down

        Returns:
            {"answer": str, "tools_used": list[str], "data": dict, "artifacts": list[dict]}
        """
        self._ensure_initialized()
        service_name = self._get_service_name()
        start_time = time.monotonic()
        ctx = context or {}

        # ── Security: prompt injection detection ──────────────────────────
        if self._detect_injection(question):
            logger.warning(f"{service_name}: prompt injection detected: '{question[:80]}'")
            return {
                "answer": "No puedo procesar esa solicitud. ¿En qué puedo ayudarte con tus tareas?",
                "tools_used": [],
                "data": {},
                "artifacts": [],
            }

        if not self._model:
            return {
                "answer": "Servicio IA no disponible temporalmente. "
                          "Consulta los paneles de control.",
                "tools_used": [],
                "data": {},
                "artifacts": [],
            }

        tools_used: List[str] = []
        tool_results: Dict[str, Any] = {}
        function_map = self._get_function_map()
        max_rounds = min(self._get_max_tool_rounds(), 3)  # Hard cap at 3

        # ── NLP pre-processing ──────────────────────────────────────────────
        # 1. Extract intent + slots from the raw question
        # 2. Resolve missing slots via conversation memory (slot inheritance)
        # 3. Build enriched prompt for better Gemini routing
        session_id: Optional[str] = ctx.get("session_id")
        slots = None
        slot_kwargs: Dict[str, Any] = {}
        memory_context: Dict[str, Any] = {}

        try:
            from app.modules.shared.services.nlp_preprocessor import nlp_preprocessor
            from app.modules.shared.services.conversation_memory import (
                ConversationTurn,
                conversation_memory,
            )

            # One-shot Redis upgrade: try to load a better retrained model (Phase 3+)
            # Runs only when the classifier hasn't been upgraded yet this instance lifetime
            if not getattr(self, "_nlp_upgraded", False):
                try:
                    await nlp_preprocessor.ensure_redis_upgrade()
                except Exception:
                    pass
                self._nlp_upgraded = True

            slots = nlp_preprocessor.extract_slots(question)

            # Resolve missing slots from conversation history (if session active)
            if session_id:
                slots = await conversation_memory.resolve_missing_slots(session_id, slots)
                memory_context = await conversation_memory.get_accumulated_context(session_id)

            # kwargs to inject into SQL function calls (NLP-derived defaults)
            slot_kwargs = nlp_preprocessor.get_injected_kwargs(slots)

            logger.debug(
                f"{service_name} NLP: intent={slots.intent.value} "
                f"entities={slots.entity_codes} days={slots.time_period_days} "
                f"metric={slots.metric} conf={slots.confidence:.2f}"
            )
        except Exception as nlp_err:
            logger.warning(f"{service_name} NLP pre-processing failed (non-fatal): {nlp_err}")

        # ── Dynamic few-shot retrieval (Phase 5) ─────────────────────────────
        # Retrieve similar past successful queries to inject as few-shot examples.
        # Cold start guard: < 10 successful logs → empty (no few-shot).
        few_shot_section: Optional[str] = None
        agent_type = self._get_agent_type()
        if agent_type and slots is not None:
            try:
                from app.modules.shared.services.few_shot_retriever import (
                    get_few_shot_examples,
                    format_few_shot_prompt,
                )
                few_shot_examples = await get_few_shot_examples(question, agent_type)
                if few_shot_examples:
                    few_shot_section = format_few_shot_prompt(few_shot_examples)
            except Exception as fs_err:
                logger.debug(f"{service_name} few-shot retrieval failed (non-fatal): {fs_err}")

        # ── Build enriched prompt ───────────────────────────────────────────
        # Prefer NLP-enriched prompt; fall back to legacy previous_context pattern
        prompt_text: str
        if slots is not None:
            try:
                from app.modules.shared.services.nlp_preprocessor import nlp_preprocessor
                prompt_text = nlp_preprocessor.build_enriched_prompt(
                    question, slots, memory_context or None, few_shot_section
                )
            except Exception:
                prompt_text = question
        else:
            prompt_text = question
            prev = ctx.get("previous_context")
            if prev and prev.get("question"):
                prompt_text = (
                    f"Contexto previo — Pregunta anterior: \"{prev['question']}\"\n"
                    f"Funciones usadas: {', '.join(prev.get('tools_used', []))}\n"
                    f"---\n"
                    f"Nueva pregunta: {question}"
                )

        try:
            loop = asyncio.get_running_loop()
            from app.database.connection import db_manager

            # Entity-scoped kwargs injected into every SQL function call
            entity_kwargs = self._build_entity_kwargs(ctx)

            async def _exec_fn(fn_name: str, fn_args: dict):
                if fn_name not in function_map:
                    logger.warning(f"{service_name}: unknown function '{fn_name}'")
                    return fn_name, {"error": f"Función desconocida: {fn_name}"}
                try:
                    # Precedence: entity_kwargs (auth scope) > fn_args (Gemini) > slot_kwargs (NLP defaults)
                    merged_args = {**slot_kwargs, **fn_args, **entity_kwargs}
                    async with db_manager.get_connection() as conn:
                        result = await function_map[fn_name](conn, **merged_args)
                    return fn_name, result
                except TypeError:
                    # Function doesn't accept some kwargs — fall back to fn_args only
                    try:
                        async with db_manager.get_connection() as conn:
                            result = await function_map[fn_name](conn, **fn_args)
                        return fn_name, result
                    except Exception as e:
                        logger.error(f"{service_name} function {fn_name} failed: {e}")
                        return fn_name, {"error": str(e)}
                except Exception as e:
                    logger.error(f"{service_name} function {fn_name} failed: {e}")
                    return fn_name, {"error": str(e)}

            # ── Round 1: Initial question → Gemini → function calls ──
            # ToolConfig mode=ANY: forces Gemini to call at least one tool (no text-only escape).
            _r1_kwargs: dict = {
                "generation_config": GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=FIRST_CALL_MAX_TOKENS,
                ),
            }
            if _TOOL_CONFIG_ANY is not None:
                _r1_kwargs["tool_config"] = _TOOL_CONFIG_ANY

            response = await asyncio.wait_for(
                traced_generate_sync(
                    self._model, prompt_text,
                    feature="analyst_base",
                    **_r1_kwargs,
                ),
                timeout=GEMINI_TIMEOUT_FIRST_CALL,
            )

            # Track token usage via centralized manager
            try:
                from app.modules.shared.services.vertex_ai_manager import VertexAIManager
                VertexAIManager().track_usage(response, service_name)
            except Exception:
                pass

            if not response.candidates:
                logger.warning(f"{service_name}: empty candidates from Gemini")
                return {
                    "answer": "No se obtuvo respuesta. Reformula tu pregunta.",
                    "tools_used": [],
                    "data": {},
                    "artifacts": [],
                }

            # Extract function calls from response
            function_calls = self._extract_function_calls(response)

            if not function_calls:
                try:
                    text = (response.text or "").strip()
                except (ValueError, AttributeError):
                    text = ""
                return {
                    "answer": text or "No puedo responder sin datos. Sé más específico.",
                    "tools_used": [],
                    "data": {},
                    "artifacts": [],
                }

            # Execute round 1 tools
            tools_used, tool_results = await self._execute_function_calls(
                function_calls, _exec_fn, tools_used, tool_results
            )

            if not tool_results:
                return {
                    "answer": "Error ejecutando las funciones de datos.",
                    "tools_used": tools_used,
                    "data": {},
                    "artifacts": [],
                }

            # Build chat history for multi-round
            chat_history = [
                Content(role="user", parts=[Part.from_text(prompt_text)]),
                response.candidates[0].content,
            ]

            # ── Round 2..N: Conditional extra tool rounds ──
            current_round = 1
            last_response = response

            while current_round < max_rounds:
                # Send accumulated results back to Gemini
                fn_response_parts = self._build_function_response_parts(tool_results)
                chat_history.append(Content(role="user", parts=fn_response_parts))

                is_final_round = current_round >= max_rounds - 1
                # Final round: higher temperature for natural analysis, add top_p
                gen_kwargs_final: dict = {
                    "temperature": 0.4 if is_final_round else 0.2,
                    "max_output_tokens": (
                        FIRST_CALL_MAX_TOKENS
                        if not is_final_round
                        else self._get_second_call_max_tokens()
                    ),
                }
                if is_final_round:
                    gen_kwargs_final["top_p"] = 0.9
                final_gen_config = GenerationConfig(**gen_kwargs_final)

                # Thinking budget for final analysis (separate from GenerationConfig)
                extra_gen_kwargs: dict = {}
                if is_final_round and self._is_thinking_enabled():
                    try:
                        # Attempt 1: Vertex AI ThinkingConfig class
                        from vertexai.generative_models import ThinkingConfig
                        extra_gen_kwargs["thinking_config"] = ThinkingConfig(thinking_budget=2048)
                        logger.debug(f"{service_name}: thinking_budget=2048 via ThinkingConfig")
                    except (ImportError, TypeError):
                        try:
                            # Attempt 2: dict format (Google AI Studio / newer SDK)
                            final_gen_config = GenerationConfig(
                                **gen_kwargs_final,
                                thinking_config={"type": "enabled", "budget_tokens": 2048}
                            )
                            logger.debug(f"{service_name}: thinking_budget=2048 via dict")
                        except (TypeError, ValueError):
                            logger.debug(f"{service_name}: thinking_config not supported by SDK")

                next_response = await asyncio.wait_for(
                    traced_generate_sync(
                        self._model, chat_history,
                        feature="analyst_base",
                        generation_config=final_gen_config,
                        **extra_gen_kwargs,
                    ),
                    timeout=(
                        GEMINI_TIMEOUT_EXTRA_ROUND
                        if not is_final_round
                        else GEMINI_TIMEOUT_SECOND_CALL
                    ),
                )

                # Track multi-round token usage
                try:
                    from app.modules.shared.services.vertex_ai_manager import VertexAIManager
                    VertexAIManager().track_usage(next_response, service_name)
                except Exception:
                    pass

                if not next_response.candidates:
                    break

                # Check if Gemini wants MORE tools (chain-of-tools)
                extra_calls = self._extract_function_calls(next_response)

                if extra_calls and current_round < max_rounds - 1:
                    # Gemini wants more data — execute extra tools
                    logger.info(
                        f"{service_name}: round {current_round + 1}, "
                        f"extra tools: {[fc.name for fc in extra_calls]}"
                    )
                    chat_history.append(next_response.candidates[0].content)
                    tools_used, tool_results = await self._execute_function_calls(
                        extra_calls, _exec_fn, tools_used, tool_results
                    )
                    current_round += 1
                    last_response = next_response
                else:
                    # Gemini produced text analysis — we're done
                    last_response = next_response
                    break

            # ── Extract final answer ──
            try:
                answer = (last_response.text or "").strip()
            except (ValueError, AttributeError):
                answer = ""
            if not answer:
                answer = "No se pudo generar el análisis. Consulta los paneles."

            latency = int((time.monotonic() - start_time) * 1000)
            logger.info(
                f"{service_name}: rounds={current_round + 1} tools={tools_used} "
                f"latency={latency}ms q={question[:50]}"
            )

            # Filter out error entries from returned data
            clean_data = {
                k: v
                for k, v in tool_results.items()
                if not isinstance(v, dict) or "error" not in v
            }
            artifacts = self._build_artifacts(clean_data)

            # ── Store turn in conversation memory ───────────────────────────
            if session_id and slots is not None:
                try:
                    from app.modules.shared.services.conversation_memory import (
                        ConversationTurn,
                        conversation_memory,
                    )
                    turn = ConversationTurn(
                        question=question,
                        intent=slots.intent.value,
                        entity_codes=slots.entity_codes,
                        agent_name=slots.agent_name,
                        time_period_days=slots.time_period_days,
                        metric=slots.metric,
                        tools_used=tools_used,
                        key_findings=answer[:200],
                    )
                    await conversation_memory.add_turn(session_id, turn)
                except Exception as mem_err:
                    logger.warning(f"{service_name} memory store failed (non-fatal): {mem_err}")

            # Fire-and-forget query logging (never blocks response)
            asyncio.create_task(
                self._log_query(
                    session_id=session_id,
                    question=question,
                    slots=slots,
                    tools_used=tools_used,
                    response_time_ms=latency,
                    was_successful=True,
                )
            )

            # Self-reflection: evaluate response quality (if enabled)
            if self._is_self_reflection_enabled() and answer and len(answer) > 50:
                try:
                    reflection_prompt = (
                        f'Evalúa esta respuesta del 1 al 10 (exactitud, completitud, claridad). '
                        f'Responde SOLO con un número.\n\nPregunta: {question[:100]}\n\nRespuesta: {answer[:500]}'
                    )
                    ref_response = await asyncio.wait_for(
                        traced_generate_sync(
                            self._model, reflection_prompt,
                            feature="analyst_base",
                            generation_config=GenerationConfig(temperature=0.1, max_output_tokens=10),
                        ),
                        timeout=8.0,
                    )
                    import re as _re
                    score_match = _re.search(r'\b(\d{1,2})\b', ref_response.text or "")
                    if score_match:
                        reflection_score = int(score_match.group(1))
                        logger.info(f"{service_name} self-reflection: {reflection_score}/10")
                        if reflection_score < 5:
                            logger.warning(f"{service_name} low quality ({reflection_score}/10), regenerating")
                            # Regenerate with explicit improvement instruction
                            regen_response = await asyncio.wait_for(
                                traced_generate_sync(
                                    self._model,
                                    chat_history + [Content(
                                        role="user",
                                        parts=[Part.from_text(
                                            f"Tu respuesta anterior fue evaluada {reflection_score}/10. "
                                            f"Mejórala: más completa, precisa y estructurada."
                                        )]
                                    )],
                                    feature="analyst_base",
                                    generation_config=GenerationConfig(temperature=0.4, max_output_tokens=self._get_second_call_max_tokens()),
                                ),
                                timeout=GEMINI_TIMEOUT_SECOND_CALL,
                            )
                            regen_text = regen_response.text or ""
                            if regen_text and len(regen_text) > len(answer) * 0.5:
                                answer = regen_text
                                logger.info(f"{service_name} self-reflection: regenerated response accepted")
                except Exception as ref_err:
                    logger.debug(f"{service_name} self-reflection failed (non-fatal): {ref_err}")

            return {
                "answer": answer,
                "tools_used": tools_used,
                "data": clean_data,
                "artifacts": artifacts,
            }

        except asyncio.TimeoutError:
            latency = int((time.monotonic() - start_time) * 1000)
            logger.warning(
                f"{service_name} timed out after {latency}ms, tools={tools_used}"
            )
            asyncio.create_task(
                self._log_query(
                    session_id=session_id,
                    question=question,
                    slots=slots,
                    tools_used=tools_used,
                    response_time_ms=latency,
                    was_successful=False,
                )
            )
            if tool_results:
                clean_data = {
                    k: v
                    for k, v in tool_results.items()
                    if not isinstance(v, dict) or "error" not in v
                }
                artifacts = self._build_artifacts(clean_data)
                return {
                    "answer": "El análisis tardó demasiado. Datos parciales obtenidos.",
                    "tools_used": tools_used,
                    "data": clean_data,
                    "artifacts": artifacts,
                }
            return {
                "answer": "Consulta demasiado lenta. Intenta con una pregunta más específica.",
                "tools_used": tools_used,
                "data": {},
                "artifacts": [],
            }
        except Exception as e:
            latency = int((time.monotonic() - start_time) * 1000)
            logger.error(f"{service_name} error: {type(e).__name__}: {e}")
            asyncio.create_task(
                self._log_query(
                    session_id=session_id,
                    question=question,
                    slots=slots,
                    tools_used=tools_used,
                    response_time_ms=latency,
                    was_successful=False,
                )
            )
            return {
                "answer": "Error procesando la consulta.",
                "tools_used": tools_used,
                "data": {},
                "artifacts": [],
            }

    # ---- Multi-round helpers ----

    @staticmethod
    def _extract_function_calls(response) -> list:
        """Extract function_call parts from a Gemini response."""
        calls = []
        for candidate in response.candidates:
            if not hasattr(candidate, "content") or not candidate.content:
                continue
            for part in candidate.content.parts:
                if (
                    hasattr(part, "function_call")
                    and part.function_call
                    and part.function_call.name
                ):
                    calls.append(part.function_call)
        return calls

    @staticmethod
    async def _execute_function_calls(
        function_calls: list,
        exec_fn: Callable,
        tools_used: List[str],
        tool_results: Dict[str, Any],
    ) -> tuple:
        """Execute function calls in parallel, accumulating into tools_used and tool_results."""
        tasks = []
        for fc in function_calls:
            fn_name = fc.name
            try:
                fn_args = {k: v for k, v in fc.args.items()} if fc.args else {}
                fn_args = {
                    k: (int(v) if isinstance(v, float) and v == int(v) else v)
                    for k, v in fn_args.items()
                }
            except (TypeError, AttributeError):
                fn_args = {}
            tools_used.append(fn_name)
            tasks.append(exec_fn(fn_name, fn_args))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Function execution error: {r}")
                continue
            fn_name, fn_result = r
            tool_results[fn_name] = fn_result
        return tools_used, tool_results

    @staticmethod
    def _build_function_response_parts(tool_results: Dict[str, Any]) -> list:
        """Build Gemini function_response parts from tool results."""
        parts = []
        for fn_name, fn_result in tool_results.items():
            parts.append(
                Part.from_function_response(
                    name=fn_name,
                    response={
                        "result": json.dumps(
                            fn_result, default=str, ensure_ascii=False
                        )
                    },
                )
            )
        return parts

    @staticmethod
    def _build_entity_kwargs(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Build entity-scoping kwargs from context.

        Returns kwargs to inject into SQL functions:
        - _entity_code: user's entity code
        - _entity_location_id: user's site UUID
        - _is_main_office: whether user's site is the main office (global view)
        - _user_id: current user UUID
        - workflow_codes: entity's workflow codes (for config/tariff functions)
        """
        kwargs = {}
        if ctx.get("entity_code"):
            kwargs["_entity_code"] = ctx["entity_code"]
        if ctx.get("entity_location_id"):
            kwargs["_entity_location_id"] = ctx["entity_location_id"]
        if "is_main_office" in ctx:
            kwargs["_is_main_office"] = ctx["is_main_office"]
        if ctx.get("user_id"):
            kwargs["_user_id"] = ctx["user_id"]
        if ctx.get("workflow_codes"):
            kwargs["workflow_codes"] = ctx["workflow_codes"]
        return kwargs
