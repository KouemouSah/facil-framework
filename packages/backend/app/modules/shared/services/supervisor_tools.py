"""
Supervisor Core Tools — 8 SQL functions for entity workflow supervision.

These functions are used by DynamicAnalystService("supervisor") to answer
questions about service requests, agent workload, SLA, and pipeline
for ANY entity with workflow_codes.

All functions:
  - Accept (db, **kwargs) where kwargs includes _entity_code, _entity_location_id, _is_main_office
  - Use parameterized queries ($1, $2) — NEVER string interpolation
  - Are scoped by entity_code + entity_location_id (satellite = site-only, main_office = all)
  - Return JSON-serializable dicts
  - Handle 0 rows gracefully (empty results, not errors)

Site scoping model:
  service_requests HAS entity_location_id column → direct WHERE filter (no subselect)
  agent_profiles HAS entity_location_id column → direct WHERE filter
"""

import asyncio
import json

from app.core.ai_telemetry import traced_generate_sync
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

try:
    from vertexai.generative_models import FunctionDeclaration
    _VERTEX_AVAILABLE = True
except ImportError:
    _VERTEX_AVAILABLE = False


# ── Site scoping helper ──────────────────────────────────────────────────────

def _site_filter(kwargs: dict, alias: str, param_offset: int, col: str = "entity_location_id"):
    """Build site-scoping WHERE clause for service_requests or agent_profiles.

    Returns (sql_clause, params) — empty if main_office or no location.
    Unlike Treasury (which needs subselect via validated_by_agent_id),
    service_requests and agent_profiles have entity_location_id directly.
    """
    is_main = kwargs.get("_is_main_office", True)
    location_id = kwargs.get("_entity_location_id")
    if is_main or not location_id:
        return "", []
    param_num = param_offset + 1
    return f"AND {alias}.{col} = ${param_num}", [location_id]


# ── Terminal statuses (requests considered "done") ───────────────────────────

_TERMINAL_STATUSES = ("COMPLETED", "REJECTED", "EXPIRED", "CANCELLED")

# ============================================================================
# 8 SQL FUNCTIONS
# ============================================================================

async def get_request_stats(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    """Count service requests by status and workflow for the entity."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "sr", 2)

    # By status
    by_status = await db.fetch(f"""
        SELECT sr.status::text AS status, COUNT(*) AS count
        FROM service_requests sr
        WHERE sr.entity_code = $1
          AND sr.created_at >= NOW() - make_interval(days => $2)
          {sc}
        GROUP BY sr.status
        ORDER BY count DESC
    """, entity_code, days, *sp)

    # By workflow
    by_workflow = await db.fetch(f"""
        SELECT sr.workflow_code, sr.status::text AS status, COUNT(*) AS count
        FROM service_requests sr
        WHERE sr.entity_code = $1
          AND sr.created_at >= NOW() - make_interval(days => $2)
          {sc}
        GROUP BY sr.workflow_code, sr.status
        ORDER BY sr.workflow_code, count DESC
    """, entity_code, days, *sp)

    total = sum(r["count"] for r in by_status)
    return {
        "entity_code": entity_code,
        "period_days": days,
        "total": total,
        "by_status": [{"status": r["status"], "count": r["count"]} for r in by_status],
        "by_workflow": [
            {"workflow": r["workflow_code"], "status": r["status"], "count": r["count"]}
            for r in by_workflow
        ],
    }


async def get_request_pipeline(db, **kwargs) -> Dict[str, Any]:
    """Status funnel for the entity (last 90 days)."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "sr", 1)

    # Ordered pipeline with amounts
    rows = await db.fetch(f"""
        SELECT sr.status::text AS status,
               COUNT(*) AS count,
               COALESCE(SUM(sr.total_amount), 0) AS amount
        FROM service_requests sr
        WHERE sr.entity_code = $1
          AND sr.created_at >= NOW() - INTERVAL '90 days'
          {sc}
        GROUP BY sr.status
        ORDER BY CASE sr.status::text
            WHEN 'DRAFT' THEN 1
            WHEN 'SUBMITTED' THEN 2
            WHEN 'UNDER_REVIEW' THEN 3
            WHEN 'DOCUMENTS_REQUIRED' THEN 4
            WHEN 'DOSSIER_VALIDE' THEN 5
            WHEN 'PAYMENT_PENDING' THEN 6
            WHEN 'PAID' THEN 7
            WHEN 'CITA_SCHEDULED' THEN 8
            WHEN 'IN_PROGRESS' THEN 9
            WHEN 'COMPLETED' THEN 10
            WHEN 'REJECTED' THEN 11
            ELSE 12
        END
    """, entity_code, *sp)

    return {
        "entity_code": entity_code,
        "period": "90 days",
        "stages": [
            {"status": r["status"], "count": r["count"], "amount": float(r["amount"])}
            for r in rows
        ],
    }


async def get_request_sla(db, **kwargs) -> Dict[str, Any]:
    """SLA analysis: average processing times and overdue requests."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "sr", 1)

    row = await db.fetchrow(f"""
        WITH times AS (
            SELECT sr.id, sr.status::text AS status,
                EXTRACT(EPOCH FROM (sr.validated_at - sr.submitted_at)) / 3600.0 AS hours_to_validate,
                EXTRACT(EPOCH FROM (sr.completed_at - sr.submitted_at)) / 3600.0 AS hours_total,
                EXTRACT(EPOCH FROM (NOW() - sr.submitted_at)) / 3600.0 AS hours_pending
            FROM service_requests sr
            WHERE sr.entity_code = $1
              AND sr.submitted_at >= NOW() - INTERVAL '90 days'
              {sc}
        )
        SELECT
            COUNT(*) AS total,
            ROUND(AVG(hours_to_validate) FILTER (WHERE hours_to_validate IS NOT NULL)::numeric, 1) AS avg_validation_hours,
            ROUND(AVG(hours_total) FILTER (WHERE hours_total IS NOT NULL)::numeric, 1) AS avg_total_hours,
            COUNT(*) FILTER (
                WHERE status NOT IN ('COMPLETED','REJECTED','EXPIRED','CANCELLED')
                  AND hours_pending > 48
            ) AS overdue_48h,
            COUNT(*) FILTER (
                WHERE status NOT IN ('COMPLETED','REJECTED','EXPIRED','CANCELLED')
                  AND hours_pending > 120
            ) AS overdue_5d,
            COUNT(*) FILTER (
                WHERE status NOT IN ('COMPLETED','REJECTED','EXPIRED','CANCELLED')
                  AND hours_pending > 360
            ) AS overdue_15d,
            COUNT(*) FILTER (
                WHERE status NOT IN ('COMPLETED','REJECTED','EXPIRED','CANCELLED')
            ) AS active_count
        FROM times
    """, entity_code, *sp)

    active = row["active_count"] or 0
    overdue_48h = row["overdue_48h"] or 0
    return {
        "entity_code": entity_code,
        "period": "90 days",
        "total_requests": row["total"] or 0,
        "active_requests": active,
        "avg_validation_hours": float(row["avg_validation_hours"]) if row["avg_validation_hours"] else None,
        "avg_total_hours": float(row["avg_total_hours"]) if row["avg_total_hours"] else None,
        "overdue_48h": overdue_48h,
        "overdue_5d": row["overdue_5d"] or 0,
        "overdue_15d": row["overdue_15d"] or 0,
        "sla_compliance_pct": round((active - overdue_48h) / max(active, 1) * 100, 1),
    }


async def get_request_rejections(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    """Rejection analysis: rates by workflow, top rejection reasons."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "sr", 2)

    # Rejection rate by workflow
    by_workflow = await db.fetch(f"""
        SELECT sr.workflow_code,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE sr.status = 'REJECTED') AS rejected
        FROM service_requests sr
        WHERE sr.entity_code = $1
          AND sr.created_at >= NOW() - make_interval(days => $2)
          {sc}
        GROUP BY sr.workflow_code
        ORDER BY rejected DESC
    """, entity_code, days, *sp)

    # Top rejection reasons
    top_reasons = await db.fetch(f"""
        SELECT sr.workflow_code, sr.rejection_reason, COUNT(*) AS count
        FROM service_requests sr
        WHERE sr.entity_code = $1
          AND sr.status = 'REJECTED'
          AND sr.rejection_reason IS NOT NULL
          AND sr.updated_at >= NOW() - make_interval(days => $2)
          {sc}
        GROUP BY sr.workflow_code, sr.rejection_reason
        ORDER BY count DESC
        LIMIT 10
    """, entity_code, days, *sp)

    total_all = sum(r["total"] for r in by_workflow)
    total_rejected = sum(r["rejected"] for r in by_workflow)
    return {
        "entity_code": entity_code,
        "period_days": days,
        "total_requests": total_all,
        "total_rejected": total_rejected,
        "rejection_rate_pct": round(total_rejected / max(total_all, 1) * 100, 1),
        "by_workflow": [
            {
                "workflow": r["workflow_code"],
                "total": r["total"],
                "rejected": r["rejected"],
                "rate_pct": round(r["rejected"] / max(r["total"], 1) * 100, 1),
            }
            for r in by_workflow
        ],
        "top_reasons": [
            {"workflow": r["workflow_code"], "reason": r["rejection_reason"], "count": r["count"]}
            for r in top_reasons
        ],
    }


async def get_request_trends(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    """Daily submission and completion trends."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "sr", 2)

    rows = await db.fetch(f"""
        SELECT DATE(sr.created_at) AS date,
               COUNT(*) AS submitted,
               COUNT(*) FILTER (WHERE sr.status = 'COMPLETED') AS completed,
               COUNT(*) FILTER (WHERE sr.status = 'REJECTED') AS rejected
        FROM service_requests sr
        WHERE sr.entity_code = $1
          AND sr.created_at >= NOW() - make_interval(days => $2)
          {sc}
        GROUP BY DATE(sr.created_at)
        ORDER BY date
    """, entity_code, days, *sp)

    return {
        "entity_code": entity_code,
        "period_days": days,
        "data_points": len(rows),
        "daily": [
            {
                "date": str(r["date"]),
                "submitted": r["submitted"],
                "completed": r["completed"],
                "rejected": r["rejected"],
            }
            for r in rows
        ],
    }


async def get_entity_agents(db, **kwargs) -> Dict[str, Any]:
    """List agents for the entity with workload and availability."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "ap", 1, col="entity_location_id")

    rows = await db.fetch(f"""
        SELECT u.full_name,
               ap.is_supervisor,
               aw.availability::text AS availability,
               aw.workload_status::text AS workload_status,
               aw.current_assignments,
               aw.max_concurrent_assignments,
               ROUND(COALESCE(aw.capacity_percentage, 0)::numeric, 0) AS capacity_pct,
               aw.success_rate,
               aw.avg_processing_time_hours,
               el.location_name AS site_name,
               el.city
        FROM agent_profiles ap
        JOIN users u ON u.id = ap.user_id
        JOIN entities e ON e.id = ap.entity_id
        LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
        LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
        WHERE e.code = $1
          AND ap.is_active = true
          {sc}
        ORDER BY ap.is_supervisor DESC, u.full_name
    """, entity_code, *sp)

    return {
        "entity_code": entity_code,
        "total_agents": len(rows),
        "available": sum(1 for r in rows if r["availability"] in ("available", None)),
        "agents": [
            {
                "name": r["full_name"],
                "is_supervisor": r["is_supervisor"],
                "availability": r["availability"] or "available",
                "workload_status": r["workload_status"] or "available",
                "current_assignments": r["current_assignments"] or 0,
                "max_assignments": r["max_concurrent_assignments"] or 0,
                "capacity_pct": float(r["capacity_pct"]) if r["capacity_pct"] else 0,
                "success_rate": float(r["success_rate"]) if r["success_rate"] else None,
                "avg_hours": float(r["avg_processing_time_hours"]) if r["avg_processing_time_hours"] else None,
                "site": r["site_name"] or "N/A",
                "city": r["city"] or "",
            }
            for r in rows
        ],
    }


async def get_agent_ranking(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    """Agent performance ranking for the entity."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "ap", 1, col="entity_location_id")

    rows = await db.fetch(f"""
        SELECT u.full_name,
               aps.current_month_processed AS processed,
               aps.current_month_approved AS approved,
               aps.current_month_rejected AS rejected,
               aps.current_month_escalated AS escalated,
               ROUND(COALESCE(aps.avg_processing_minutes, 0)::numeric, 0) AS avg_minutes,
               ROUND(COALESCE(aps.sla_respect_percentage, 0)::numeric, 1) AS sla_pct,
               aps.last_action_at
        FROM agent_performance_stats aps
        JOIN agent_profiles ap ON ap.id = aps.agent_profile_id
        JOIN users u ON u.id = ap.user_id
        JOIN entities e ON e.id = ap.entity_id
        WHERE e.code = $1
          AND ap.is_active = true
          {sc}
        ORDER BY aps.current_month_processed DESC NULLS LAST
    """, entity_code, *sp)

    return {
        "entity_code": entity_code,
        "agents": [
            {
                "name": r["full_name"],
                "processed": r["processed"] or 0,
                "approved": r["approved"] or 0,
                "rejected": r["rejected"] or 0,
                "escalated": r["escalated"] or 0,
                "avg_minutes": float(r["avg_minutes"]) if r["avg_minutes"] else 0,
                "sla_pct": float(r["sla_pct"]) if r["sla_pct"] else 0,
                "last_action": str(r["last_action_at"]) if r["last_action_at"] else None,
            }
            for r in rows
        ],
    }


async def get_pending_detail(db, limit: int = 20, **kwargs) -> Dict[str, Any]:
    """Detailed list of pending/active requests."""
    entity_code = kwargs.get("_entity_code", "")
    sc, sp = _site_filter(kwargs, "sr", 2)

    rows = await db.fetch(f"""
        SELECT sr.reference, sr.workflow_code, sr.status::text AS status,
               u.full_name AS citizen_name,
               ROUND(EXTRACT(EPOCH FROM (NOW() - sr.submitted_at)) / 3600.0) AS hours_pending,
               sr.submitted_at,
               sr.priority::text AS priority,
               ag.full_name AS assigned_agent
        FROM service_requests sr
        LEFT JOIN users u ON u.id = sr.user_id
        LEFT JOIN users ag ON ag.id = sr.assigned_to
        WHERE sr.entity_code = $1
          AND sr.status::text NOT IN ('COMPLETED', 'REJECTED', 'EXPIRED', 'CANCELLED')
          {sc}
        ORDER BY sr.submitted_at ASC
        LIMIT $2
    """, entity_code, limit, *sp)

    return {
        "entity_code": entity_code,
        "total_pending": len(rows),
        "requests": [
            {
                "reference": r["reference"],
                "workflow": r["workflow_code"],
                "status": r["status"],
                "citizen": r["citizen_name"] or "N/A",
                "hours_pending": float(r["hours_pending"]) if r["hours_pending"] else 0,
                "submitted_at": str(r["submitted_at"]) if r["submitted_at"] else None,
                "priority": r["priority"] or "normal",
                "assigned_to": r["assigned_agent"] or "Sin asignar",
            }
            for r in rows
        ],
    }


# ============================================================================
# WORKFLOW CONFIG FUNCTIONS (reads PredefinedWorkflow objects — no SQL)
# ============================================================================

async def get_workflow_config(db, workflow_code: str = "", **kwargs) -> Dict[str, Any]:
    """Get workflow configuration: documents required, steps, metadata.

    Reads from PredefinedWorkflow objects registered in WorkflowEngine.
    No SQL — these are code-defined configurations.
    """
    from app.modules.service_requests.services.workflow_engine import workflow_engine
    from app.modules.service_requests.models.enums import SolicitudType

    if not workflow_code:
        # List all workflows for the entity — use workflow_codes from context
        entity_code = kwargs.get("_entity_code", "")
        wf_codes = kwargs.get("workflow_codes") or []
        seen = set()
        entity_workflows = []
        for code in wf_codes:
            wf = workflow_engine.get_workflow_by_string(code)
            if wf and id(wf) not in seen:
                seen.add(id(wf))
                entity_workflows.append(wf)
        if not entity_workflows:
            return {"entity_code": entity_code, "workflows": [], "message": "No hay workflows para esta entidad."}

        return {
            "entity_code": entity_code,
            "workflows": [
                {
                    "code": w.workflow_code.value,
                    "name": w.service_name_es,
                    "category": w.category.value,
                    "requires_appointment": w.requires_appointment,
                    "requires_agent_review": w.requires_agent_review,
                    "allowed_types": [t.value for t in w.allowed_solicitud_types],
                    "total_steps": w.get_total_steps(),
                }
                for w in entity_workflows
            ],
        }

    # Specific workflow
    wf = workflow_engine.get_workflow_by_string(workflow_code)
    if not wf:
        return {"error": f"Workflow '{workflow_code}' no encontrado."}

    # Steps
    steps = wf.get_steps()
    steps_info = [
        {
            "number": s.step_number,
            "id": s.step_id,
            "type": s.step_type.value,
            "title": s.title_es,
        }
        for s in steps
    ]

    # Documents for each solicitud_type
    docs_by_type = {}
    for sol_type in wf.allowed_solicitud_types:
        try:
            docs = wf.get_document_requirements(sol_type)
            docs_by_type[sol_type.value] = [
                {
                    "code": d.document_code,
                    "name": d.document_name_es,
                    "required": d.is_required,
                    "faces": d.faces_required,
                    "condition": d.condition_type.value if d.condition_type else "always",
                }
                for d in docs
            ]
        except Exception:
            docs_by_type[sol_type.value] = []

    return {
        "workflow_code": wf.workflow_code.value,
        "name": wf.service_name_es,
        "category": wf.category.value,
        "entity_code": wf.entity_code.value if hasattr(wf, 'entity_code') else "N/A",
        "requires_appointment": wf.requires_appointment,
        "requires_agent_review": wf.requires_agent_review,
        "requires_nota_ingreso": wf.requires_nota_ingreso,
        "allowed_types": [t.value for t in wf.allowed_solicitud_types],
        "sub_types": wf.allowed_sub_types if hasattr(wf, 'allowed_sub_types') else [],
        "total_steps": len(steps_info),
        "steps": steps_info,
        "documents_by_type": docs_by_type,
    }


async def get_workflow_tariffs(db, workflow_code: str = "", **kwargs) -> Dict[str, Any]:
    """Get tariff breakdown for a workflow: base price, supplements, totals.

    Reads DIRECTLY from PredefinedWorkflow TariffConfig — no SQL.
    Reads fixed_amounts dict directly to avoid case-sensitivity bug in get_tariff().
    """
    from app.modules.service_requests.services.workflow_engine import workflow_engine

    if not workflow_code:
        # List tariffs for all entity workflows — use workflow_codes from context
        entity_code = kwargs.get("_entity_code", "")
        wf_codes = kwargs.get("workflow_codes") or []
        seen = set()
        entity_workflows = []
        for code in wf_codes:
            wf = workflow_engine.get_workflow_by_string(code)
            if wf and id(wf) not in seen:
                seen.add(id(wf))
                entity_workflows.append(wf)
        if not entity_workflows:
            return {"entity_code": entity_code, "tariffs": [], "message": "No hay workflows para esta entidad."}

        tariffs = []
        for wf in entity_workflows:
            tariff_data = _extract_tariff_data(wf)
            tariffs.extend(tariff_data)
        return {"entity_code": entity_code, "tariffs": tariffs}

    # Specific workflow
    wf = workflow_engine.get_workflow_by_string(workflow_code)
    if not wf:
        return {"error": f"Workflow '{workflow_code}' no encontrado."}

    return {
        "workflow_code": wf.workflow_code.value,
        "workflow_name": wf.service_name_es,
        "tariffs": _extract_tariff_data(wf),
    }


def _extract_tariff_data(wf) -> List[Dict[str, Any]]:
    """Extract all tariff data from a PredefinedWorkflow.

    Reads TariffConfig.fixed_amounts directly (avoids get_tariff .upper() bug).
    Includes supplements with unit_price, quantity, subtotal.
    """
    config = wf.get_tariff_config()
    if not config:
        return []

    # Build supplements list once (same for all types)
    supplements = [
        {
            "code": s.code,
            "name_es": s.name_es,
            "unit_price": s.unit_price,
            "quantity": s.quantity,
            "subtotal": s.subtotal,
            "is_required": s.is_required,
        }
        for s in (config.supplements or [])
    ]
    supplements_total = sum(s["subtotal"] for s in supplements)

    tariffs = []
    for key, base_amount in (config.fixed_amounts or {}).items():
        tariffs.append({
            "workflow_code": wf.workflow_code.value,
            "workflow_name": wf.service_name_es,
            "tariff_key": key,
            "base_amount": base_amount,
            "supplements": supplements,
            "supplements_total": supplements_total,
            "total_amount": base_amount + supplements_total,
            "currency": config.currency,
            "tariff_type": config.tariff_type.value,
        })

    # Fallback: if no fixed_amounts, still return the config info
    if not tariffs:
        tariffs.append({
            "workflow_code": wf.workflow_code.value,
            "workflow_name": wf.service_name_es,
            "tariff_key": "default",
            "base_amount": 0,
            "supplements": supplements,
            "supplements_total": supplements_total,
            "total_amount": supplements_total,
            "currency": config.currency,
            "tariff_type": config.tariff_type.value,
        })

    return tariffs


# ============================================================================
# FUNCTION MAP + DECLARATIONS
# ============================================================================

SUPERVISOR_FUNCTION_MAP: Dict[str, Callable] = {
    "get_request_stats": lambda db, **kw: get_request_stats(db, kw.get("days", 30), **kw),
    "get_request_pipeline": lambda db, **kw: get_request_pipeline(db, **kw),
    "get_request_sla": lambda db, **kw: get_request_sla(db, **kw),
    "get_request_rejections": lambda db, **kw: get_request_rejections(db, kw.get("days", 30), **kw),
    "get_request_trends": lambda db, **kw: get_request_trends(db, kw.get("days", 30), **kw),
    "get_entity_agents": lambda db, **kw: get_entity_agents(db, **kw),
    "get_agent_ranking": lambda db, **kw: get_agent_ranking(db, **kw),
    "get_pending_detail": lambda db, **kw: get_pending_detail(db, kw.get("limit", 20), **kw),
    "get_workflow_config": lambda db, **kw: get_workflow_config(db, kw.get("workflow_code", ""), **kw),
    "get_workflow_tariffs": lambda db, **kw: get_workflow_tariffs(db, kw.get("workflow_code", ""), **kw),
}

# Gemini FunctionDeclarations — only available when Vertex AI SDK is installed
SUPERVISOR_FUNC_DECLS: list = []

if _VERTEX_AVAILABLE:
    SUPERVISOR_FUNC_DECLS = [
        FunctionDeclaration(
            name="get_request_stats",
            description=(
                "Obtener estadísticas de solicitudes por estado y workflow. "
                "Muestra cuántas solicitudes hay en cada estado (SUBMITTED, UNDER_REVIEW, etc.) "
                "y por cada workflow (PASAPORTE_NUEVO, CONDUCIR_RENOVACION, etc.)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Período en días (default 30)",
                    },
                },
            },
        ),
        FunctionDeclaration(
            name="get_request_pipeline",
            description=(
                "Ver el pipeline/funnel de solicitudes: cuántas en cada etapa del proceso "
                "(DRAFT → SUBMITTED → UNDER_REVIEW → COMPLETED). Incluye montos."
            ),
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="get_request_sla",
            description=(
                "Analizar los tiempos de procesamiento (SLA): tiempo promedio de validación, "
                "tiempo total, solicitudes en retardo (>48h, >5 días, >15 días)."
            ),
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="get_request_rejections",
            description=(
                "Análisis de rechazos: tasa de rechazo por workflow, "
                "motivos de rechazo más frecuentes."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Período en días (default 30)",
                    },
                },
            },
        ),
        FunctionDeclaration(
            name="get_request_trends",
            description=(
                "Tendencias diarias de solicitudes: volumen de envíos, "
                "completados y rechazados por día."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Período en días (default 30)",
                    },
                },
            },
        ),
        FunctionDeclaration(
            name="get_entity_agents",
            description=(
                "Lista de agentes de la entidad con su disponibilidad, "
                "carga de trabajo, tasa de éxito y sitio."
            ),
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="get_agent_ranking",
            description=(
                "Ranking de rendimiento de los agentes: procesados, aprobados, "
                "rechazados, escalados, tiempo promedio, cumplimiento SLA."
            ),
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="get_pending_detail",
            description=(
                "Lista detallada de solicitudes pendientes/activas: "
                "referencia, workflow, ciudadano, horas en espera, agente asignado."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de resultados (default 20)",
                    },
                },
            },
        ),
        FunctionDeclaration(
            name="get_workflow_config",
            description=(
                "Configuración de un workflow: documentos requeridos, pasos del proceso, "
                "tipo de solicitud permitido, si requiere cita o revisión de agente. "
                "Sin workflow_code: lista todos los workflows de la entidad."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "workflow_code": {
                        "type": "string",
                        "description": (
                            "Código del workflow (ej: PASAPORTE_NUEVO, CONDUCIR_RENOVACION). "
                            "Si no se proporciona, lista todos los workflows de la entidad."
                        ),
                    },
                },
            },
        ),
        FunctionDeclaration(
            name="get_workflow_tariffs",
            description=(
                "Tarifas de un workflow: precio base, suplementos, total por tipo de solicitud. "
                "Sin workflow_code: lista tarifas de todos los workflows de la entidad."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "workflow_code": {
                        "type": "string",
                        "description": (
                            "Código del workflow (ej: PASAPORTE_NUEVO, CONDUCIR_RENOVACION). "
                            "Si no se proporciona, lista tarifas de todos los workflows."
                        ),
                    },
                },
            },
        ),
    ]


# ============================================================================
# PROMPT TEMPLATE
# ============================================================================

SUPERVISOR_PROMPT_TEMPLATE = """Eres el asistente IA del supervisor de {entity_name}.
Sitio: {site_name} ({city}).

Workflows gestionados por esta entidad:
{workflow_list}

Agentes activos: {agent_count} | Disponibles: {available_count}

Tu rol es analizar las solicitudes de servicio, el rendimiento de los agentes,
los tiempos de procesamiento (SLA) y el pipeline de workflows para esta entidad.

REGLAS ESTRICTAS:
- NUNCA inventes datos. Solo usa las funciones proporcionadas.
- Responde SIEMPRE en español.
- Cita cifras EXACTAS retornadas por las funciones.
- Si no hay datos suficientes, dilo explícitamente.
- Todos los montos en XAF (Franco CFA).
- Analiza tendencias y propón acciones concretas cuando sea pertinente.
- Sé factual y conciso (máximo 500 palabras).
- Fecha actual: {current_date} ({day_of_week}).

RAZONAMIENTO ANTES DE RESPONDER (Chain-of-Thought):
Antes de llamar funciones, RAZONA internamente:
1. ¿Qué métricas necesito sobre esta entidad para responder?
2. ¿Qué funciones debo llamar y en qué orden?
3. ¿Necesito cruzar datos de pipeline + SLA + agentes para una visión completa?
4. ¿Cómo presentar los resultados para que el supervisor actúe inmediatamente?

FORMATOS DE PRESENTACIÓN — elige el más apropiado:
- Dato único → negrita inline
- Pipeline/funnel → tabla con etapas y cantidades
- SLA → tabla con ✓/✗ por indicador + % cumplimiento
- Ranking agentes → tabla ordenada con posición
- Alerta → > **Atención:** SLA en riesgo
- Resumen ejecutivo → ficha con ▸ KPIs
- Formato mixto → combinar (el más efectivo para supervisión)

ESTRATEGIA DE FUNCIONES — MUY IMPORTANTE:
DEBES llamar al menos una función. Las respuestas sin datos son inútiles.

| Pregunta del usuario | Función(es) a llamar |
|---------------------|---------------------|
| Estadísticas, resumen, cuántas solicitudes | get_request_stats |
| Pipeline, funnel, etapas, flujo | get_request_pipeline |
| SLA, tiempos, retrasos, en retardo | get_request_sla |
| Rechazos, motivos rechazo, tasa rechazo | get_request_rejections |
| Tendencias, volumen diario, evolución | get_request_trends |
| Agentes, disponibilidad, carga trabajo | get_entity_agents |
| Rendimiento, ranking, mejores agentes | get_agent_ranking |
| Pendientes, en espera, detalle solicitudes | get_pending_detail |
| Documentos requeridos, pasos, configuración workflow | get_workflow_config |
| Precios, tarifas, suplementos, cuánto cuesta | get_workflow_tariffs |
| Visión general, briefing | get_request_stats + get_request_sla + get_entity_agents |
"""


# ============================================================================
# ARTIFACTS BUILDER
# ============================================================================

def supervisor_build_artifacts(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build typed artifacts from supervisor tool results."""
    artifacts: List[Dict[str, Any]] = []

    for tool_name, data in tool_results.items():
        if isinstance(data, dict) and "error" in data:
            continue

        if tool_name == "get_request_stats":
            artifacts.append({
                "type": "kpi_grid",
                "title": f"Solicitudes ({data.get('period_days', 30)} días)",
                "metrics": [
                    {"label": "Total", "value": str(data.get("total", 0))},
                ] + [
                    {"label": s["status"], "value": str(s["count"])}
                    for s in (data.get("by_status") or [])[:6]
                ],
            })

        elif tool_name == "get_request_pipeline":
            stages = data.get("stages") or []
            if stages:
                artifacts.append({
                    "type": "table",
                    "title": "Pipeline de Solicitudes",
                    "headers": ["Estado", "Cantidad", "Monto (XAF)"],
                    "rows": [
                        [s["status"], str(s["count"]), f"{s['amount']:,.0f}"]
                        for s in stages
                    ],
                    "alignments": ["left", "right", "right"],
                })

        elif tool_name == "get_request_sla":
            artifacts.append({
                "type": "kpi_grid",
                "title": "Análisis SLA",
                "metrics": [
                    {"label": "Solicitudes activas", "value": str(data.get("active_requests", 0))},
                    {"label": "Retardo >48h", "value": str(data.get("overdue_48h", 0))},
                    {"label": "Retardo >5d", "value": str(data.get("overdue_5d", 0))},
                    {"label": "Cumplimiento SLA", "value": f"{data.get('sla_compliance_pct', 0)}%"},
                ],
            })

        elif tool_name == "get_entity_agents":
            agents = data.get("agents") or []
            if agents:
                artifacts.append({
                    "type": "table",
                    "title": f"Agentes ({data.get('total_agents', 0)})",
                    "headers": ["Nombre", "Disponibilidad", "Carga", "Asignaciones", "Sitio"],
                    "rows": [
                        [
                            a["name"],
                            a["availability"],
                            f"{a['capacity_pct']:.0f}%",
                            f"{a['current_assignments']}/{a['max_assignments']}",
                            a["site"],
                        ]
                        for a in agents
                    ],
                    "alignments": ["left", "left", "right", "right", "left"],
                })

        elif tool_name == "get_request_rejections":
            by_wf = data.get("by_workflow") or []
            if by_wf:
                artifacts.append({
                    "type": "table",
                    "title": f"Rechazos ({data.get('period_days', 30)} días) — Tasa global: {data.get('rejection_rate_pct', 0)}%",
                    "headers": ["Workflow", "Total", "Rechazados", "Tasa"],
                    "rows": [
                        [w["workflow"], str(w["total"]), str(w["rejected"]), f"{w['rate_pct']}%"]
                        for w in by_wf
                    ],
                    "alignments": ["left", "right", "right", "right"],
                })

        elif tool_name == "get_request_trends":
            daily = data.get("daily") or []
            if daily:
                total_sub = sum(d["submitted"] for d in daily)
                total_comp = sum(d["completed"] for d in daily)
                total_rej = sum(d["rejected"] for d in daily)
                artifacts.append({
                    "type": "kpi_grid",
                    "title": f"Tendencias ({data.get('period_days', 30)} días)",
                    "metrics": [
                        {"label": "Días con datos", "value": str(len(daily))},
                        {"label": "Total enviadas", "value": str(total_sub)},
                        {"label": "Total completadas", "value": str(total_comp)},
                        {"label": "Total rechazadas", "value": str(total_rej)},
                    ],
                })

        elif tool_name == "get_agent_ranking":
            agents = data.get("agents") or []
            if agents:
                artifacts.append({
                    "type": "table",
                    "title": "Ranking de Agentes",
                    "headers": ["Nombre", "Procesadas", "Aprobadas", "Rechazadas", "Tiempo (min)", "SLA %"],
                    "rows": [
                        [
                            a["name"],
                            str(a["processed"]),
                            str(a["approved"]),
                            str(a["rejected"]),
                            str(a["avg_minutes"]),
                            f"{a['sla_pct']}%",
                        ]
                        for a in agents
                    ],
                    "alignments": ["left", "right", "right", "right", "right", "right"],
                })

        elif tool_name == "get_pending_detail":
            requests = data.get("requests") or []
            if requests:
                artifacts.append({
                    "type": "table",
                    "title": f"Solicitudes Pendientes ({len(requests)})",
                    "headers": ["Referencia", "Workflow", "Estado", "Ciudadano", "Horas", "Agente"],
                    "rows": [
                        [
                            r["reference"] or "—",
                            r["workflow"],
                            r["status"],
                            r["citizen"],
                            f"{r['hours_pending']:.0f}h",
                            r["assigned_to"],
                        ]
                        for r in requests[:15]  # Cap display at 15
                    ],
                    "alignments": ["left", "left", "left", "left", "right", "left"],
                })

    return artifacts


# ============================================================================
# SUPERVISOR BRIEFING
# ============================================================================

async def generate_supervisor_briefing(
    db, entity_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate automated briefing for supervisor.

    Runs get_request_stats + get_request_sla + get_entity_agents in parallel,
    then passes aggregated data to Gemini for a natural language summary.

    Args:
        db: Database connection (not used directly — each query gets its own).
        entity_context: Dict with _entity_code, _entity_location_id, _is_main_office, etc.

    Returns:
        {briefing: str, priority: str, recommendations: list}
    """
    from app.database.connection import db_manager

    kwargs = {
        "_entity_code": entity_context.get("entity_code", ""),
        "_entity_location_id": entity_context.get("entity_location_id"),
        "_is_main_office": entity_context.get("is_main_office", True),
        "workflow_codes": entity_context.get("workflow_codes", []),
    }

    async def _safe_stats():
        async with db_manager.get_connection() as conn:
            return await get_request_stats(conn, days=7, **kwargs)

    async def _safe_sla():
        async with db_manager.get_connection() as conn:
            return await get_request_sla(conn, **kwargs)

    async def _safe_agents():
        async with db_manager.get_connection() as conn:
            return await get_entity_agents(conn, **kwargs)

    stats, sla, agents = await asyncio.gather(
        _safe_stats(), _safe_sla(), _safe_agents()
    )

    # Determine priority
    priority = "normal"
    overdue_48h = sla.get("overdue_48h", 0)
    overdue_5d = sla.get("overdue_5d", 0)
    sla_pct = sla.get("sla_compliance_pct", 100)
    if overdue_5d > 0 or sla_pct < 70:
        priority = "urgent"
    elif overdue_48h > 0 or sla_pct < 90:
        priority = "attention"

    # Try LLM briefing
    try:
        from app.modules.shared.services.base_analyst_service import VERTEX_AI_AVAILABLE
        if VERTEX_AI_AVAILABLE:
            from vertexai.generative_models import GenerativeModel, GenerationConfig

            data_summary = json.dumps(
                {"stats_7d": stats, "sla": sla, "agents": agents},
                default=str, ensure_ascii=False,
            )

            briefing_prompt = (
                f"Analiza los datos operativos de la entidad {entity_context.get('entity_name', '')} "
                f"y responde ÚNICAMENTE con un objeto JSON válido "
                f"(sin bloques de código markdown, sin texto adicional).\n\n"
                f"Formato exacto requerido:\n"
                f'{{"briefing": "<resumen ejecutivo 100-150 palabras: solicitudes, SLA, agentes>", '
                f'"recommendations": ["<acción concreta 1>", "<acción concreta 2>", "<acción concreta 3>"]}}\n\n'
                f"Reglas:\n"
                f"- briefing: narrativa fluida en español, markdown básico (**negrita**), cifras exactas\n"
                f"- recommendations: array de 2-4 acciones concretas basadas SOLO en los datos\n"
                f"- NUNCA inventes datos que no aparezcan en los datos proporcionados\n\n"
                f"DATOS:\n{data_summary}"
            )

            from app.config import get_settings as _get_settings
            model = GenerativeModel(_get_settings().GEMINI_CHAT_MODEL)
            response = await asyncio.wait_for(
                traced_generate_sync(
                    model, briefing_prompt,
                    feature="supervisor_tools",
                    generation_config=GenerationConfig(temperature=0.2, max_output_tokens=600),
                ),
                timeout=15.0,
            )

            text = response.text.strip()
            # Clean markdown code blocks if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
            if text.startswith("json"):
                text = text[4:].strip()

            parsed = json.loads(text)
            return {
                "briefing": parsed.get("briefing", ""),
                "priority": priority,
                "recommendations": parsed.get("recommendations", []),
                "agent_type": "supervisor",
            }
    except Exception as exc:
        logger.warning(f"Supervisor briefing LLM failed, using fallback: {exc}")

    # Fallback without LLM
    total = stats.get("total", 0)
    active = sla.get("active_requests", 0)
    agent_count = agents.get("total_agents", 0)
    available = agents.get("available", 0)

    recs = []
    if overdue_5d > 0:
        recs.append(f"Priorizar {overdue_5d} solicitud(es) con más de 5 días de retraso")
    if overdue_48h > 0:
        recs.append(f"Revisar {overdue_48h} solicitud(es) con más de 48h sin procesar")
    if available < agent_count and agent_count > 0:
        recs.append(f"Solo {available}/{agent_count} agentes disponibles — verificar ausencias")
    if not recs:
        recs.append("Situación normal — continuar monitoreo estándar")

    return {
        "briefing": (
            f"**Últimos 7 días**: {total} solicitudes. "
            f"**Activas**: {active}. "
            f"**SLA**: {sla_pct}% cumplimiento ({overdue_48h} >48h, {overdue_5d} >5d). "
            f"**Agentes**: {available}/{agent_count} disponibles."
        ),
        "priority": priority,
        "recommendations": recs,
        "agent_type": "supervisor",
    }
