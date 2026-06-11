"""
Supervisor Extended Tools — Composable tools for entity-specific supervision.

These tools extend the base supervisor tools (supervisor_tools.py) with
domain-specific functions for inspections, licenses, and appointments.

Loaded conditionally based on entity workflow_codes:
  - Inspection tools → entities with INSPECCION/MATRICULACION workflows
  - License tools → entities with OMS/commercial license workflows
  - Appointment tools → entities with appointment-based workflows

All functions follow the (db, **kwargs) pattern with _entity_code injection.
"""

from typing import Any, Dict

from loguru import logger

try:
    from vertexai.generative_models import FunctionDeclaration
    _VERTEX = True
except ImportError:
    _VERTEX = False


# ============================================================================
# INSPECTION TOOLS (OMS, ITVE)
# ============================================================================

async def get_inspection_stats(db, **kwargs) -> dict:
    """Stats inspections par periode (total, en cours, completees, scelles en attente)."""
    entity_code = kwargs.get("_entity_code", "")
    days = kwargs.get("days", 30)
    row = await db.fetchrow("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE fi.status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE fi.status = 'in_progress') AS in_progress,
            COUNT(*) FILTER (WHERE fi.seal_applied = true) AS sealed,
            COUNT(*) FILTER (WHERE fi.seal_applied = true AND fi.seal_approved_by IS NULL) AS pending_seal_approval,
            COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued = true) AS mise_en_demeure,
            COUNT(*) FILTER (WHERE fi.payment_collected = true) AS with_payment,
            COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected = true), 0) AS total_collected
        FROM field_inspections fi
        JOIN entities e ON e.id = fi.entity_id
        WHERE e.code = $1
          AND fi.created_at >= NOW() - ($2 || ' days')::INTERVAL
    """, entity_code, str(days))
    return dict(row) if row else {}


async def get_pending_seals(db, **kwargs) -> dict:
    """Scelles en attente d'approbation superviseur."""
    entity_code = kwargs.get("_entity_code", "")
    rows = await db.fetch("""
        SELECT fi.id::text, fi.inspection_date::text, fi.seal_reason,
               fi.seal_proposed_at::text, fi.seal_notes,
               c.name AS company_name, u.first_name || ' ' || u.last_name AS agent_name
        FROM field_inspections fi
        JOIN entities e ON e.id = fi.entity_id
        LEFT JOIN companies c ON c.id = fi.company_id
        LEFT JOIN users u ON u.id = fi.agent_id
        WHERE e.code = $1
          AND fi.seal_applied = true
          AND fi.seal_approved_by IS NULL
        ORDER BY fi.seal_proposed_at ASC
        LIMIT 20
    """, entity_code)
    return {"pending_seals": [dict(r) for r in rows], "total": len(rows)}


async def get_inspections_by_company(db, **kwargs) -> dict:
    """Inspections d'une entreprise par nom ou NIF."""
    query = kwargs.get("query", "")
    if not query:
        return {"error": "Provide company name or NIF"}
    rows = await db.fetch("""
        SELECT fi.id::text, fi.inspection_date::text, fi.status, fi.result,
               fi.activity_conforme, fi.unpaid_obligations_count,
               fi.unpaid_obligations_amount, fi.seal_applied,
               c.name AS company_name
        FROM field_inspections fi
        JOIN companies c ON c.id = fi.company_id
        WHERE (c.name ILIKE '%' || $1 || '%'
               OR c.nif ILIKE '%' || $1 || '%')
        ORDER BY fi.created_at DESC
        LIMIT 15
    """, query)
    return {"inspections": [dict(r) for r in rows], "total": len(rows)}


async def get_compliance_summary(db, **kwargs) -> dict:
    """Resume conformite par zone."""
    entity_code = kwargs.get("_entity_code", "")
    rows = await db.fetch("""
        SELECT cz.zone_code, cz.name AS zone_name,
               COUNT(DISTINCT cl.id) AS total_licenses,
               COUNT(DISTINCT cl.id) FILTER (WHERE cl.compliance_score >= 80) AS compliant,
               COUNT(DISTINCT cl.id) FILTER (WHERE cl.compliance_score < 50) AS critical,
               ROUND(AVG(cl.compliance_score)::numeric, 1) AS avg_score
        FROM commercial_licenses cl
        JOIN commerce_zones cz ON cz.id = cl.zone_id
        WHERE cl.status IN ('active', 'overdue')
        GROUP BY cz.zone_code, cz.name
        ORDER BY avg_score ASC
    """)
    return {"zones": [dict(r) for r in rows], "total": len(rows)}


async def get_overdue_obligations(db, **kwargs) -> dict:
    """Obligations en retard par priorite."""
    entity_code = kwargs.get("_entity_code", "")
    rows = await db.fetch("""
        SELECT lo.id::text, lo.fee_type, lo.amount, lo.penalty_amount,
               lo.due_date::text, lo.status,
               c.name AS company_name, c.nif
        FROM license_obligations lo
        JOIN commercial_licenses cl ON cl.id = lo.license_id
        JOIN companies c ON c.id = cl.company_id
        WHERE lo.status = 'overdue'
          AND lo.due_date < NOW()
        ORDER BY lo.due_date ASC
        LIMIT 20
    """)
    return {"overdue": [dict(r) for r in rows], "total": len(rows)}


# ============================================================================
# LICENSE TOOLS (OMS)
# ============================================================================

async def get_license_stats(db, **kwargs) -> dict:
    """Stats licences commerciales (actives, expirees, suspendues)."""
    rows = await db.fetch("""
        SELECT cl.status, COUNT(*) AS count,
               COALESCE(SUM(cl.total_amount), 0) AS total_amount
        FROM commercial_licenses cl
        GROUP BY cl.status
        ORDER BY count DESC
    """)
    return {"by_status": [dict(r) for r in rows]}


async def get_expiring_licenses(db, **kwargs) -> dict:
    """Licences qui expirent dans N jours."""
    days = kwargs.get("days", 30)
    rows = await db.fetch("""
        SELECT cl.id::text, cl.fiscal_year, cl.deadline::text, cl.status,
               cl.total_amount, cl.compliance_score,
               c.name AS company_name, c.nif,
               cz.name AS zone_name
        FROM commercial_licenses cl
        JOIN companies c ON c.id = cl.company_id
        LEFT JOIN commerce_zones cz ON cz.id = cl.zone_id
        WHERE cl.deadline BETWEEN NOW() AND NOW() + ($1 || ' days')::INTERVAL
          AND cl.status = 'active'
        ORDER BY cl.deadline ASC
        LIMIT 20
    """, str(days))
    return {"expiring": [dict(r) for r in rows], "total": len(rows)}


async def get_license_by_company(db, **kwargs) -> dict:
    """Detail licence + obligations d'une entreprise."""
    query = kwargs.get("query", "")
    if not query:
        return {"error": "Provide company name or NIF"}
    row = await db.fetchrow("""
        SELECT cl.id, cl.fiscal_year, cl.status, cl.total_amount,
               cl.amount_paid, cl.penalty_amount,
               cl.obligations_total, cl.obligations_paid, cl.obligations_overdue,
               cl.compliance_score, cl.deadline::text,
               c.name AS company_name, c.nif
        FROM commercial_licenses cl
        JOIN companies c ON c.id = cl.company_id
        WHERE (c.name ILIKE '%' || $1 || '%' OR c.nif ILIKE '%' || $1 || '%')
        ORDER BY cl.created_at DESC
        LIMIT 1
    """, query)
    if not row:
        return {"error": f"No license found for '{query}'"}
    result = dict(row)
    # Get obligations
    obligations = await db.fetch("""
        SELECT lo.fee_type, lo.amount, lo.penalty_amount, lo.due_date::text, lo.status
        FROM license_obligations lo
        WHERE lo.license_id = $1
        ORDER BY lo.due_date
    """, row["id"])
    result["obligations"] = [dict(o) for o in obligations]
    return result


async def get_zone_coverage(db, **kwargs) -> dict:
    """Couverture par zone commerciale."""
    rows = await db.fetch("""
        SELECT cz.zone_code, cz.name AS zone_name, cz.tier,
               COUNT(cl.id) AS license_count,
               COUNT(cl.id) FILTER (WHERE cl.status = 'active') AS active,
               COALESCE(SUM(cl.total_amount) FILTER (WHERE cl.status = 'active'), 0) AS revenue
        FROM commerce_zones cz
        LEFT JOIN commercial_licenses cl ON cl.zone_id = cz.id
        GROUP BY cz.id, cz.zone_code, cz.name, cz.tier
        ORDER BY license_count DESC
    """)
    return {"zones": [dict(r) for r in rows], "total": len(rows)}


# ============================================================================
# APPOINTMENT TOOLS (CNEDOGE, DGT)
# ============================================================================

async def get_appointment_stats(db, **kwargs) -> dict:
    """Stats rendez-vous (confirmes, no-show, taux)."""
    entity_code = kwargs.get("_entity_code", "")
    days = kwargs.get("days", 30)
    row = await db.fetchrow("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE ar.status = 'confirmed') AS confirmed,
            COUNT(*) FILTER (WHERE ar.status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE ar.status = 'cancelled') AS cancelled,
            COUNT(*) FILTER (WHERE sr.no_show_at IS NOT NULL) AS no_show
        FROM appointment_reservations ar
        JOIN service_requests sr ON sr.id = ar.service_request_id
        WHERE sr.entity_code = $1
          AND ar.created_at >= NOW() - ($2 || ' days')::INTERVAL
    """, entity_code, str(days))
    result = dict(row) if row else {}
    total = result.get("total", 0)
    if total > 0:
        result["completion_rate"] = round(result.get("completed", 0) / total * 100, 1)
        result["no_show_rate"] = round(result.get("no_show", 0) / total * 100, 1)
    return result


async def get_slot_utilization(db, **kwargs) -> dict:
    """Taux de remplissage par creneau."""
    entity_code = kwargs.get("_entity_code", "")
    rows = await db.fetch("""
        SELECT asc2.day_of_week, asc2.start_time::text,
               asc2.max_appointments_per_slot AS capacity,
               COUNT(ar.id) AS booked,
               el.location_name
        FROM appointment_slot_configs asc2
        JOIN entity_locations el ON el.id = asc2.entity_location_id
        JOIN entities e ON e.id = el.entity_id
        LEFT JOIN appointment_reservations ar ON ar.entity_location_id = asc2.entity_location_id
            AND EXTRACT(DOW FROM ar.appointment_date) = asc2.day_of_week
            AND ar.appointment_time = asc2.start_time
            AND ar.status NOT IN ('cancelled', 'expired')
            AND ar.appointment_date >= NOW() - INTERVAL '30 days'
        WHERE e.code = $1 AND asc2.is_active = true
        GROUP BY asc2.day_of_week, asc2.start_time, asc2.max_appointments_per_slot, el.location_name
        ORDER BY asc2.day_of_week, asc2.start_time
    """, entity_code)
    return {"slots": [dict(r) for r in rows], "total": len(rows)}


async def get_no_show_patterns(db, **kwargs) -> dict:
    """Patterns de no-show par jour/heure."""
    entity_code = kwargs.get("_entity_code", "")
    rows = await db.fetch("""
        SELECT
            EXTRACT(DOW FROM sr.cita_date)::int AS day_of_week,
            sr.cita_time::text AS time_slot,
            COUNT(*) AS no_shows
        FROM service_requests sr
        WHERE sr.entity_code = $1
          AND sr.no_show_at IS NOT NULL
          AND sr.cita_date IS NOT NULL
        GROUP BY day_of_week, time_slot
        ORDER BY no_shows DESC
        LIMIT 10
    """, entity_code)
    return {"patterns": [dict(r) for r in rows], "total": len(rows)}


# ============================================================================
# FUNCTION MAPS
# ============================================================================

INSPECTION_FUNCTION_MAP: Dict[str, Any] = {
    "get_inspection_stats": get_inspection_stats,
    "get_pending_seals": get_pending_seals,
    "get_inspections_by_company": get_inspections_by_company,
    "get_compliance_summary": get_compliance_summary,
    "get_overdue_obligations": get_overdue_obligations,
}

LICENSE_FUNCTION_MAP: Dict[str, Any] = {
    "get_license_stats": get_license_stats,
    "get_expiring_licenses": get_expiring_licenses,
    "get_license_by_company": get_license_by_company,
    "get_zone_coverage": get_zone_coverage,
}

APPOINTMENT_FUNCTION_MAP: Dict[str, Any] = {
    "get_appointment_stats": get_appointment_stats,
    "get_slot_utilization": get_slot_utilization,
    "get_no_show_patterns": get_no_show_patterns,
}


# ============================================================================
# FUNCTION DECLARATIONS (Gemini)
# ============================================================================

INSPECTION_FUNC_DECLS: list = []
LICENSE_FUNC_DECLS: list = []
APPOINTMENT_FUNC_DECLS: list = []

if _VERTEX:
    INSPECTION_FUNC_DECLS = [
        FunctionDeclaration(name="get_inspection_stats", description="Estadisticas de inspecciones (total, completadas, scellados pendientes)", parameters={"type": "object", "properties": {"days": {"type": "integer", "description": "Periodo en dias (default 30)"}}}),
        FunctionDeclaration(name="get_pending_seals", description="Scellados pendientes de aprobacion del supervisor", parameters={"type": "object", "properties": {}}),
        FunctionDeclaration(name="get_inspections_by_company", description="Inspecciones de una empresa por nombre o NIF", parameters={"type": "object", "properties": {"query": {"type": "string", "description": "Nombre o NIF de la empresa"}}, "required": ["query"]}),
        FunctionDeclaration(name="get_compliance_summary", description="Resumen de conformidad por zona comercial", parameters={"type": "object", "properties": {}}),
        FunctionDeclaration(name="get_overdue_obligations", description="Obligaciones vencidas por prioridad", parameters={"type": "object", "properties": {}}),
    ]

    LICENSE_FUNC_DECLS = [
        FunctionDeclaration(name="get_license_stats", description="Estadisticas de licencias comerciales (activas, expiradas)", parameters={"type": "object", "properties": {}}),
        FunctionDeclaration(name="get_expiring_licenses", description="Licencias que expiran en los proximos N dias", parameters={"type": "object", "properties": {"days": {"type": "integer", "description": "Dias hacia adelante (default 30)"}}}),
        FunctionDeclaration(name="get_license_by_company", description="Detalle de licencia y obligaciones de una empresa", parameters={"type": "object", "properties": {"query": {"type": "string", "description": "Nombre o NIF de la empresa"}}, "required": ["query"]}),
        FunctionDeclaration(name="get_zone_coverage", description="Cobertura de licencias por zona comercial", parameters={"type": "object", "properties": {}}),
    ]

    APPOINTMENT_FUNC_DECLS = [
        FunctionDeclaration(name="get_appointment_stats", description="Estadisticas de citas (confirmadas, no-show, tasa)", parameters={"type": "object", "properties": {"days": {"type": "integer", "description": "Periodo en dias (default 30)"}}}),
        FunctionDeclaration(name="get_slot_utilization", description="Tasa de utilizacion por horario de cita", parameters={"type": "object", "properties": {}}),
        FunctionDeclaration(name="get_no_show_patterns", description="Patrones de no-show por dia y hora", parameters={"type": "object", "properties": {}}),
    ]


# ============================================================================
# PROMPT FRAGMENTS (appended to supervisor base prompt)
# ============================================================================

INSPECTION_PROMPT_FRAGMENT = """
HERRAMIENTAS DE INSPECCION (disponibles para tu entidad):
| Funcion | Descripcion |
|---|---|
| get_inspection_stats | Estadisticas inspecciones (total, completadas, scellados) |
| get_pending_seals | Scellados pendientes de aprobacion |
| get_inspections_by_company | Inspecciones de una empresa |
| get_compliance_summary | Conformidad por zona |
| get_overdue_obligations | Obligaciones vencidas |
"""

LICENSE_PROMPT_FRAGMENT = """
HERRAMIENTAS DE LICENCIAS (disponibles para tu entidad):
| Funcion | Descripcion |
|---|---|
| get_license_stats | Estadisticas licencias (activas, expiradas) |
| get_expiring_licenses | Licencias proximas a expirar |
| get_license_by_company | Detalle licencia de una empresa |
| get_zone_coverage | Cobertura por zona comercial |
"""

APPOINTMENT_PROMPT_FRAGMENT = """
HERRAMIENTAS DE CITAS (disponibles para tu entidad):
| Funcion | Descripcion |
|---|---|
| get_appointment_stats | Estadisticas citas (confirmadas, no-show) |
| get_slot_utilization | Tasa de utilizacion por horario |
| get_no_show_patterns | Patrones de no-show |
"""
