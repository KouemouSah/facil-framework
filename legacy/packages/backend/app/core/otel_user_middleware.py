"""
OTEL user-attribute middleware (Phase B.3).

Attaches `user.id` and `user.role` attributes to the active span on every
authenticated HTTP request. Lets us filter the Application Observability
service map / traces by user, useful for:

- Debugging a specific user's bundle workflow trace
- Per-role performance segmentation (citizen vs agent vs admin)
- Audit drill-down: link a Tempo trace to a specific user_id

Soft-import: missing opentelemetry package = middleware becomes a no-op
pass-through. Never blocks the request.

Privacy: user.id is the UUID (already a non-PII identifier in our domain).
We do NOT add user.email or user.name. RGPD-safe.
"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


try:
    from opentelemetry import trace as _otel_trace
    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OTEL_AVAILABLE = False


class OtelUserAttributeMiddleware(BaseHTTPMiddleware):
    """Tag the request's active span with user.id / user.role when available.

    The user is resolved from request.state.user (populated by upstream auth
    middleware / dependency). If absent, the middleware is silently a no-op.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        response = await call_next(request)

        if not _OTEL_AVAILABLE:
            return response

        try:
            user = getattr(request.state, "user", None)
            if user is None:
                return response

            span = _otel_trace.get_current_span()
            # If no recording span (no tracer configured), this is a no-op.
            if span is None or not span.is_recording():
                return response

            user_id = getattr(user, "id", None)
            user_role = getattr(user, "role", None)
            if user_id is not None:
                span.set_attribute("user.id", str(user_id))
            if user_role is not None:
                span.set_attribute("user.role", str(user_role))
        except Exception as exc:
            # Never let the middleware crash the response path.
            logger.debug("otel_user_middleware: skipped ({})", exc)

        return response
