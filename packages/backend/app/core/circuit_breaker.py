"""
Circuit Breaker pattern for external service calls.

Prevents cascading failures when an external service (BANGE, Gemini, SMTP)
is down. Instead of retrying and creating FAILED records, the circuit
opens and returns a fast failure.

States:
    CLOSED  → Normal operation. Failures increment counter.
    OPEN    → Service considered down. Calls fail immediately.
    HALF_OPEN → After recovery_timeout, allow 1 probe call.

Usage:
    breaker = CircuitBreaker("bange", failure_threshold=5, recovery_timeout=60)

    if not breaker.allow_request():
        return ServiceUnavailableResponse(...)

    try:
        result = await external_call()
        breaker.record_success()
    except Exception:
        breaker.record_failure()
        raise
"""

import time
from enum import Enum
from loguru import logger


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Lock-free circuit breaker for async FastAPI.

    Uses atomic attribute reads/writes instead of locks.
    Python's GIL guarantees atomic reads/writes of simple attributes,
    so no threading.Lock or asyncio.Lock needed for this pattern.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    f"Circuit breaker [{self.name}]: OPEN -> HALF_OPEN "
                    f"(recovery timeout {self.recovery_timeout}s elapsed)"
                )
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        current_state = self.state  # triggers OPEN->HALF_OPEN transition

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        # OPEN
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info(f"Circuit breaker [{self.name}]: HALF_OPEN -> CLOSED (probe succeeded)")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker [{self.name}]: HALF_OPEN -> OPEN (probe failed)")
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker [{self.name}]: CLOSED -> OPEN "
                    f"({self._failure_count} failures in a row)"
                )

    def get_status(self) -> dict:
        """Return current circuit breaker status (for health checks)."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# ============================================================================
# Pre-configured circuit breakers for external services
# ============================================================================

# BANGE: 5 failures → open for 60s
bange_circuit = CircuitBreaker("bange", failure_threshold=5, recovery_timeout=60)

# Gemini: 10 failures → open for 120s (more tolerant, AI can be slow)
gemini_circuit = CircuitBreaker("gemini", failure_threshold=10, recovery_timeout=120)

# SMTP: 3 failures → open for 300s (email can wait)
smtp_circuit = CircuitBreaker("smtp", failure_threshold=3, recovery_timeout=300)
