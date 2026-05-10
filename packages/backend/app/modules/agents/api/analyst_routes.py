"""
Unified Analyst Endpoint — Dynamic agent routing via ToolRegistry.

POST /agents/analyst/ask    — single endpoint for all agent types
GET  /agents/analyst/briefing — unified briefing (treasury + supervisor)

Agent type is resolved 100% from DB (agent_profiles + entities).
No entity names hardcoded in routing logic.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.jsonb import ensure_list

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required

router = APIRouter()


# ── Request / Response Models ────────────────────────────────────────────────

class AnalystAskRequest(BaseModel):
    """Unified request for all analyst agent types."""
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question (3-1000 chars)",
    )
    previous_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Previous Q&A context for drill-down: {question, tools_used}",
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Client-generated session UUID for conversation memory",
    )


class AnalystAskResponse(BaseModel):
    """Unified response from any analyst agent."""
    answer: str
    tools_used: List[str] = []
    data: Dict[str, Any] = {}
    artifacts: List[Dict[str, Any]] = []
    agent_type: Optional[str] = None


# ── Input Sanitization ───────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r'(?i)ignore\s+(previous|above|all)\s+(instructions?|prompts?)'),
    re.compile(r'(?i)you\s+are\s+now\s+'),
    re.compile(r'(?i)system\s*:\s*'),
    re.compile(r'(?i)INST\]'),
    re.compile(r'(?i)\[\/INST\]'),
]


def _sanitize_question(question: str) -> str:
    """Sanitize user question to prevent prompt injection."""
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', question)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub('', cleaned)
    return cleaned.strip()


# ── Agent Context Resolution (100% DB-driven) ───────────────────────────────

# Rate limits per agent_type
_RATE_LIMITS = {
    "treasury": {"max_requests": 20, "window_seconds": 3600},    # 20/hour
    "admin": {"max_requests": 10, "window_seconds": 60},          # 10/min
    "supervisor": {"max_requests": 15, "window_seconds": 60},     # 15/min
    "entity_agent": {"max_requests": 20, "window_seconds": 60},   # 20/min (field agents use it heavily)
    "orchestrator": {"max_requests": 10, "window_seconds": 60},   # 10/min
}

# Cache TTL per agent_type (seconds)
_CACHE_TTL = {
    "treasury": 300,     # 5 min (expensive SQL queries)
    "supervisor": 120,   # 2 min
    "entity_agent": 60,  # 1 min (request-specific data changes fast)
    "admin": 0,          # no cache (real-time)
    "orchestrator": 120, # 2 min
}

# Days of week in Spanish — imported from base
from app.modules.shared.services.base_analyst_service import DAYS_ES as _DAYS_ES


async def _resolve_agent_context(
    db: asyncpg.Connection, user_id: str
) -> Optional[Dict[str, Any]]:
    """Resolve user -> entity context + agent_type for dynamic dispatch.

    Resolution is 100% DB-driven. No entity names hardcoded.
    The agent_type is determined by:
      1. entities.entity_type = 'treasury' → treasury agent (intrinsic entity property)
      2. entities.workflow_codes length > 0 → supervisor agent
      3. Admin users detected separately (superadmin/admin role, no agent_profile needed)
    """
    row = await db.fetchrow("""
        SELECT ap.entity_id, ap.is_supervisor, ap.entity_location_id,
               e.code AS entity_code, e.name AS entity_name,
               e.workflow_codes, e.entity_type::text AS entity_type,
               el.location_name AS site_name, el.city, el.is_main_office
        FROM agent_profiles ap
        JOIN entities e ON e.id = ap.entity_id
        LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
        WHERE ap.user_id = $1 AND ap.is_active = true
        LIMIT 1
    """, user_id)

    if not row:
        return None

    entity_code = row["entity_code"]
    workflow_codes = ensure_list(row["workflow_codes"])
    entity_type = row["entity_type"]

    # Agent type resolution — DB-driven via entity_type + is_supervisor + workflow_codes
    if entity_type == "treasury":
        agent_type = "treasury"
    elif row["is_supervisor"] and len(workflow_codes) > 0:
        agent_type = "supervisor"
    elif len(workflow_codes) > 0:
        # Field agent (CNEDOGE, DGT, Extranjeria, etc.) — entity_agent tools
        agent_type = "entity_agent"
    else:
        # Entity without workflows and not treasury — no agent available
        return None

    # Agent count for supervisor prompt
    agent_count = 0
    available_count = 0
    if agent_type == "supervisor":
        counts = await db.fetchrow("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (
                       WHERE aw.availability = 'available' OR aw.availability IS NULL
                   ) AS available
            FROM agent_profiles ap2
            LEFT JOIN agent_workloads aw ON ap2.id = aw.agent_profile_id
            WHERE ap2.entity_id = $1 AND ap2.is_active = true
        """, row["entity_id"])
        agent_count = counts["total"] or 0
        available_count = counts["available"] or 0

    now = datetime.now(timezone.utc)

    return {
        "agent_type": agent_type,
        "entity_code": entity_code,
        "entity_name": row["entity_name"],
        "entity_location_id": str(row["entity_location_id"]) if row["entity_location_id"] else None,
        "is_main_office": row["is_main_office"] if row["is_main_office"] is not None else True,
        "site_name": row["site_name"] or "Principal",
        "city": row["city"] or "",
        "workflow_codes": workflow_codes,
        "is_supervisor": row["is_supervisor"] or False,
        "agent_count": agent_count,
        "available_count": available_count,
        "current_date": now.strftime("%Y-%m-%d"),
        "day_of_week": _DAYS_ES[now.weekday()],
    }


async def _resolve_admin_agent(
    db: asyncpg.Connection, user_id: str
) -> Optional[Dict[str, Any]]:
    """Check if user has admin role permissions for the admin agent.

    Admin users (superadmin/admin) may not have agent_profiles.
    They access the admin agent via role-based permission check.
    """
    has_perm = await db.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM users u
            JOIN role_permissions rp ON rp.role_id = u.role_id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE u.id = $1 AND p.name = 'agent.view'
        )
    """, user_id)

    if not has_perm:
        return None

    now = datetime.now(timezone.utc)

    return {
        "agent_type": "admin",
        "entity_code": "ADMIN",
        "entity_name": "Administration",
        "entity_location_id": None,
        "is_main_office": True,
        "site_name": "Global",
        "city": "",
        "workflow_codes": [],
        "is_supervisor": False,
        "agent_count": 0,
        "available_count": 0,
        "current_date": now.strftime("%Y-%m-%d"),
        "day_of_week": _DAYS_ES[now.weekday()],
    }


# ── Unified Ask Endpoint ─────────────────────────────────────────────────────

@router.post(
    "/analyst/ask",
    response_model=AnalystAskResponse,
    summary="Ask the AI analyst (unified endpoint)",
    description=(
        "Single endpoint for all AI analyst agents. "
        "Agent type is resolved automatically from user profile. "
        "Supports treasury, supervisor, admin, and orchestrator agents."
    ),
)
async def analyst_ask(
    request: AnalystAskRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("analyst.ask")),
):
    """
    Unified AI analyst endpoint.

    Resolves agent_type from user's agent_profile + entity:
    - Entity with entity_type='treasury' -> treasury agent (17 functions)
    - Entity with workflows -> supervisor agent (10 functions)
    - Admin/superadmin role -> admin agent (11 functions)

    Rate limited per agent_type. Cached per agent_type + question hash.
    """
    from app.core.cache import check_rate_limit, get_cache
    from app.modules.shared.services.dynamic_analyst_service import create_analyst

    user_id = current_user.get("sub") or (
        current_user.id if hasattr(current_user, "id") else None
    )
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    # Resolve agent context from DB
    agent_ctx = await _resolve_agent_context(db, str(user_id))

    # Fallback: check if user is admin (no agent_profile needed)
    if not agent_ctx:
        agent_ctx = await _resolve_admin_agent(db, str(user_id))

    if not agent_ctx:
        raise HTTPException(
            status_code=404,
            detail="No se encontro perfil de agente. Contacte al administrador.",
        )

    agent_type = agent_ctx["agent_type"]

    # Rate limit
    rate_cfg = _RATE_LIMITS.get(agent_type, {"max_requests": 10, "window_seconds": 60})
    is_allowed, _remaining = await check_rate_limit(
        str(user_id),
        f"/agents/analyst/ask/{agent_type}",
        max_requests=rate_cfg["max_requests"],
        window_seconds=rate_cfg["window_seconds"],
    )
    if not is_allowed:
        return AnalystAskResponse(
            answer=(
                f"Has alcanzado el limite de consultas "
                f"({rate_cfg['max_requests']}/{rate_cfg['window_seconds']}s). "
                f"Espera antes de intentar de nuevo."
            ),
            tools_used=[],
            data={},
            artifacts=[],
            agent_type=agent_type,
        )

    # Sanitize input
    sanitized = _sanitize_question(request.question)
    if len(sanitized) < 3:
        return AnalystAskResponse(
            answer="Pregunta demasiado corta o invalida. Escribe una pregunta clara.",
            tools_used=[],
            data={},
            artifacts=[],
            agent_type=agent_type,
        )

    # Build process context (includes workflow_codes for supervisor config functions)
    context: Dict[str, Any] = {
        "user_id": str(user_id),
        "entity_code": agent_ctx.get("entity_code"),
        "entity_location_id": agent_ctx.get("entity_location_id"),
        "is_main_office": agent_ctx.get("is_main_office", True),
        "workflow_codes": agent_ctx.get("workflow_codes", []),
    }

    # Session ID for conversation memory
    if request.session_id:
        context["session_id"] = request.session_id[:128]

    # Previous context for drill-down
    if request.previous_context:
        prev = request.previous_context
        if prev.get("question"):
            context["previous_context"] = {
                "question": str(prev["question"])[:500],
                "tools_used": prev.get("tools_used", []),
            }

    # Cache check
    cache_ttl = _CACHE_TTL.get(agent_type, 0)
    cache_key = None
    if cache_ttl > 0:
        cache = get_cache()
        entity_code_key = agent_ctx.get("entity_code", "global")
        location_key = agent_ctx.get("entity_location_id") or "main"
        question_hash = hashlib.sha256(sanitized.lower().encode()).hexdigest()[:16]
        cache_key = f"analyst:{agent_type}:{entity_code_key}:{location_key}:{question_hash}"
        cached = await cache.get(cache_key)
        if cached:
            cached["agent_type"] = agent_type
            return cached

    # Create dynamic analyst and process
    try:
        analyst = create_analyst(agent_type, agent_ctx)
        result = await analyst.process_question(db, sanitized, context=context)
    except KeyError as e:
        logger.error(f"Analyst: unknown agent_type '{agent_type}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Tipo de agente no registrado: {agent_type}",
        )
    except Exception as e:
        logger.error(f"Analyst: process_question failed ({agent_type}): {e}")
        raise HTTPException(
            status_code=500,
            detail="Error al procesar la pregunta. Intente de nuevo.",
        )

    # Add agent_type to response
    result["agent_type"] = agent_type

    # Cache successful results
    if cache_key and cache_ttl > 0 and result.get("tools_used"):
        cache = get_cache()
        await cache.set(cache_key, result, ttl=cache_ttl)

    return result


# ── Unified Briefing Endpoint ─────────────────────────────────────────────────

@router.get(
    "/analyst/briefing",
    summary="Get automated analyst briefing",
    description="Auto-generated briefing based on agent type. Currently supports treasury.",
)
async def analyst_briefing(
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("analyst.ask")),
):
    """
    Unified briefing endpoint. Resolves agent_type and generates briefing.
    Currently only treasury has a briefing implementation.
    """
    from app.core.cache import get_cache

    user_id = current_user.get("sub") or (
        current_user.id if hasattr(current_user, "id") else None
    )
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    agent_ctx = await _resolve_agent_context(db, str(user_id))
    if not agent_ctx:
        agent_ctx = await _resolve_admin_agent(db, str(user_id))
    if not agent_ctx:
        raise HTTPException(status_code=404, detail="No agent profile found")

    agent_type = agent_ctx["agent_type"]

    # Treasury briefing (existing implementation)
    if agent_type == "treasury":
        from app.modules.service_requests.services.treasury_analyst_service import (
            treasury_analyst_service,
        )

        cache = get_cache()
        scope_key = agent_ctx.get("entity_location_id", "global")
        cache_key = f"analyst:briefing:treasury:{scope_key}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        context = {"user_id": str(user_id), **agent_ctx}
        result = await treasury_analyst_service.generate_briefing(db, context=context)
        await cache.set(cache_key, result, ttl=300)
        return result

    # Supervisor briefing
    if agent_type == "supervisor":
        from app.modules.shared.services.supervisor_tools import (
            generate_supervisor_briefing,
        )

        cache = get_cache()
        scope_key = agent_ctx.get("entity_location_id", agent_ctx.get("entity_code", "global"))
        cache_key = f"analyst:briefing:supervisor:{scope_key}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        result = await generate_supervisor_briefing(db, agent_ctx)
        await cache.set(cache_key, result, ttl=120)  # 2 min cache
        return result

    # Admin/other briefing — not yet implemented
    return {
        "briefing": f"Briefing no disponible para agente tipo '{agent_type}'. En desarrollo.",
        "priority": "info",
        "agent_type": agent_type,
    }


# ── Agent Inventory Endpoint ──────────────────────────────────────────────────

@router.get(
    "/analyst/agents",
    summary="List all registered agent types",
    description="Returns all agents registered in the ToolRegistry with their capabilities.",
)
async def list_registered_agents(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.view_dashboard")),
):
    """List all registered agent types with capabilities (admin only)."""
    from app.modules.shared.services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    agents = []
    for agent_type in registry.list_agent_types():
        ts = registry.get(agent_type)
        agents.append({
            "agent_type": agent_type,
            "label": ts.agent_type_label,
            "has_functions": bool(ts.function_declarations),
            "has_process_fn": ts.process_fn is not None,
            "function_count": len(ts.function_declarations),
            "sub_agents": list(ts.sub_agents.keys()),
        })
    return {"agents": agents, "total": len(agents)}


# ── Token Usage Endpoint ──────────────────────────────────────────────────────

@router.get(
    "/analyst/token-usage",
    summary="Get Vertex AI token usage stats",
    description="Returns aggregated token usage and estimated cost from VertexAIManager.",
)
async def get_token_usage(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.view_dashboard")),
):
    """Return aggregated token usage stats from VertexAIManager (admin only)."""
    from app.modules.shared.services.vertex_ai_manager import VertexAIManager

    manager = VertexAIManager()
    stats = manager.get_stats()
    # Estimate cost: Gemini 2.0 Flash pricing
    # Input: $0.10/1M tokens, Output: $0.40/1M tokens
    input_cost = stats["total_tokens_in"] * 0.0000001
    output_cost = stats["total_tokens_out"] * 0.0000004
    return {
        **stats,
        "estimated_cost_usd": round(input_cost + output_cost, 4),
        "model": "gemini-2.0-flash",
    }
