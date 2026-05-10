"""
LLM Briefing Service — Gemini-generated admin dashboard summary.

Takes structured alert data (SQL results) and generates a natural language
briefing for the admin. NEVER used for detection — only for summarization
and anomaly pattern analysis on real data.

Design: Same pattern as LLMRoutingService (lazy init, graceful fallback).
Language: Spanish by default (Equatorial Guinea admin context).
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional

from loguru import logger

from app.config import get_settings
from app.core.ai_telemetry import traced_generate_sync

from app.modules.shared.services.vertex_ai_manager import (
    VERTEX_AI_AVAILABLE,
    VertexAIManager,
)

if VERTEX_AI_AVAILABLE:
    from vertexai.generative_models import GenerationConfig


SYSTEM_PROMPT = """Eres un asistente de operaciones conciso para un administrador del sistema TaxasGE
(plataforma de servicios fiscales de Guinea Ecuatorial).

Recibes datos estructurados de alertas sobre {agent_count} agentes en {entity_count} entidades.
Tu tarea: generar un resumen ejecutivo en español Y analizar los datos para detectar anomalías o patrones.

REGLAS:
- Responde SIEMPRE en español
- Céntrate en lo que NECESITA ATENCIÓN (no en lo que está bien)
- Si todo es normal, di "Todos los indicadores operativos están dentro de los parámetros esperados."
- Menciona nombres de agentes y entidades específicos cuando sea relevante
- Cita cifras EXACTAS de los datos (NUNCA inventes datos)
- Si detectas patrones anómalos (agente siempre sobrecargado, bloqueos recurrentes, SLA sistemáticamente en riesgo), menciónalo
- Propón acciones concretas cuando sea pertinente
- Sé factual, no alarmista

FORMATO:
- El campo "briefing" doit contenir du Markdown: **negrita** para datos clave, listas - para acciones
- Máximo 200 palabras en el briefing

RESPONDE SOLO CON JSON VÁLIDO:
{{"briefing": "Tu resumen en **Markdown** aquí.", "priority": "normal|attention|urgent", "anomalies": ["descripción de anomalía si la hay"]}}"""


class LLMBriefingService:
    """Gemini-powered admin alerts briefing."""

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
            model_name = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
            self._model = manager.create_model(model_name)
            self._initialized = True
            logger.info(f"LLM Briefing Service initialized via VertexAIManager ({model_name})")
        except Exception as e:
            logger.error(f"Failed to initialize LLM Briefing Service: {e}")
            self._initialized = True

    async def generate_briefing(
        self, alerts_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a natural language briefing from structured alert data.

        Args:
            alerts_data: Result from get_admin_alerts_dashboard()

        Returns:
            {"briefing": str, "priority": str, "anomalies": list} or None on failure
        """
        self._ensure_initialized()

        if not self._model:
            logger.debug("LLM model not available, skipping briefing")
            return None

        agent_count = 0
        entity_count = 0
        if alerts_data.get("workload_by_entity"):
            entity_count = len(alerts_data["workload_by_entity"])
            agent_count = sum(
                e.get("agent_count", 0) for e in alerts_data["workload_by_entity"]
            )

        prompt = SYSTEM_PROMPT.format(
            agent_count=agent_count, entity_count=entity_count
        )

        user_data = json.dumps(
            {
                "inactive_count": alerts_data.get("inactive_count", 0),
                "overloaded_count": alerts_data.get("overloaded_count", 0),
                "stale_locks_count": alerts_data.get("stale_locks_count", 0),
                "sla_at_risk_count": alerts_data.get("sla_at_risk_count", 0),
                "total_alerts": alerts_data.get("total_alerts", 0),
                "inactive_agents": alerts_data.get("inactive_agents"),
                "overloaded_agents": alerts_data.get("overloaded_agents"),
                "stale_locks": alerts_data.get("stale_locks"),
                "sla_at_risk": alerts_data.get("sla_at_risk"),
                "workload_by_entity": alerts_data.get("workload_by_entity"),
            },
            default=str,
            ensure_ascii=False,
        )

        start_time = time.monotonic()

        try:
            response = await asyncio.wait_for(
                traced_generate_sync(
                    self._model,
                    [prompt, f"Datos de alertas:\n{user_data}"],
                    feature="briefing",
                    generation_config=GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=512,
                        response_mime_type="application/json",
                    ),
                ),
                timeout=10.0,
            )

            # Track token usage via centralized manager
            VertexAIManager().track_usage(response, "LLMBriefingService")
            VertexAIManager().track_success()

            # Safely handle None/empty response
            if not response.candidates:
                logger.warning("LLM briefing: empty candidates")
                return None
            text = response.text
            if not text:
                logger.warning("LLM briefing: empty response text")
                return None
            text = text.strip()
            result = json.loads(text)

            latency_ms = int((time.monotonic() - start_time) * 1000)
            tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0)
            tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0)

            logger.info(
                f"LLM briefing generated: priority={result.get('priority', 'unknown')} "
                f"latency={latency_ms}ms tokens={tokens_in}/{tokens_out}"
            )

            return {
                "briefing": result.get("briefing", ""),
                "priority": result.get("priority", "normal"),
                "anomalies": result.get("anomalies", []),
            }

        except asyncio.TimeoutError:
            VertexAIManager().track_failure()
            logger.warning("LLM briefing timed out")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"LLM briefing returned invalid JSON: {e}")
            return None
        except Exception as e:
            VertexAIManager().track_failure()
            error_str = str(e)
            if "429" in error_str or "Resource exhausted" in error_str:
                logger.warning(f"LLM briefing rate-limited (429): {e}")
            else:
                logger.error(f"LLM briefing error: {e}")
            return None


# Singleton
llm_briefing_service = LLMBriefingService()
