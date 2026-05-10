"""
Agent Decision Tools — AI-powered DEEP REASONING for agents and supervisors.

Unlike basic SQL tools, these tools use a 2-step pattern:
  Step 1: GATHER — SQL queries collect relevant data
  Step 2: REASON — Gemini analyzes the data with specialized prompts

This makes each tool a mini-agent that produces INTELLIGENT analysis,
not just formatted SQL results.

SECURITY:
- All SQL uses parameterized queries ($1, $2)
- Entity-scoped via _entity_code
- Site-scoped via _entity_location_id + _is_main_office
"""

import asyncio
from typing import Dict, Tuple, List, Optional, Any
from loguru import logger

from app.core.ai_telemetry import traced_generate_sync


def _site_filter(kwargs: dict, alias: str, param_offset: int) -> Tuple[str, List]:
    """Site-scoping: satellite agents see only their location."""
    is_main = kwargs.get("_is_main_office", True)
    location_id = kwargs.get("_entity_location_id")
    if is_main or not location_id:
        return "", []
    return f"AND {alias}.entity_location_id = ${param_offset + 1}", [location_id]


def _entity_filter(kwargs: dict, alias: str, param_offset: int) -> Tuple[str, List]:
    """Entity-scoping."""
    entity_code = kwargs.get("_entity_code", "") or kwargs.get("entity_code", "")
    if not entity_code:
        return "", []
    return f"AND {alias}.entity_code = ${param_offset + 1}", [entity_code]


async def _llm_analyze(data_context: str, analysis_prompt: str) -> str:
    """Call Gemini to REASON about gathered data. Returns analysis text."""
    try:
        from app.modules.shared.services.vertex_ai_manager import VertexAIManager
        from app.config import get_settings
        manager = VertexAIManager()
        if not manager.is_available:
            return "[Analyse IA non disponible — données brutes ci-dessus]"

        settings = get_settings()
        model = manager.create_model(settings.GEMINI_CHAT_MODEL)
        if not model:
            return "[Modèle IA non disponible]"

        prompt = f"{analysis_prompt}\n\nDADOS REALES DEL SISTEMA:\n{data_context}"
        response = await asyncio.wait_for(
            traced_generate_sync(model, prompt, feature="agent_decision"),
            timeout=15.0,
        )
        manager.track_usage(response, "decision_tool")
        return response.text or "[Sin análisis]"
    except Exception as e:
        logger.warning(f"LLM analysis failed: {e}")
        return f"[Analyse automatique non disponible: {e}]"


# ============================================================================
# 1. AI DECISION SUPPORT — Deep reasoning on dossier
# ============================================================================

async def ai_decision_support(db, **kwargs) -> dict:
    """Analyze a dossier with LLM reasoning — recommends approve/reject with justification."""
    reference = kwargs.get("reference", "")
    if not reference:
        return {"error": "Proporcione la referencia del dossier"}

    # GATHER: collect all relevant data
    sr = await db.fetchrow("""
        SELECT sr.id, sr.reference, sr.workflow_code, sr.solicitud_type,
               sr.status::text, sr.total_amount, sr.currency,
               sr.form_data, sr.validations, sr.notes, sr.submitted_at,
               sr.entity_code, sr.rejection_reason, sr.escalated,
               w.name_es as workflow_name, w.sla_hours
        FROM service_requests sr
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        WHERE sr.reference ILIKE '%' || $1 || '%'
        LIMIT 1
    """, reference)

    if not sr:
        return {"error": f"Dossier '{reference}' no encontrado"}

    # Citizen history
    history = await db.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE status::text = 'COMPLETED') as completed,
               COUNT(*) FILTER (WHERE status::text = 'REJECTED') as rejected
        FROM service_requests WHERE user_id = (SELECT user_id FROM service_requests WHERE id = $1)
    """, sr["id"])

    # Similar past decisions
    similar = await db.fetch("""
        SELECT status::text, rejection_reason, total_amount
        FROM service_requests
        WHERE workflow_code = $1 AND status::text IN ('COMPLETED', 'REJECTED')
        ORDER BY updated_at DESC LIMIT 5
    """, sr["workflow_code"])

    # Document count
    doc_count = await db.fetchval("""
        SELECT COUNT(*) FROM uploaded_files
        WHERE user_id = (SELECT user_id FROM service_requests WHERE id = $1)
    """, sr["id"])

    # Build data context for LLM
    data_context = f"""
DOSSIER: {sr['reference']}
Workflow: {sr['workflow_name']} ({sr['workflow_code']})
Type: {sr['solicitud_type']}
Statut actuel: {sr['status']}
Montant: {sr['total_amount']} {sr['currency'] or 'XAF'}
Soumis: {sr['submitted_at']}
Escaladé: {sr['escalated']}
Notes: {sr['notes'] or 'Aucune'}
Validations: {sr['validations'] or 'Aucune'}
Motif rejet précédent: {sr['rejection_reason'] or 'N/A'}

HISTORIQUE CITOYEN:
Total demandes: {history['total']}, Complétées: {history['completed']}, Rejetées: {history['rejected']}
Documents uploadés: {doc_count}

CAS SIMILAIRES RÉCENTS:
{chr(10).join(f"- {s['status']}: {s['total_amount']} XAF, motif rejet: {s['rejection_reason'] or 'N/A'}" for s in similar) if similar else 'Aucun cas similaire trouvé'}
"""

    # REASON: LLM analyzes
    analysis = await _llm_analyze(data_context, """
Eres un analista experto en trámites gubernamentales de Guinea Ecuatorial.
Analiza este dossier y proporciona:
1. EVALUACIÓN DE RIESGO (LOW/MEDIUM/HIGH/CRITICAL) con justificación
2. RECOMENDACIÓN (APROBAR / RECHAZAR / SOLICITAR DOCUMENTOS / ESCALAR) con razones
3. PUNTOS DE ATENCIÓN para el agente (máximo 3)
4. COMPARACIÓN con casos similares previos

Sé factual. Si hay dudas, recomienda revisión adicional.
Responde en español, formato conciso con viñetas.
""")

    return {
        "reference": sr["reference"],
        "workflow": sr["workflow_name"],
        "status": sr["status"],
        "amount": f"{sr['total_amount']} {sr['currency']}" if sr["total_amount"] else None,
        "ai_analysis": analysis,
        "data": {
            "citizen_history": dict(history) if history else {},
            "documents_count": doc_count,
            "similar_cases_count": len(similar),
        },
    }


# ============================================================================
# 2. ASSESS REQUEST RISK — Deep pattern analysis
# ============================================================================

async def assess_request_risk(db, **kwargs) -> dict:
    """Deep risk scoring with LLM pattern analysis."""
    reference = kwargs.get("reference", "")
    if not reference:
        return {"error": "Proporcione la referencia"}

    sr = await db.fetchrow("""
        SELECT sr.id, sr.reference, sr.total_amount, sr.workflow_code,
               sr.form_data, sr.submitted_at, sr.status::text, sr.entity_code,
               w.name_es as workflow_name,
               u.full_name, u.created_at as user_created_at
        FROM service_requests sr
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        LEFT JOIN users u ON u.id = sr.user_id
        WHERE sr.reference ILIKE '%' || $1 || '%'
        LIMIT 1
    """, reference)

    if not sr:
        return {"error": f"Dossier '{reference}' no encontrado"}

    # Gather risk signals
    rejection_count = await db.fetchval("""
        SELECT COUNT(*) FROM service_requests
        WHERE user_id = (SELECT user_id FROM service_requests WHERE id = $1) AND status::text = 'REJECTED'
    """, sr["id"])

    avg_amount = await db.fetchval("""
        SELECT AVG(total_amount) FROM service_requests
        WHERE workflow_code = $1 AND total_amount > 0 AND status::text = 'COMPLETED'
    """, sr["workflow_code"])

    data_context = f"""
DOSSIER: {sr['reference']} — {sr['workflow_name']}
Montant: {sr['total_amount']} XAF (moyenne workflow: {int(avg_amount or 0)} XAF)
Citoyen: {sr['full_name']} (inscrit: {sr['user_created_at']})
Rejets précédents du citoyen: {rejection_count}
Formulaire (données clés): {str(sr['form_data'])[:500] if sr['form_data'] else 'Vide'}
"""

    analysis = await _llm_analyze(data_context, """
Eres un analista de riesgos fiscales. Evalúa el nivel de riesgo de esta solicitud.
Proporciona:
1. SCORE DE RIESGO (0-100) con justificación
2. FACTORES DE RIESGO identificados (lista)
3. SEÑALES POSITIVAS (si las hay)
4. RECOMENDACIÓN para el agente
Sé preciso y factual. Formato conciso.
""")

    return {
        "reference": sr["reference"],
        "ai_risk_analysis": analysis,
        "raw_signals": {
            "amount": float(sr["total_amount"]) if sr["total_amount"] else 0,
            "avg_amount": float(avg_amount) if avg_amount else 0,
            "citizen_rejections": rejection_count,
        },
    }


# ============================================================================
# 3. FIND SIMILAR CASES — Pattern matching with LLM synthesis
# ============================================================================

async def find_similar_cases(db, **kwargs) -> dict:
    """Find and ANALYZE past decisions for similar cases."""
    workflow_code = kwargs.get("workflow_code", "")
    limit = min(int(kwargs.get("limit", 5)), 10)
    if not workflow_code:
        return {"error": "Proporcione el workflow_code"}

    conditions = ["sr.workflow_code = $1", "sr.status::text IN ('COMPLETED', 'REJECTED')"]
    params = [workflow_code]
    idx = 1

    ef, ep = _entity_filter(kwargs, "sr", idx)
    if ef:
        conditions.append(ef.lstrip("AND "))
        params.extend(ep)
        idx += len(ep)
    sf, sp = _site_filter(kwargs, "sr", idx)
    if sf:
        conditions.append(sf.lstrip("AND "))
        params.extend(sp)
        idx += len(sp)

    params.append(limit)
    where = " AND ".join(conditions)

    rows = await db.fetch(f"""
        SELECT sr.reference, sr.status::text, sr.total_amount, sr.currency,
               sr.rejection_reason, sr.completed_at, sr.solicitud_type
        FROM service_requests sr
        WHERE {where}
        ORDER BY sr.updated_at DESC LIMIT ${idx + 1}
    """, *params)

    if not rows:
        return {"workflow_code": workflow_code, "similar_cases": [], "count": 0, "analysis": "No hay casos similares."}

    data_context = f"WORKFLOW: {workflow_code}\n\nCASOS SIMILARES:\n"
    for r in rows:
        data_context += f"- {r['reference']}: {r['status']} | {r['total_amount']} {r['currency'] or 'XAF'} | Tipo: {r['solicitud_type']} | Motivo rechazo: {r['rejection_reason'] or 'N/A'}\n"

    analysis = await _llm_analyze(data_context, """
Analiza estos casos similares y proporciona:
1. PATRÓN GENERAL: ¿Cuál es la tendencia de aprobación vs rechazo?
2. MOTIVOS COMUNES de rechazo (si aplica)
3. RANGO DE MONTOS típico
4. CONSEJO para el agente basado en los precedentes
Formato conciso, máximo 200 palabras.
""")

    return {
        "workflow_code": workflow_code,
        "similar_cases": [
            {"reference": r["reference"], "status": r["status"],
             "amount": f"{r['total_amount']} {r['currency']}" if r["total_amount"] else None,
             "rejection_reason": r["rejection_reason"]}
            for r in rows
        ],
        "count": len(rows),
        "ai_analysis": analysis,
    }


# ============================================================================
# 4. SUMMARIZE REQUEST — Executive dossier summary
# ============================================================================

async def summarize_request(db, **kwargs) -> dict:
    """LLM-generated executive summary of a dossier for quick agent review."""
    reference = kwargs.get("reference", "")
    if not reference:
        return {"error": "Proporcione la referencia"}

    sr = await db.fetchrow("""
        SELECT sr.id, sr.reference, sr.workflow_code, sr.solicitud_type,
               sr.status::text, sr.total_amount, sr.currency,
               sr.submitted_at, sr.payment_status, sr.cita_date,
               sr.notes, sr.rejection_reason, sr.escalated, sr.form_data,
               w.name_es as workflow_name, w.sla_hours,
               u.full_name as citizen_name
        FROM service_requests sr
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        LEFT JOIN users u ON u.id = sr.user_id
        WHERE sr.reference ILIKE '%' || $1 || '%'
        LIMIT 1
    """, reference)

    if not sr:
        return {"error": f"Dossier '{reference}' no encontrado"}

    # SLA remaining
    sla_info = "N/A"
    if sr["sla_hours"] and sr["submitted_at"]:
        from datetime import datetime, timezone
        elapsed = (datetime.now(timezone.utc) - sr["submitted_at"]).total_seconds() / 3600
        remaining = max(0, sr["sla_hours"] - elapsed)
        sla_info = f"{remaining:.1f}h restantes sur {sr['sla_hours']}h"

    # History
    events = await db.fetch("""
        SELECT action, new_status::text, comment, performed_at
        FROM service_request_history WHERE service_request_id = $1
        ORDER BY performed_at DESC LIMIT 5
    """, sr["id"])

    data_context = f"""
DOSSIER: {sr['reference']}
Citoyen: {sr['citizen_name']}
Workflow: {sr['workflow_name']} ({sr['solicitud_type']})
Statut: {sr['status']}
Montant: {sr['total_amount']} {sr['currency'] or 'XAF'}
Paiement: {sr['payment_status'] or 'N/A'}
RDV: {sr['cita_date'] or 'N/A'}
SLA: {sla_info}
Escaladé: {sr['escalated']}
Notes: {sr['notes'] or 'Aucune'}
Données formulaire (résumé): {str(sr['form_data'])[:300] if sr['form_data'] else 'Vide'}

HISTORIQUE ACTIONS:
{chr(10).join(f"- {e['performed_at']}: {e['action']} → {e['new_status']} | {e['comment'] or ''}" for e in events) if events else 'Aucun historique'}
"""

    analysis = await _llm_analyze(data_context, """
Genera un RESUMEN EJECUTIVO de este dossier para un agente que va a revisarlo.
Incluye:
1. RESUMEN (2-3 frases: qué es, quién lo pide, cuánto)
2. ESTADO ACTUAL y próximo paso esperado
3. ALERTAS (SLA en riesgo, documentos faltantes, escalación, etc.)
4. ACCIÓN RECOMENDADA para el agente
Formato ficha compacta con ▸ indicadores.
""")

    return {
        "reference": sr["reference"],
        "ai_summary": analysis,
    }


# ============================================================================
# 5. PREDICT SLA RISK — LLM-analyzed SLA predictions
# ============================================================================

async def predict_sla_risk(db, **kwargs) -> dict:
    """Predict SLA risks with LLM analysis of patterns."""
    conditions = ["sr.status::text NOT IN ('COMPLETED', 'CANCELLED', 'EXPIRED', 'REJECTED')"]
    params = []
    idx = 0

    ef, ep = _entity_filter(kwargs, "sr", idx)
    if ef:
        conditions.append(ef.lstrip("AND "))
        params.extend(ep)
        idx += len(ep)
    sf, sp = _site_filter(kwargs, "sr", idx)
    if sf:
        conditions.append(sf.lstrip("AND "))
        params.extend(sp)
        idx += len(sp)

    where = " AND ".join(conditions)

    rows = await db.fetch(f"""
        SELECT sr.reference, sr.workflow_code, sr.status::text, sr.entity_code,
               sr.submitted_at,
               w.sla_hours, w.name_es as workflow_name,
               EXTRACT(EPOCH FROM (NOW() - sr.submitted_at)) / 3600 as elapsed_hours
        FROM service_requests sr
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        WHERE {where} AND w.sla_hours IS NOT NULL AND sr.submitted_at IS NOT NULL
        ORDER BY (EXTRACT(EPOCH FROM (NOW() - sr.submitted_at)) / 3600) / NULLIF(w.sla_hours, 0) DESC
        LIMIT 15
    """, *params)

    at_risk = []
    for r in rows:
        if r["sla_hours"] and r["elapsed_hours"]:
            pct = (r["elapsed_hours"] / r["sla_hours"]) * 100
            if pct >= 60:
                at_risk.append({
                    "reference": r["reference"], "workflow": r["workflow_name"],
                    "status": r["status"], "entity": r["entity_code"],
                    "elapsed_h": round(r["elapsed_hours"], 1),
                    "sla_h": r["sla_hours"],
                    "remaining_h": round(max(0, r["sla_hours"] - r["elapsed_hours"]), 1),
                    "pct_used": round(pct, 0),
                })

    if not at_risk:
        return {"at_risk": [], "count": 0, "ai_analysis": "Aucun dossier à risque SLA."}

    data_context = "DOSSIERS À RISQUE SLA:\n"
    for a in at_risk:
        data_context += f"- {a['reference']}: {a['workflow']} | {a['status']} | {a['pct_used']}% SLA utilisé | {a['remaining_h']}h restantes\n"

    analysis = await _llm_analyze(data_context, """
Analiza los dossiers en riesgo de incumplimiento SLA.
Proporciona:
1. CLASIFICACIÓN por urgencia (CRÍTICO / ALTO / MEDIO)
2. CAUSA PROBABLE del retraso por dossier
3. ACCIONES INMEDIATAS recomendadas (priorizar, reasignar, escalar)
4. IMPACTO si no se actúa (consecuencias)
Formato tabla o lista priorizada.
""")

    return {"at_risk": at_risk, "count": len(at_risk), "ai_analysis": analysis}


# ============================================================================
# 6. SUGGEST REASSIGNMENT — LLM-reasoned agent matching
# ============================================================================

async def suggest_reassignment(db, **kwargs) -> dict:
    """LLM-reasoned reassignment based on workload, specialization, and performance."""
    reference = kwargs.get("reference", "")
    if not reference:
        return {"error": "Proporcione la referencia de la solicitud"}

    sr = await db.fetchrow("""
        SELECT sr.id, sr.reference, sr.workflow_code, sr.entity_code,
               sr.assigned_to, sr.total_amount, sr.status::text,
               u.full_name as current_agent_name, w.name_es as workflow_name
        FROM service_requests sr
        LEFT JOIN users u ON u.id = sr.assigned_to
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        WHERE sr.reference ILIKE '%' || $1 || '%'
        LIMIT 1
    """, reference)

    if not sr:
        return {"error": f"Solicitud '{reference}' no encontrada"}

    agents = await db.fetch("""
        SELECT u.full_name, aw.current_assignments, aw.capacity_percentage,
               aw.workload_status::text, aw.completion_rate_7d, aw.quality_score_avg,
               ap.specializations
        FROM agent_profiles ap
        JOIN users u ON u.id = ap.user_id
        LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
        WHERE ap.entity_id = (SELECT id FROM entities WHERE code = $1 LIMIT 1)
          AND ap.is_active = true
          AND COALESCE(aw.workload_status::text, 'available') NOT IN ('overloaded', 'unavailable')
        ORDER BY COALESCE(aw.capacity_percentage, 0) ASC
        LIMIT 5
    """, sr["entity_code"])

    data_context = f"""
SOLICITUD: {sr['reference']} — {sr['workflow_name']}
Agent actuel: {sr['current_agent_name'] or 'Non assigné'}
Montant: {sr['total_amount']} XAF

AGENTS DISPONIBLES:
"""
    for a in agents:
        data_context += (
            f"- {a['full_name']}: {a['current_assignments']} assignments, "
            f"capacité {round(float(a['capacity_percentage']), 0) if a['capacity_percentage'] else 0}%, "
            f"statut {a['workload_status']}, "
            f"taux complétion 7j: {round(float(a['completion_rate_7d']), 0) if a['completion_rate_7d'] else 'N/A'}%, "
            f"qualité: {round(float(a['quality_score_avg']), 1) if a['quality_score_avg'] else 'N/A'}, "
            f"spécialisations: {a['specializations'] or 'aucune'}\n"
        )

    analysis = await _llm_analyze(data_context, """
Recomienda el MEJOR agente para esta reasignación.
Considera:
1. CAPACIDAD actual (menor carga = mejor)
2. TASA DE COMPLETACIÓN (mayor = más confiable)
3. CALIDAD (score más alto = menos errores)
4. ESPECIALIZACIÓN (match con el workflow si possible)
Proporciona tu recomendación con justificación clara.
""")

    return {
        "request": sr["reference"],
        "current_agent": sr["current_agent_name"],
        "ai_recommendation": analysis,
        "available_agents": [
            {"name": a["full_name"], "workload": a["workload_status"],
             "capacity": round(float(a["capacity_percentage"]), 0) if a["capacity_percentage"] else 0}
            for a in agents
        ],
    }


# ============================================================================
# 7. GET SYSTEM HEALTH — LLM-analyzed system overview
# ============================================================================

async def get_system_health(db, **kwargs) -> dict:
    """System health with LLM anomaly detection."""
    status_counts = await db.fetch("""
        SELECT status::text, COUNT(*) as cnt FROM service_requests
        WHERE created_at >= NOW() - INTERVAL '7 days' GROUP BY status ORDER BY cnt DESC
    """)

    sla = await db.fetchrow("""
        SELECT COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (completed_at - submitted_at))/3600 <= w.sla_hours) as met,
               COUNT(*) as total
        FROM service_requests sr JOIN workflows w ON w.code = sr.workflow_code
        WHERE sr.completed_at >= NOW() - INTERVAL '7 days' AND w.sla_hours IS NOT NULL
    """)

    agents = await db.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE aw.workload_status::text = 'available') as available,
               COUNT(*) FILTER (WHERE aw.workload_status::text = 'overloaded') as overloaded
        FROM agent_profiles ap LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
        WHERE ap.is_active = true
    """)

    data_context = f"""
ÉTAT DU SYSTÈME (7 derniers jours):

Solicitudes par statut: {', '.join(f"{r['status']}: {r['cnt']}" for r in status_counts)}
SLA compliance: {round(sla['met'] / sla['total'] * 100, 1) if sla and sla['total'] else 'N/A'}% ({sla['met']}/{sla['total']})
Agents: {agents['total']} total, {agents['available']} disponibles, {agents['overloaded']} surchargés
"""

    analysis = await _llm_analyze(data_context, """
Analiza la salud del sistema y proporciona:
1. ESTADO GENERAL (🟢 Normal / 🟡 Atención / 🔴 Crítico)
2. ANOMALÍAS detectadas (si las hay)
3. MÉTRICAS CLAVE con tendencia
4. ACCIONES RECOMENDADAS para el administrador
Formato dashboard exécutif, conciso.
""")

    return {"ai_analysis": analysis, "raw": {"statuses": {r["status"]: r["cnt"] for r in status_counts},
            "sla_pct": round(sla['met'] / sla['total'] * 100, 1) if sla and sla['total'] else None,
            "agents": dict(agents) if agents else {}}}


# ============================================================================
# 8. OPTIMIZE WORKLOAD — LLM-reasoned rebalancing
# ============================================================================

async def optimize_workload(db, **kwargs) -> dict:
    """LLM-analyzed workload optimization suggestions."""
    rows = await db.fetch("""
        SELECT u.full_name, e.code as entity_code, e.name as entity_name,
               aw.current_assignments, aw.capacity_percentage,
               aw.workload_status::text, aw.completion_rate_7d
        FROM agent_profiles ap
        JOIN users u ON u.id = ap.user_id
        LEFT JOIN entities e ON e.id = ap.entity_id
        LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
        WHERE ap.is_active = true
        ORDER BY COALESCE(aw.capacity_percentage, 0) DESC
        LIMIT 20
    """)

    data_context = "CHARGE DE TRAVAIL DES AGENTS:\n"
    for r in rows:
        data_context += (
            f"- {r['full_name']} ({r['entity_name'] or 'N/A'}): "
            f"{r['current_assignments']} assignments, "
            f"{round(float(r['capacity_percentage']), 0) if r['capacity_percentage'] else 0}% capacité, "
            f"statut: {r['workload_status']}, "
            f"complétion 7j: {round(float(r['completion_rate_7d']), 0) if r['completion_rate_7d'] else 'N/A'}%\n"
        )

    analysis = await _llm_analyze(data_context, """
Analiza la distribución de carga de trabajo y proporciona:
1. DESEQUILIBRIOS detectados (agentes sobrecargados vs subutilizados)
2. SUGERENCIAS DE REASIGNACIÓN concretas (de quién a quién)
3. IMPACTO ESTIMADO de las reasignaciones
4. PRIORIDAD de cada acción (ALTA/MEDIA/BAJA)
Formato tabla con acciones concretas.
""")

    overloaded = [r for r in rows if r["workload_status"] == "overloaded"]
    return {"ai_analysis": analysis, "total_agents": len(rows), "overloaded": len(overloaded)}


# ============================================================================
# EXPORTS
# ============================================================================

DECISION_FUNCTION_MAP = {
    "ai_decision_support": ai_decision_support,
    "assess_request_risk": assess_request_risk,
    "find_similar_cases": find_similar_cases,
    "summarize_request": summarize_request,
    "predict_sla_risk": predict_sla_risk,
    "suggest_reassignment": suggest_reassignment,
    "get_system_health": get_system_health,
    "optimize_workload": optimize_workload,
}

# ============================================================================
# FUNCTION DECLARATIONS — for Gemini function-calling
# ============================================================================

# Source-of-truth: list of (name, FunctionDeclaration) tuples. Both
# DECISION_FUNC_DECLS (list, consumed by Gemini Tool config) and
# DECISION_FUNC_DECLS_BY_NAME (dict, used by tool_registry.py for O(1)
# name lookup) are derived from this single source so they can never
# desynchronize.
#
# Why a dict by name? `vertexai.generative_models.FunctionDeclaration`
# is a proto-plus wrapper whose `.name` attribute is NOT exposed as a
# Python property in some SDK versions. Introspecting it crashes with
# `'FunctionDeclaration' object has no attribute 'name'`. We keep the
# name we passed at construction time in a separate dict to bypass the
# protobuf access entirely.
_DECISION_DECLS_SOURCE: List[Any] = []  # list of (name, declaration) tuples
DECISION_FUNC_DECLS_BY_NAME: Dict[str, Any] = {}
DECISION_FUNC_DECLS: List[Any] = []

try:
    from vertexai.generative_models import FunctionDeclaration as _FD

    _DECISION_DECLS_SOURCE = [
        ("ai_decision_support", _FD(
            name="ai_decision_support",
            description="Análisis IA profundo de un dossier con recomendación de aprobación/rechazo. Usa cuando el agente pregunta '¿debo aprobar?', 'analiza este dossier', 'qué opinas de esta solicitud'.",
            parameters={"type": "object", "properties": {"reference": {"type": "string", "description": "Referencia del dossier (SR-xxxx)"}}, "required": ["reference"]},
        )),
        ("assess_request_risk", _FD(
            name="assess_request_risk",
            description="Evaluación de riesgo IA con score 0-100 y factores. Usa cuando se pregunta 'riesgo de esta solicitud', 'es sospechosa', 'hay anomalías'.",
            parameters={"type": "object", "properties": {"reference": {"type": "string", "description": "Referencia del dossier"}}, "required": ["reference"]},
        )),
        ("find_similar_cases", _FD(
            name="find_similar_cases",
            description="Buscar casos similares pasados con análisis de patrones. Usa cuando se pregunta 'casos similares', 'precedentes', 'qué se hizo antes'.",
            parameters={"type": "object", "properties": {"workflow_code": {"type": "string", "description": "Código del workflow"}, "status": {"type": "string", "description": "Filtrar por estado (COMPLETED/REJECTED)"}}, "required": ["workflow_code"]},
        )),
        ("summarize_request", _FD(
            name="summarize_request",
            description="Resumen ejecutivo IA de un dossier para revisión rápida. Usa cuando se pide 'resumen del dossier', 'resume esta solicitud', 'qué contiene'.",
            parameters={"type": "object", "properties": {"reference": {"type": "string", "description": "Referencia del dossier"}}, "required": ["reference"]},
        )),
        ("predict_sla_risk", _FD(
            name="predict_sla_risk",
            description="Predicción IA de qué dossiers van a incumplir el SLA. Usa cuando se pregunta 'SLA en riesgo', 'qué va a vencer', 'urgencias'.",
            parameters={"type": "object", "properties": {"entity_code": {"type": "string", "description": "Código entidad (opcional)"}}},
        )),
        ("suggest_reassignment", _FD(
            name="suggest_reassignment",
            description="Recomendación IA de reasignación con análisis de carga y especialización. Usa cuando se pide 'reasignar', 'a quién darle este dossier'.",
            parameters={"type": "object", "properties": {"reference": {"type": "string", "description": "Referencia de la solicitud"}}, "required": ["reference"]},
        )),
        ("get_system_health", _FD(
            name="get_system_health",
            description="Salud del sistema con detección de anomalías IA. Usa cuando se pregunta 'estado del sistema', 'cómo va todo', 'hay problemas'.",
            parameters={"type": "object", "properties": {}},
        )),
        ("optimize_workload", _FD(
            name="optimize_workload",
            description="Sugerencias IA de reequilibrio de carga entre agentes. Usa cuando se pide 'optimizar carga', 'redistribuir trabajo', 'equilibrar agentes'.",
            parameters={"type": "object", "properties": {}},
        )),
    ]
except ImportError:
    try:
        from google.generativeai.types import FunctionDeclaration as _FD2

        _DECISION_DECLS_SOURCE = [
            ("ai_decision_support", _FD2(name="ai_decision_support", description="Análisis IA de dossier con recomendación.", parameters={"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]})),
            ("assess_request_risk", _FD2(name="assess_request_risk", description="Evaluación de riesgo IA.", parameters={"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]})),
            ("find_similar_cases", _FD2(name="find_similar_cases", description="Buscar casos similares.", parameters={"type": "object", "properties": {"workflow_code": {"type": "string"}}, "required": ["workflow_code"]})),
            ("summarize_request", _FD2(name="summarize_request", description="Resumen ejecutivo IA.", parameters={"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]})),
            ("predict_sla_risk", _FD2(name="predict_sla_risk", description="Predicción SLA.", parameters={"type": "object", "properties": {}})),
            ("suggest_reassignment", _FD2(name="suggest_reassignment", description="Sugerencia reasignación.", parameters={"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]})),
            ("get_system_health", _FD2(name="get_system_health", description="Salud del sistema.", parameters={"type": "object", "properties": {}})),
            ("optimize_workload", _FD2(name="optimize_workload", description="Optimizar carga.", parameters={"type": "object", "properties": {}})),
        ]
    except ImportError:
        _DECISION_DECLS_SOURCE = []

# Derive both collections from the single source (cannot drift)
DECISION_FUNC_DECLS_BY_NAME = dict(_DECISION_DECLS_SOURCE)
DECISION_FUNC_DECLS = [decl for _, decl in _DECISION_DECLS_SOURCE]
