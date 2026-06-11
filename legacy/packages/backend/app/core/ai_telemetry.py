"""
AI telemetry wrapper — emits OTEL spans + persists rows to ai_call_metrics.

Phase A.2 of AI_OBSERVABILITY_PLAN.md.

Used to wrap every Gemini / Vertex AI call so we capture:
- token usage + estimated cost in XAF
- latency
- finish_reason + 6-status error classification
- OTEL trace_id / span_id for Tempo correlation
- privacy-safe prompt_hash (SHA-256 truncated to 16 hex)

Coexistence with VertexAIManager (memory: 2026-05-05 audit)
-----------------------------------------------------------
This module does NOT replace `app.modules.shared.services.vertex_ai_manager`
(VertexAIManager singleton). The two systems are COMPLEMENTARY:

  | Concern                       | VertexAIManager  | ai_call_metrics (this) |
  | Circuit breaker (10 fail/60s) | YES              | no                     |
  | In-memory stats (sub-μs read) | YES              | no                     |
  | BD persistence (cross-worker) | no               | YES                    |
  | Cost in XAF                   | no               | YES                    |
  | Per-feature/model/user tags   | no               | YES                    |
  | OTEL trace correlation        | no               | YES                    |
  | Time series + drill-down      | no               | YES (vw_ai_cost_*)     |

Call sites should keep their existing pattern:

    response = await traced_generate_sync(model, prompt, feature="X", ...)
    VertexAIManager().track_usage(response, "ServiceName")  # circuit breaker
    VertexAIManager().track_success()                       # reset consecutive

In except blocks:
    except Exception:
        VertexAIManager().track_failure()                   # circuit breaker
        raise

Both systems run independently. ai_call_metrics' persist is fire-and-forget
(asyncio.create_task) so it never blocks the user-facing call. VertexAIManager
remains the source of truth for "should I make this call right now?" via its
`is_available` check.

Memory rules:
- #21: Gemini JSON mode obligatoire — wrapper detects json_parse_error status
- #24: json.dumps for JSONB — n/a here (no JSONB column in ai_call_metrics)
- #40: GRAFANA_OTLP_TOKEN provisioned via Secret Manager
- Privacy/RGPD: NEVER store raw prompt or response content. Only the SHA-256
  truncated hash. No reverse-mapping table.

Soft OTEL import: if opentelemetry packages are not installed, spans are
silently skipped — only the BD persistence runs. This lets us deploy the
wrapper before completing the OTLP endpoint setup.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import time
from typing import Any, Optional, Sequence

import asyncpg
from loguru import logger

# Soft OTEL import — module loads even if opentelemetry-api isn't installed.
try:
    from opentelemetry import trace as _otel_trace
    _OTEL_AVAILABLE = True
    _tracer = _otel_trace.get_tracer("facil.ai")
except Exception:  # pragma: no cover — environment without OTEL
    _OTEL_AVAILABLE = False
    _otel_trace = None
    _tracer = None


# ---------------------------------------------------------------------------
# Pricing — XAF per 1M tokens. Updated quarterly via cron (TODO Phase B).
# Source: Vertex AI pricing page × FX rate. Placeholders kept conservative
# (over-estimates so cost appears slightly higher than reality, never lower).
# ---------------------------------------------------------------------------
PRICING_XAF: dict[str, dict[str, float]] = {
    # Gemini 2.5 Flash — primary chatbot + classification model
    "gemini-2.5-flash":     {"input": 45.0,    "output": 180.0},
    "gemini-2.5-flash-001": {"input": 45.0,    "output": 180.0},
    # Gemini 1.5 Pro — used for complex enrichment + agent decisions
    "gemini-1.5-pro":       {"input": 750.0,   "output": 3000.0},
    "gemini-1.5-pro-001":   {"input": 750.0,   "output": 3000.0},
    "gemini-1.5-pro-002":   {"input": 750.0,   "output": 3000.0},
    # Gemini 1.5 Flash — fallback model
    "gemini-1.5-flash":     {"input": 45.0,    "output": 180.0},
    "gemini-1.5-flash-002": {"input": 45.0,    "output": 180.0},
    # Embeddings — text-embedding-005 (Vertex). No output tokens.
    "text-embedding-005":   {"input": 7.5,     "output": 0.0},
    "text-embedding-004":   {"input": 7.5,     "output": 0.0},
}


# Phase B.2 — BD-backed pricing cache.
# Refreshed every CACHE_TTL seconds; fallback to PRICING_XAF if BD unreachable.
_PRICING_CACHE: dict[str, dict[str, float]] = {}
_PRICING_CACHE_TS: float = 0.0
_PRICING_CACHE_TTL = 600.0  # 10 minutes


async def _load_pricing_from_db(pool: asyncpg.Pool) -> dict[str, dict[str, float]]:
    """Load active pricing rows from ai_pricing_config (Phase B.2)."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT model_name, "
                "       input_xaf_per_1m_tokens AS input, "
                "       output_xaf_per_1m_tokens AS output "
                "FROM ai_pricing_config WHERE is_active = true"
            )
        return {
            r["model_name"]: {"input": float(r["input"]), "output": float(r["output"])}
            for r in rows
        }
    except Exception as exc:
        logger.warning("ai_telemetry: BD pricing load failed (fallback to static): {}", exc)
        return {}


async def get_pricing(pool: Optional[asyncpg.Pool] = None) -> dict[str, dict[str, float]]:
    """Return the pricing dict, refreshed from BD when stale.

    Priority order:
    1. BD ai_pricing_config (cached 10 min)
    2. Static PRICING_XAF in this module (fallback)
    """
    global _PRICING_CACHE, _PRICING_CACHE_TS
    now = time.monotonic()
    if not _PRICING_CACHE or (now - _PRICING_CACHE_TS) > _PRICING_CACHE_TTL:
        if pool is None:
            try:
                from app.database.connection import get_db_pool
                pool = await get_db_pool()
            except Exception:
                return PRICING_XAF
        bd = await _load_pricing_from_db(pool)
        if bd:
            _PRICING_CACHE = bd
            _PRICING_CACHE_TS = now
        else:
            return PRICING_XAF
    return _PRICING_CACHE


def normalize_model_name(model: str) -> str:
    """Normalize Vertex AI model paths to short keys used in PRICING_XAF.

    Vertex AI returns full resource paths like:
      'publishers/google/models/gemini-2.5-flash'
      'projects/.../publishers/google/models/text-embedding-005'

    Pricing dict is keyed on short names ('gemini-2.5-flash'). Strip the
    prefix so the lookup succeeds. Idempotent: short names pass through
    unchanged.
    """
    if not model:
        return "unknown"
    # Strip everything up to and including the last '/' (handles both
    # 'publishers/google/models/X' and 'projects/.../models/X').
    if "/" in model:
        return model.rsplit("/", 1)[-1]
    return model


def estimate_cost_xaf(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate XAF cost from token counts. Reads from BD cache (mig 327)
    when populated; falls back to static PRICING_XAF. 0 for unknown models.

    Sync-only (called from finally blocks). The async `get_pricing()` helper
    pre-fills `_PRICING_CACHE` from BD periodically.
    """
    short = normalize_model_name(model)
    # BD cache wins when populated; static dict is fallback.
    pricing = _PRICING_CACHE if _PRICING_CACHE else PRICING_XAF
    p = pricing.get(short)
    if p is None:
        logger.warning("ai_telemetry: unknown model '{}' (short='{}') — cost will be 0", model, short)
        return 0.0
    return (
        (input_tokens / 1_000_000.0) * p["input"]
        + (output_tokens / 1_000_000.0) * p["output"]
    )


def hash_prompt(prompt: Any) -> str:
    """SHA-256 truncated to 16 hex chars. Privacy-safe identifier.

    Accepts any prompt shape (string, list of parts, dict). Coerces to str
    bounded at 8192 chars to keep the hash fast.
    """
    s = str(prompt)
    if len(s) > 8192:
        s = s[:8192]
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Error classification — maps any exception to one of 6 status values
# defined by the chk_aim_status BD constraint (mig 325).
# ---------------------------------------------------------------------------
_ERROR_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("rate limit", "quota", "429", "resource exhausted"), "rate_limited"),
    (("deadline exceeded", "timeout", "504", "timed out"),  "timeout"),
    (("blocked", "safety", "harm", "recitation"),           "content_blocked"),
    (("invalid json", "json decode", "json parse",
      "expecting value", "json.decoder", "jsondecode"),     "json_parse_error"),
)


def classify_error(exc: BaseException) -> str:
    """Return one of: rate_limited | timeout | content_blocked | json_parse_error | error.

    Inspects the exception class name + message for known signatures.
    Falls back to generic 'error' when no hint matches.
    """
    msg = str(exc).lower()
    cls_name = exc.__class__.__name__.lower()
    for hints, status in _ERROR_HINTS:
        for hint in hints:
            if hint in msg or hint in cls_name:
                return status
    return "error"


# ---------------------------------------------------------------------------
# Persistence — fire-and-forget BD insert (never blocks caller, never raises).
# Tracked in a WeakSet so shutdown can await pending tasks.
# ---------------------------------------------------------------------------
_pending_persists: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> None:
    _pending_persists.add(task)
    task.add_done_callback(_pending_persists.discard)


async def _persist_metric(pool: asyncpg.Pool, **kw: Any) -> None:
    """Insert one row into ai_call_metrics. Never raises.

    Phase C.1: now persists injection_risk / injection_score / injection_rules
    (mig 328) so the assessment is queryable in SQL for dashboard + alerts.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ai_call_metrics (
                    trace_id, span_id, provider, model_name, operation,
                    feature, user_id, user_role,
                    input_tokens, output_tokens, cost_xaf,
                    latency_ms, finish_reason, status, error_class, prompt_hash,
                    injection_risk, injection_score, injection_rules
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7::uuid, $8,
                    $9, $10, $11,
                    $12, $13, $14, $15, $16,
                    $17, $18, $19::text[]
                )
                """,
                kw.get("trace_id"), kw.get("span_id"),
                kw.get("provider", "gemini"),
                kw["model_name"], kw["operation"],
                kw["feature"],
                kw.get("user_id"), kw.get("user_role"),
                int(kw.get("input_tokens") or 0),
                int(kw.get("output_tokens") or 0),
                float(kw.get("cost_xaf") or 0),
                int(kw["latency_ms"]),
                kw.get("finish_reason"),
                kw["status"],
                kw.get("error_class"),
                kw.get("prompt_hash"),
                kw.get("injection_risk"),
                int(kw.get("injection_score") or 0),
                kw.get("injection_rules"),  # list[str] or None
            )
    except Exception as exc:
        logger.warning(
            "ai_telemetry: persist failed (non-blocking) feature={} err={}",
            kw.get("feature"), exc,
        )


async def flush_pending_persists(timeout: float = 5.0) -> None:
    """Await any pending persist tasks. Call from FastAPI shutdown event."""
    if not _pending_persists:
        return
    pending = list(_pending_persists)
    logger.info("ai_telemetry: flushing {} pending persists...", len(pending))
    try:
        await asyncio.wait_for(
            asyncio.gather(*pending, return_exceptions=True),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "ai_telemetry: shutdown flush timed out after {}s ({} tasks still pending)",
            timeout, len(_pending_persists),
        )


# ---------------------------------------------------------------------------
# OTEL span helpers — soft no-ops when OTEL is not installed.
# ---------------------------------------------------------------------------
class _NoSpan:
    """Drop-in replacement for an OTEL span when opentelemetry isn't loaded."""
    def set_attribute(self, *a: Any, **kw: Any) -> None: pass
    def record_exception(self, *a: Any, **kw: Any) -> None: pass
    def set_status(self, *a: Any, **kw: Any) -> None: pass
    def get_span_context(self) -> Any:  # pragma: no cover
        class _Ctx:
            trace_id = 0
            span_id = 0
        return _Ctx()


class _NoSpanCM:
    def __enter__(self) -> _NoSpan: return _NoSpan()
    def __exit__(self, *a: Any) -> None: pass


def _start_span(name: str):
    if _OTEL_AVAILABLE and _tracer is not None:
        return _tracer.start_as_current_span(name)
    return _NoSpanCM()


def _format_trace_id(span: Any) -> tuple[Optional[str], Optional[str]]:
    try:
        ctx = span.get_span_context()
        tid = format(ctx.trace_id, "032x") if ctx.trace_id else None
        sid = format(ctx.span_id, "016x") if ctx.span_id else None
        # Reject all-zero IDs (no recording context)
        if tid == "0" * 32:
            tid = None
        if sid == "0" * 16:
            sid = None
        return tid, sid
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Public API: traced_generate (chat / completion) + traced_embed
# ---------------------------------------------------------------------------
async def _resolve_pool(pool: Optional[asyncpg.Pool]) -> asyncpg.Pool:
    """When the caller doesn't pass an explicit pool, fall back to the global
    `get_db_pool()` singleton. Done lazily inside the wrapper so the import
    cycle (ai_telemetry → database → models → ai_telemetry) doesn't break.
    """
    if pool is not None:
        return pool
    from app.database.connection import get_db_pool
    return await get_db_pool()


async def traced_generate(
    model: Any,
    prompt: Any,
    *,
    feature: str,
    pool: Optional[asyncpg.Pool] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    operation: str = "chat",
    **kwargs: Any,
) -> Any:
    """Wrapper around the **async** `model.generate_content_async(prompt, **kwargs)`.

    Emits an OTEL span + persists a row in ai_call_metrics. Returns whatever
    the underlying SDK returns. Errors propagate after recording.

    Use `traced_generate_sync` if your SDK exposes only the synchronous
    `model.generate_content()` (most of Vertex AI in this codebase).

    :param model:       a Vertex AI / Gemini GenerativeModel instance
    :param prompt:      whatever the model accepts (str / list of parts)
    :param feature:     Facil feature label (chatbot_rag | ocr | classification | ...)
    :param pool:        optional asyncpg pool — defaults to `get_db_pool()`
    :param user_id:     optional UUID of the user triggering the call (audit)
    :param user_role:   optional role (citizen | agent | admin) for segmentation
    :param operation:   'chat' (default) | 'completion'
    :param **kwargs:    forwarded to generate_content_async
    """
    pool = await _resolve_pool(pool)
    return await _traced_call(
        model=model, prompt=prompt, feature=feature, pool=pool,
        user_id=user_id, user_role=user_role,
        operation=operation, provider="gemini",
        invoke=lambda m, p: m.generate_content_async(p, **kwargs),
    )


async def traced_generate_sync(
    model: Any,
    prompt: Any,
    *,
    feature: str,
    pool: Optional[asyncpg.Pool] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    operation: str = "chat",
    executor: Optional[concurrent.futures.Executor] = None,
    **kwargs: Any,
) -> Any:
    """Wrapper around the **sync** `model.generate_content(prompt, **kwargs)`,
    run in an executor.

    This is the right entry point for the Vertex AI Gemini SDK as currently
    used in this codebase (the SDK exposes a sync-only `generate_content`
    that we run with `loop.run_in_executor`). Replaces the manual pattern:

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: model.generate_content(prompt, **kwargs),
        )

    With:

        from app.core.ai_telemetry import traced_generate_sync
        response = await traced_generate_sync(
            model, prompt, feature='chatbot_rag', **kwargs,
        )

    Behavior is preserved (still runs sync call in default thread executor);
    only telemetry is added.
    """
    pool = await _resolve_pool(pool)
    loop = asyncio.get_event_loop()
    return await _traced_call(
        model=model, prompt=prompt, feature=feature, pool=pool,
        user_id=user_id, user_role=user_role,
        operation=operation, provider="gemini",
        invoke=lambda m, p: loop.run_in_executor(
            executor, lambda: m.generate_content(p, **kwargs)
        ),
    )


async def traced_embed(
    embed_model: Any,
    texts: Sequence[Any],
    *,
    feature: str,
    pool: Optional[asyncpg.Pool] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Wrapper around the **async** `embed_model.get_embeddings_async(texts, **kwargs)`.

    Same telemetry pattern as `traced_generate` but with `operation='embeddings'`
    and `provider='vertex_embedding'`.
    """
    pool = await _resolve_pool(pool)
    return await _traced_call(
        model=embed_model, prompt=texts, feature=feature, pool=pool,
        user_id=user_id, user_role=user_role,
        operation="embeddings", provider="vertex_embedding",
        invoke=lambda m, p: m.get_embeddings_async(p, **kwargs),
    )


async def traced_embed_sync(
    embed_model: Any,
    texts: Sequence[Any],
    *,
    feature: str,
    pool: Optional[asyncpg.Pool] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    executor: Optional[concurrent.futures.Executor] = None,
    **kwargs: Any,
) -> Any:
    """Wrapper around the **sync** `embed_model.get_embeddings(texts, **kwargs)`,
    run in an executor. Symmetric to `traced_generate_sync` for embeddings.
    """
    pool = await _resolve_pool(pool)
    loop = asyncio.get_event_loop()
    return await _traced_call(
        model=embed_model, prompt=texts, feature=feature, pool=pool,
        user_id=user_id, user_role=user_role,
        operation="embeddings", provider="vertex_embedding",
        invoke=lambda m, p: loop.run_in_executor(
            executor, lambda: m.get_embeddings(p, **kwargs)
        ),
    )


async def _traced_call(
    *,
    model: Any,
    prompt: Any,
    feature: str,
    pool: asyncpg.Pool,
    user_id: Optional[str],
    user_role: Optional[str],
    operation: str,
    provider: str,
    invoke,
) -> Any:
    """Shared core for both traced_generate and traced_embed."""
    # Phase B.5 — prompt injection scan (cheap regex, ~50µs).
    # Phase C.1: also persisted to BD via injection_* columns (mig 328).
    injection_risk = "none"
    injection_score = 0
    injection_rules: Optional[list[str]] = None
    if operation in ("chat", "completion"):
        try:
            from app.core.ai_security import (
                detect_prompt_injection, PromptInjectionBlocked,
            )
            assessment = detect_prompt_injection(prompt)
            injection_risk = assessment.risk
            injection_score = assessment.score
            # Top 5 rules for the BD column (text[])
            if assessment.matched_rules:
                injection_rules = list(assessment.matched_rules)[:5]
            if assessment.is_suspicious:
                logger.warning(
                    "ai_security: feature={} risk={} score={} rules={}",
                    feature, assessment.risk, assessment.score,
                    injection_rules,
                )
            if assessment.should_block:
                raise PromptInjectionBlocked(assessment)
        except ImportError:
            pass  # ai_security module unavailable, skip
        except Exception as exc:
            if exc.__class__.__name__ == "PromptInjectionBlocked":
                raise
            logger.debug("ai_security: scan skipped ({})", exc)

    # Refresh pricing cache from BD (mig 327) — fire-and-forget, non-blocking.
    # If the cache is fresh, this is a no-op. If stale, it kicks off a BD
    # query in the background; the *current* call uses whatever's cached.
    try:
        if not _PRICING_CACHE or (time.monotonic() - _PRICING_CACHE_TS) > _PRICING_CACHE_TTL:
            asyncio.create_task(get_pricing(pool))
    except Exception:
        pass

    raw_model_name = (
        getattr(model, "_model_name", None)
        or getattr(model, "model_name", None)
        or "unknown"
    )
    # Normalize Vertex AI resource paths (publishers/google/models/X → X)
    # so model_name is consistent across BD rows + spans + dashboard panels.
    model_name = normalize_model_name(raw_model_name)
    prompt_hash = hash_prompt(prompt)

    with _start_span(f"gen_ai.{operation}") as span:
        trace_id, span_id = _format_trace_id(span)

        span.set_attribute("gen_ai.system", provider)
        span.set_attribute("gen_ai.operation.name", operation)
        span.set_attribute("gen_ai.request.model", model_name)
        span.set_attribute("facil.feature", feature)
        span.set_attribute("facil.prompt_hash", prompt_hash)
        if user_role:
            span.set_attribute("facil.user_role", user_role)
        # Phase B.5 — prompt injection assessment on the span
        if injection_risk != "none":
            span.set_attribute("ai_security.risk", injection_risk)
            span.set_attribute("ai_security.score", injection_score)

        start = time.monotonic()
        status = "error"
        error_class: Optional[str] = None
        finish_reason: Optional[str] = None
        input_tokens = 0
        output_tokens = 0
        cost_xaf = 0.0

        try:
            response = await invoke(model, prompt)

            # Extract Gemini-style usage metadata when available.
            um = getattr(response, "usage_metadata", None)
            if um is not None:
                input_tokens = int(getattr(um, "prompt_token_count", 0) or 0)
                output_tokens = int(getattr(um, "candidates_token_count", 0) or 0)
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)

            cands = getattr(response, "candidates", None)
            if cands and len(cands) > 0:
                fr = getattr(cands[0], "finish_reason", None)
                if fr is not None:
                    finish_reason = str(fr)
                    span.set_attribute("gen_ai.response.finish_reasons", [finish_reason])

            cost_xaf = estimate_cost_xaf(model_name, input_tokens, output_tokens)
            if cost_xaf:
                span.set_attribute("facil.cost_xaf", cost_xaf)

            status = "success"
            return response

        except Exception as exc:
            error_class = exc.__class__.__name__
            status = classify_error(exc)
            span.record_exception(exc)
            if _OTEL_AVAILABLE and _otel_trace is not None:
                span.set_status(_otel_trace.Status(_otel_trace.StatusCode.ERROR, status))
            span.set_attribute("error.class", error_class)
            raise

        finally:
            latency_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("facil.latency_ms", latency_ms)

            # Fire-and-forget persist. Track for graceful shutdown.
            task = asyncio.create_task(_persist_metric(
                pool=pool,
                trace_id=trace_id, span_id=span_id,
                provider=provider, model_name=model_name, operation=operation,
                feature=feature, user_id=user_id, user_role=user_role,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_xaf=cost_xaf, latency_ms=latency_ms,
                finish_reason=finish_reason, status=status,
                error_class=error_class, prompt_hash=prompt_hash,
                # Phase C.1 — injection assessment (mig 328)
                injection_risk=injection_risk if injection_risk != "none" else None,
                injection_score=injection_score,
                injection_rules=injection_rules,
            ))
            _track_task(task)


__all__ = [
    "traced_generate",
    "traced_generate_sync",
    "traced_embed",
    "traced_embed_sync",
    "estimate_cost_xaf",
    "hash_prompt",
    "classify_error",
    "flush_pending_persists",
    "PRICING_XAF",
]
