"""
VertexAIManager — Singleton managing Vertex AI initialization.

Centralizes:
  1. vertexai.init() — called ONCE per process (not per service)
  2. Model factory — create GenerativeModel with shared project/location
  3. Token tracking — accumulate usage across all services
  4. Circuit breaker — global pause on repeated failures

Process-safe: each uvicorn worker gets its own singleton.
Not thread-safe — relies on Python GIL + single-threaded asyncio event loop.
"""

import time
from typing import Any, Dict, Optional

from loguru import logger

# Vertex AI SDK (optional dependency)
VERTEX_AI_AVAILABLE = False
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Tool
    VERTEX_AI_AVAILABLE = True
except ImportError:
    logger.warning("Vertex AI SDK not available — LLM services disabled")


class VertexAIManager:
    """Singleton managing Vertex AI initialization and token tracking.

    Usage:
        manager = VertexAIManager()
        manager.initialize()
        model = manager.create_model("gemini-2.5-flash", system_instruction="...")
    """

    _instance: Optional["VertexAIManager"] = None

    # Init state
    _sdk_initialized: bool = False
    _init_failures: int = 0
    _project: str = ""
    _location: str = ""

    # Token tracking (accumulated across all services)
    _total_tokens_in: int = 0
    _total_tokens_out: int = 0
    _total_requests: int = 0
    _failed_requests: int = 0

    # Circuit breaker
    _consecutive_failures: int = 0
    _circuit_open: bool = False
    _circuit_open_until: float = 0.0

    MAX_INIT_RETRIES = 3
    CIRCUIT_BREAKER_THRESHOLD = 10
    CIRCUIT_BREAKER_COOLDOWN = 60.0  # seconds

    def __new__(cls) -> "VertexAIManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self) -> bool:
        """Initialize Vertex AI SDK. Called once per process. Safe to call multiple times.

        Returns True if SDK is initialized, False otherwise.
        """
        if self._sdk_initialized:
            return True

        if not VERTEX_AI_AVAILABLE:
            logger.debug("VertexAIManager: SDK not available, skip init")
            return False

        if self._init_failures >= self.MAX_INIT_RETRIES:
            return False

        try:
            from app.config import get_settings
            settings = get_settings()

            self._project = settings.GOOGLE_CLOUD_PROJECT
            self._location = settings.GOOGLE_CLOUD_LOCATION

            vertexai.init(
                project=self._project,
                location=self._location,
            )

            self._sdk_initialized = True
            self._init_failures = 0
            logger.info(
                f"VertexAIManager: initialized "
                f"(project={self._project}, location={self._location})"
            )
            return True

        except Exception as e:
            self._init_failures += 1
            logger.error(
                f"VertexAIManager: init failed "
                f"(attempt {self._init_failures}/{self.MAX_INIT_RETRIES}): {e}"
            )
            return False

    def create_model(
        self,
        model_name: str,
        system_instruction: Optional[str] = None,
        tools: Optional[list] = None,
    ) -> Optional[Any]:
        """Create a GenerativeModel with consistent project/location.

        Args:
            model_name: Gemini model name (e.g., "gemini-2.5-flash").
            system_instruction: System prompt for the model.
            tools: List of Tool objects for function calling.

        Returns:
            GenerativeModel instance or None if SDK unavailable.
        """
        if not self.initialize():
            return None

        try:
            return GenerativeModel(
                model_name,
                system_instruction=system_instruction,
                tools=tools,
            )
        except Exception as e:
            logger.error(f"VertexAIManager: failed to create model '{model_name}': {e}")
            return None

    def track_usage(self, response: Any, service_name: str = "") -> None:
        """Extract and accumulate token usage from a Gemini response.

        Safe to call with any response — silently ignores missing metadata.
        """
        self._total_requests += 1
        try:
            if not response or not hasattr(response, "usage_metadata"):
                return
            meta = response.usage_metadata
            if meta:
                tokens_in = getattr(meta, "prompt_token_count", 0) or 0
                tokens_out = getattr(meta, "candidates_token_count", 0) or 0
                self._total_tokens_in += tokens_in
                self._total_tokens_out += tokens_out
                if tokens_in > 0 or tokens_out > 0:
                    logger.debug(
                        f"VertexAI [{service_name}]: "
                        f"+{tokens_in} in / +{tokens_out} out tokens"
                    )
        except Exception:
            pass  # Never fail on tracking

    def track_failure(self) -> None:
        """Track a failed Gemini call. Opens circuit breaker if threshold reached."""
        self._failed_requests += 1
        self._consecutive_failures += 1

        if self._consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open = True
            self._circuit_open_until = time.monotonic() + self.CIRCUIT_BREAKER_COOLDOWN
            logger.warning(
                f"VertexAIManager: circuit breaker OPEN "
                f"({self._consecutive_failures} consecutive failures, "
                f"cooldown {self.CIRCUIT_BREAKER_COOLDOWN}s)"
            )

    def track_success(self) -> None:
        """Track a successful Gemini call. Resets consecutive failure counter."""
        self._consecutive_failures = 0
        if self._circuit_open:
            self._circuit_open = False
            logger.info("VertexAIManager: circuit breaker CLOSED (success after cooldown)")

    @property
    def is_available(self) -> bool:
        """Check if Vertex AI is initialized and circuit breaker is closed."""
        if not VERTEX_AI_AVAILABLE:
            return False
        if not self._sdk_initialized:
            return self.initialize()
        if self._circuit_open:
            if time.monotonic() >= self._circuit_open_until:
                # Cooldown expired — allow a probe
                self._circuit_open = False
                logger.info("VertexAIManager: circuit breaker cooldown expired, allowing probe")
                return True
            return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregated stats for admin dashboard."""
        return {
            "sdk_initialized": self._sdk_initialized,
            "project": self._project,
            "location": self._location,
            "total_tokens_in": self._total_tokens_in,
            "total_tokens_out": self._total_tokens_out,
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "consecutive_failures": self._consecutive_failures,
            "circuit_open": self._circuit_open,
            "error_rate": (
                round(self._failed_requests / self._total_requests, 4)
                if self._total_requests > 0 else 0.0
            ),
        }

    def reset_stats(self) -> None:
        """Reset accumulated stats (admin action)."""
        self._total_tokens_in = 0
        self._total_tokens_out = 0
        self._total_requests = 0
        self._failed_requests = 0
        self._consecutive_failures = 0
        self._circuit_open = False
