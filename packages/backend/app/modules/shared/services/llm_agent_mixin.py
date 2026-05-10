"""
LLMAgentMixin — Lightweight mixin for LLM agent services.

Provides shared infrastructure without imposing the function-calling pattern:
  1. Lazy model initialization via VertexAIManager singleton
  2. Shared _call_gemini() async wrapper with timeout + tracking
  3. Shared _call_gemini_structured() for JSON responses
  4. Graceful degradation (returns None if unavailable)

Design: Mixin, NOT a base class. Services keep their own patterns
(RAG pipeline, batch processing, function-calling) while sharing
init/call/tracking infrastructure.

Usage:
    class MyService(LLMAgentMixin):
        def _get_service_name(self) -> str:
            return "MyService"

        def _get_model_name(self) -> str:
            return "gemini-2.0-flash"

        async def do_work(self, text: str):
            response_text = await self._call_gemini(
                f"Analyze: {text}",
                timeout=15.0,
                generation_config={"temperature": 0.1, "max_output_tokens": 512},
            )
            return response_text
"""

import asyncio
import json
from typing import Any, Dict, Optional

from loguru import logger

from app.core.ai_telemetry import traced_generate_sync
from app.modules.shared.services.vertex_ai_manager import (
    VERTEX_AI_AVAILABLE,
    VertexAIManager,
)

if VERTEX_AI_AVAILABLE:
    from vertexai.generative_models import GenerationConfig


class LLMAgentMixin:
    """Mixin providing shared Gemini model lifecycle and call wrapper.

    Subclasses MUST override:
      - _get_service_name() -> str
      - _get_model_name() -> str

    Subclasses MAY override:
      - _get_system_instruction() -> Optional[str]
      - _get_tools() -> Optional[list]  (for function-calling agents)
      - _get_default_generation_config() -> dict
    """

    # Instance state (set by _ensure_model)
    _mixin_model: Any = None
    _mixin_initialized: bool = False

    # ── Abstract interface (override in subclass) ────────────────────────

    def _get_service_name(self) -> str:
        """Human-readable service name for logging."""
        return self.__class__.__name__

    def _get_model_name(self) -> str:
        """Gemini model name (e.g., 'gemini-2.0-flash')."""
        from app.config import get_settings
        return getattr(get_settings(), "GEMINI_CHAT_MODEL", "gemini-2.0-flash")

    def _get_system_instruction(self) -> Optional[str]:
        """System prompt for the model. None = no system instruction."""
        return None

    def _get_tools(self) -> Optional[list]:
        """Gemini Tool objects for function calling. None = no tools."""
        return None

    def _get_default_generation_config(self) -> dict:
        """Default generation config (can be overridden per call)."""
        return {"temperature": 0.3, "top_p": 0.9, "max_output_tokens": 2048}

    # ── Model lifecycle ──────────────────────────────────────────────────

    def _ensure_model(self) -> bool:
        """Lazy-initialize model via VertexAIManager singleton.

        Returns True if model is ready, False otherwise.
        Safe to call multiple times — idempotent.
        """
        if self._mixin_initialized:
            return self._mixin_model is not None

        self._mixin_initialized = True
        manager = VertexAIManager()

        if not manager.is_available:
            logger.debug(f"{self._get_service_name()}: Vertex AI not available")
            return False

        self._mixin_model = manager.create_model(
            self._get_model_name(),
            system_instruction=self._get_system_instruction(),
            tools=self._get_tools(),
        )

        if self._mixin_model:
            logger.info(f"{self._get_service_name()}: model initialized via mixin")
            return True
        else:
            logger.warning(f"{self._get_service_name()}: model creation failed")
            return False

    def _reset_model(self) -> None:
        """Force re-initialization on next call (e.g., after config change)."""
        self._mixin_model = None
        self._mixin_initialized = False

    # ── Gemini call wrappers ─────────────────────────────────────────────

    async def _call_gemini(
        self,
        prompt: Any,
        timeout: float = 25.0,
        generation_config: Optional[dict] = None,
    ) -> Optional[str]:
        """Call Gemini and return text response.

        Args:
            prompt: Text string or list of Content objects.
            timeout: Max seconds to wait.
            generation_config: Override default config (temperature, max_output_tokens, etc.)

        Returns:
            Response text or None on failure/timeout.
        """
        if not self._ensure_model():
            return None

        manager = VertexAIManager()
        if not manager.is_available:
            return None

        service_name = self._get_service_name()
        config = {**self._get_default_generation_config(), **(generation_config or {})}

        try:
            if VERTEX_AI_AVAILABLE:
                gen_config = GenerationConfig(**config)
            else:
                gen_config = None

            response = await asyncio.wait_for(
                traced_generate_sync(
                    self._mixin_model, prompt,
                    feature="agent_mixin",
                    generation_config=gen_config,
                ),
                timeout=timeout,
            )

            manager.track_usage(response, service_name)
            manager.track_success()

            if response and response.candidates:
                try:
                    return (response.text or "").strip()
                except (ValueError, AttributeError):
                    return ""
            return None

        except asyncio.TimeoutError:
            manager.track_failure()
            logger.warning(f"{service_name}: Gemini call timed out ({timeout}s)")
            return None
        except Exception as e:
            manager.track_failure()
            logger.error(f"{service_name}: Gemini call failed: {type(e).__name__}: {e}")
            return None

    async def _call_gemini_structured(
        self,
        prompt: Any,
        timeout: float = 25.0,
        generation_config: Optional[dict] = None,
    ) -> Optional[Any]:
        """Call Gemini expecting a JSON response.

        Returns parsed JSON (dict/list) or None on failure.
        Handles common LLM quirks: markdown code fences, trailing commas.
        """
        text = await self._call_gemini(prompt, timeout, generation_config)
        if not text:
            return None

        # Strip markdown code fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1])
            else:
                cleaned = cleaned.strip("`").strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(
                f"{self._get_service_name()}: failed to parse JSON response: {e}"
            )
            logger.debug(f"Raw response: {text[:200]}")
            return None

    async def _call_gemini_raw(
        self,
        prompt: Any,
        timeout: float = 25.0,
        generation_config: Optional[dict] = None,
        **kwargs,
    ) -> Optional[Any]:
        """Call Gemini and return the raw response object (for function-calling, etc.)

        This is for advanced use cases where you need access to
        response.candidates[0].content.parts (e.g., function_call parts).
        """
        if not self._ensure_model():
            return None

        manager = VertexAIManager()
        if not manager.is_available:
            return None

        service_name = self._get_service_name()
        config = {**self._get_default_generation_config(), **(generation_config or {})}

        try:
            if VERTEX_AI_AVAILABLE:
                gen_config = GenerationConfig(**config)
            else:
                gen_config = None

            call_kwargs: Dict[str, Any] = {"generation_config": gen_config}
            call_kwargs.update(kwargs)

            response = await asyncio.wait_for(
                traced_generate_sync(
                    self._mixin_model, prompt,
                    feature="agent_mixin",
                    **call_kwargs,
                ),
                timeout=timeout,
            )

            manager.track_usage(response, service_name)
            manager.track_success()
            return response

        except asyncio.TimeoutError:
            manager.track_failure()
            logger.warning(f"{service_name}: Gemini raw call timed out ({timeout}s)")
            return None
        except Exception as e:
            manager.track_failure()
            logger.error(f"{service_name}: Gemini raw call failed: {type(e).__name__}: {e}")
            return None
