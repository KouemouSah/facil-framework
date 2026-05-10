"""OTEL sampler that drops noise spans before they hit BatchSpanProcessor (Phase B.9).

Why a custom sampler vs head-ratio sampler:
- Health-check probes (`/healthz`, `/ready`) and CORS preflight (`OPTIONS *`)
  represent ~30-50% of HTTP span volume but carry zero business value.
- Dropping them at the SDK level (Decision.DROP) means the span is never
  serialized, never queued in the BatchSpanProcessor, never egressed to
  Tempo. Pure savings on Tempo ingest quota AND Cloud Run egress.
- Other spans pass through with RECORD_AND_SAMPLE so Application
  Observability still derives accurate RED metrics from real business
  traffic.

Why not just exclude paths in the FastAPI instrumentor:
- The FastAPI instrumentor `excluded_urls` parameter only stops emitting
  the FastAPI route span — but the downstream asyncpg + redis spans
  inside that request still get emitted with no parent. Custom sampler
  catches the parent decision and the rest of the trace inherits it.

Wire in app/main.py:
    from app.core.otel_sampler import build_sampler
    provider = TracerProvider(resource=resource, sampler=build_sampler())
"""

from __future__ import annotations

from typing import Optional, Sequence

# All these symbols live in opentelemetry.sdk.trace.sampling but the import
# can fail if the SDK package is missing — wrap to keep boot resilient.
try:
    from opentelemetry.sdk.trace.sampling import (
        Decision,
        ParentBased,
        Sampler,
        SamplingResult,
        TraceIdRatioBased,
        ALWAYS_ON,
    )
    from opentelemetry.trace import Link, SpanKind
    from opentelemetry.util.types import Attributes
    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_AVAILABLE = False
    # Sentinel base class so type-hints below don't crash at import time.
    class Sampler:  # type: ignore[no-redef]
        pass


# Spans whose `http.target` / `http.route` matches one of these prefixes/exact
# values are dropped at the source. Keep this list narrow — anything that
# could exercise a real bug should pass through (e.g. /api/v1/healthz with a
# DB ping is intentionally NOT excluded; only the bare /healthz Cloud Run
# liveness probe is).
_DROPPED_PATHS_EXACT = frozenset({
    "/healthz",
    "/ready",
    "/readyz",
    "/livez",
    "/metrics",
    "/favicon.ico",
})

# Path prefixes (e.g. /static/css/foo.css → matches "/static/")
_DROPPED_PATH_PREFIXES = (
    "/static/",
)

# Methods we drop unconditionally (CORS preflight is pure noise).
_DROPPED_METHODS = frozenset({"OPTIONS"})


def _should_drop(attributes: Optional["Attributes"]) -> bool:
    """Return True if this span belongs to a path/method we want dropped."""
    if not attributes:
        return False
    # Method check first (cheaper, catches CORS preflight regardless of path).
    method = attributes.get("http.method") or attributes.get("http.request.method")
    if method and method in _DROPPED_METHODS:
        return True
    # Path check — try the most-specific attribute first.
    target = (
        attributes.get("http.target")
        or attributes.get("http.route")
        or attributes.get("url.path")
        or attributes.get("http.url")
    )
    if not target:
        return False
    if isinstance(target, str):
        # Strip query string if present (http.url often has it).
        path = target.split("?", 1)[0]
        # /https://host/path → keep just the path portion
        if path.startswith("http://") or path.startswith("https://"):
            try:
                path = "/" + path.split("/", 3)[3]
            except IndexError:
                return False
        if path in _DROPPED_PATHS_EXACT:
            return True
        if any(path.startswith(p) for p in _DROPPED_PATH_PREFIXES):
            return True
    return False


if _OTEL_AVAILABLE:

    class FacilNoiseFilterSampler(Sampler):
        """Drop low-value spans (health probes, CORS preflight, /static),
        delegate everything else to a wrapped sampler.

        The wrapped sampler is typically ALWAYS_ON (current Phase B policy:
        instrument everything). When you want to add ratio-based sampling on
        the long tail later, swap it for `TraceIdRatioBased(0.25)`.
        """

        def __init__(self, delegate: Optional[Sampler] = None):
            self._delegate = delegate or ALWAYS_ON

        def should_sample(  # type: ignore[override]
            self,
            parent_context,
            trace_id: int,
            name: str,
            kind: Optional[SpanKind] = None,
            attributes: Optional["Attributes"] = None,
            links: Optional[Sequence[Link]] = None,
            trace_state=None,
        ) -> "SamplingResult":
            if _should_drop(attributes):
                return SamplingResult(decision=Decision.DROP, attributes=attributes)
            return self._delegate.should_sample(
                parent_context, trace_id, name, kind, attributes, links, trace_state
            )

        def get_description(self) -> str:
            return f"FacilNoiseFilterSampler(delegate={self._delegate.get_description()})"


    def build_sampler(ratio: Optional[float] = None) -> Sampler:
        """Construct the production sampler.

        - ratio=None (default) → drop noise + record everything else 100%
        - ratio=0.25           → drop noise + ratio-sample 25% of remaining
                                 (use as fallback when Tempo quota tightens)

        Wrapped in ParentBased so that a downstream span (asyncpg query
        inside an HTTP request) inherits its parent's sampling decision.
        Without ParentBased, a sampled-out HTTP span could still emit
        sampled-in DB spans, breaking the trace.
        """
        if ratio is not None and 0.0 < ratio < 1.0:
            base = TraceIdRatioBased(ratio)
        else:
            base = ALWAYS_ON
        root = FacilNoiseFilterSampler(delegate=base)
        return ParentBased(root=root)

else:  # pragma: no cover

    def build_sampler(ratio: Optional[float] = None):  # type: ignore[no-redef]
        """OTEL SDK absent — return None, caller must skip sampler config."""
        return None
