"""
Entity Agent Tools — Business tools for field agents (CNEDOGE, DGT, Extranjeria, etc.)

These agents process citizen service requests. Their LLM assistant needs
tools to look up requests, verify documents, check tariffs, and query
appointment availability — all scoped to their entity.

IMPORTANT: All functions accept (db, **kwargs) pattern.
  - _entity_code is injected by BaseAnalystService._build_entity_kwargs()
  - Gemini provides the function-specific parameters (query, reference, etc.)
  - Entity scoping is automatic — no need for Gemini to know entity_code

10 function-calling tools for Gemini:
1. search_requests       — Find requests by reference, NIF, or citizen name
2. get_request_detail    — Full detail of a specific request
3. get_pending_queue     — Agent's pending work queue with priorities
4. get_document_status   — Document validation status for a request
5. check_tariff          — Calculate tariff for a workflow
6. get_appointment_slots — Available appointment slots
7. get_citizen_history   — Previous requests from same citizen
8. get_workflow_steps    — Procedure steps for a workflow
9. get_entity_stats      — Entity-level daily/weekly statistics
10. get_sla_countdown    — SLA time remaining for pending items
"""

from typing import Any, Dict, List
from loguru import logger

try:
    from vertexai.generative_models import FunctionDeclaration
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False


# ============================================================================
# SQL FUNCTIONS — All use (db, **kwargs) with _entity_code from context
# ============================================================================

async def search_requests(db, **kwargs) -> dict:
    """Search service requests by reference, NIF, or citizen name."""
    entity_code = kwargs.get("_entity_code", "")
    query = kwargs.get("query", "")
    limit = kwargs.get("limit", 10)
    if not query:
        return {"error": "Provide a search query (reference, NIF, or name)"}
    rows = await db.fetch("""
        SELECT sr.reference, sr.workflow_code, sr.status, sr.created_at::text,
               u.first_name || ' ' || u.last_name AS citizen_name,
               u.document_number AS nif
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.entity_code = $1
          AND (sr.reference ILIKE '%' || $2 || '%'
               OR u.document_number ILIKE '%' || $2 || '%'
               OR u.first_name ILIKE '%' || $2 || '%'
               OR u.last_name ILIKE '%' || $2 || '%')
        ORDER BY sr.created_at DESC
        LIMIT $3
    """, entity_code, query, limit)
    return {"results": [dict(r) for r in rows], "total": len(rows)}


async def get_request_detail(db, **kwargs) -> dict:
    """Get full detail of a service request by reference."""
    ref = kwargs.get("request_reference", "")
    if not ref:
        return {"error": "Provide request_reference (e.g. SR-2026-00001)"}
    row = await db.fetchrow("""
        SELECT sr.id, sr.reference, sr.workflow_code, sr.solicitud_type, sr.status,
               sr.priority::text, sr.base_amount, sr.total_amount, sr.currency,
               sr.payment_status, sr.cita_date::text, sr.cita_time::text, sr.cita_location,
               sr.created_at::text, sr.submitted_at::text, sr.assigned_at::text,
               u.first_name || ' ' || u.last_name AS citizen_name,
               u.email AS citizen_email, u.document_number AS nif
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.reference = $1
    """, ref)
    if not row:
        return {"error": f"Request {ref} not found"}
    result = dict(row)
    docs = await db.fetch("""
        SELECT document_code, document_name, is_valid, extraction_status
        FROM service_request_documents
        WHERE service_request_id = $1
        ORDER BY created_at
    """, row["id"])
    result["documents"] = [dict(d) for d in docs]
    return result


async def get_pending_queue(db, **kwargs) -> dict:
    """Get pending work queue items for the agent's entity."""
    entity_code = kwargs.get("_entity_code", "")
    limit = kwargs.get("limit", 20)
    rows = await db.fetch("""
        SELECT awq.priority_score, awq.sla_deadline::text, awq.sla_status, awq.status,
               sr.reference, sr.workflow_code, sr.created_at::text,
               u.first_name || ' ' || u.last_name AS citizen_name
        FROM agent_work_queue awq
        JOIN service_requests sr ON sr.id = awq.item_id
        JOIN users u ON u.id = sr.user_id
        WHERE awq.entity_code = $1
          AND awq.status IN ('pending', 'assigned')
        ORDER BY awq.priority_score DESC, awq.sla_deadline ASC
        LIMIT $2
    """, entity_code, limit)
    return {"queue": [dict(r) for r in rows], "total": len(rows)}


async def get_document_status(db, **kwargs) -> dict:
    """Get document validation status for a service request."""
    ref = kwargs.get("request_reference", "")
    if not ref:
        return {"error": "Provide request_reference"}
    rows = await db.fetch("""
        SELECT srd.document_code, srd.document_name, srd.is_valid,
               srd.extraction_status, srd.extraction_confidence
        FROM service_request_documents srd
        JOIN service_requests sr ON sr.id = srd.service_request_id
        WHERE sr.reference = $1
        ORDER BY srd.created_at
    """, ref)
    return {
        "documents": [dict(r) for r in rows],
        "total": len(rows),
        "all_valid": all(r["is_valid"] for r in rows if r["is_valid"] is not None),
    }


async def check_tariff(db, **kwargs) -> dict:
    """Get tariff breakdown for a workflow."""
    workflow_code = kwargs.get("workflow_code", "")
    if not workflow_code:
        return {"error": "Provide workflow_code (e.g. pasaporte_nuevo)"}
    row = await db.fetchrow("""
        SELECT base_amount, currency, tariff_code, calculation_method
        FROM workflow_tariffs
        WHERE workflow_code = $1
        ORDER BY created_at DESC LIMIT 1
    """, workflow_code)
    if not row:
        return {"error": f"No tariff found for {workflow_code}"}
    supplements = await db.fetch("""
        SELECT wsc.supplement_code, ts.name_es, ts.amount, ts.currency
        FROM workflow_supplement_config wsc
        JOIN tariff_supplements ts ON ts.code = wsc.supplement_code
        WHERE wsc.workflow_code = $1 AND ts.is_active = true
    """, workflow_code)
    result = dict(row)
    result["supplements"] = [dict(s) for s in supplements]
    return result


async def get_appointment_slots(db, **kwargs) -> dict:
    """Get available appointment slots for the next N days."""
    entity_code = kwargs.get("_entity_code", "")
    rows = await db.fetch("""
        SELECT asc2.day_of_week, asc2.start_time::text, asc2.max_appointments_per_slot,
               el.location_name, c.name AS city
        FROM appointment_slot_configs asc2
        JOIN entity_locations el ON el.id = asc2.entity_location_id
        JOIN entities e ON e.id = el.entity_id
        LEFT JOIN cities c ON c.id = el.city_id
        WHERE e.code = $1 AND asc2.is_active = true
        ORDER BY asc2.day_of_week, asc2.start_time
    """, entity_code)
    return {"slots": [dict(r) for r in rows], "total": len(rows)}


async def get_citizen_history(db, **kwargs) -> dict:
    """Get previous service requests from a citizen by NIF."""
    nif = kwargs.get("nif", "")
    if not nif:
        return {"error": "Provide citizen NIF"}
    rows = await db.fetch("""
        SELECT sr.reference, sr.workflow_code, sr.status, sr.created_at::text, sr.total_amount
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE u.document_number = $1
        ORDER BY sr.created_at DESC
        LIMIT 20
    """, nif)
    return {"requests": [dict(r) for r in rows], "total": len(rows)}


async def get_workflow_steps(db, **kwargs) -> dict:
    """Get procedure template steps for a workflow."""
    workflow_code = kwargs.get("workflow_code", "")
    if not workflow_code:
        return {"error": "Provide workflow_code"}
    rows = await db.fetch("""
        SELECT pts.step_number, pts.name_es, pts.description_es, pts.is_optional
        FROM procedure_templates pt
        JOIN procedure_template_steps pts ON pts.template_id = pt.id
        WHERE pt.template_code = $1
        ORDER BY pts.step_number
    """, workflow_code)
    return {"steps": [dict(r) for r in rows], "total": len(rows)}


async def get_entity_stats(db, **kwargs) -> dict:
    """Get entity-level statistics for the last N days."""
    entity_code = kwargs.get("_entity_code", "")
    days = kwargs.get("days", 7)
    row = await db.fetchrow("""
        SELECT
            COUNT(*) AS total_requests,
            COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
            COUNT(*) FILTER (WHERE status = 'SUBMITTED') AS pending,
            COUNT(*) FILTER (WHERE status = 'UNDER_REVIEW') AS in_review,
            COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
            COALESCE(SUM(total_amount) FILTER (WHERE status = 'COMPLETED'), 0) AS revenue
        FROM service_requests
        WHERE entity_code = $1
          AND created_at >= NOW() - ($2 || ' days')::INTERVAL
    """, entity_code, str(days))
    return dict(row) if row else {}


async def get_sla_countdown(db, **kwargs) -> dict:
    """Get SLA time remaining for pending queue items."""
    entity_code = kwargs.get("_entity_code", "")
    rows = await db.fetch("""
        SELECT sr.reference, awq.sla_deadline::text, awq.sla_status,
               EXTRACT(EPOCH FROM (awq.sla_deadline - NOW())) / 3600 AS hours_remaining
        FROM agent_work_queue awq
        JOIN service_requests sr ON sr.id = awq.item_id
        WHERE awq.entity_code = $1
          AND awq.status IN ('pending', 'assigned')
          AND awq.sla_deadline IS NOT NULL
        ORDER BY awq.sla_deadline ASC
        LIMIT 10
    """, entity_code)
    critical = sum(1 for r in rows if r["hours_remaining"] is not None and float(r["hours_remaining"]) < 4)
    return {"items": [dict(r) for r in rows], "critical": critical}


# ============================================================================
# FUNCTION MAP (name -> callable)
# ============================================================================

ENTITY_AGENT_FUNCTION_MAP: Dict[str, Any] = {
    "search_requests": search_requests,
    "get_request_detail": get_request_detail,
    "get_pending_queue": get_pending_queue,
    "get_document_status": get_document_status,
    "check_tariff": check_tariff,
    "get_appointment_slots": get_appointment_slots,
    "get_citizen_history": get_citizen_history,
    "get_workflow_steps": get_workflow_steps,
    "get_entity_stats": get_entity_stats,
    "get_sla_countdown": get_sla_countdown,
}


# ============================================================================
# FUNCTION DECLARATIONS (for Gemini function calling)
# Note: entity_code NOT declared — injected automatically from agent context
# ============================================================================

ENTITY_AGENT_FUNC_DECLS: list = []
if VERTEX_AVAILABLE:
    ENTITY_AGENT_FUNC_DECLS = [
        FunctionDeclaration(
            name="search_requests",
            description="Buscar solicitudes por referencia, NIF o nombre del ciudadano",
            parameters={"type": "object", "properties": {
                "query": {"type": "string", "description": "Texto de busqueda (referencia, NIF, nombre)"},
            }, "required": ["query"]},
        ),
        FunctionDeclaration(
            name="get_request_detail",
            description="Obtener detalle completo de una solicitud por referencia (SR-XXXX-XXXXX)",
            parameters={"type": "object", "properties": {
                "request_reference": {"type": "string", "description": "Referencia de la solicitud (ej: SR-2026-00001)"},
            }, "required": ["request_reference"]},
        ),
        FunctionDeclaration(
            name="get_pending_queue",
            description="Ver cola de trabajo pendiente con prioridades y plazos SLA",
            parameters={"type": "object", "properties": {
                "limit": {"type": "integer", "description": "Numero maximo de resultados (default 20)"},
            }},
        ),
        FunctionDeclaration(
            name="get_document_status",
            description="Ver estado de validacion de documentos de una solicitud",
            parameters={"type": "object", "properties": {
                "request_reference": {"type": "string", "description": "Referencia de la solicitud"},
            }, "required": ["request_reference"]},
        ),
        FunctionDeclaration(
            name="check_tariff",
            description="Consultar tarifa y suplementos para un tipo de tramite",
            parameters={"type": "object", "properties": {
                "workflow_code": {"type": "string", "description": "Codigo del workflow (ej: pasaporte_nuevo, residencia)"},
            }, "required": ["workflow_code"]},
        ),
        FunctionDeclaration(
            name="get_appointment_slots",
            description="Ver horarios de citas disponibles para la entidad",
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="get_citizen_history",
            description="Ver historial de solicitudes anteriores de un ciudadano por NIF",
            parameters={"type": "object", "properties": {
                "nif": {"type": "string", "description": "Numero de identificacion fiscal del ciudadano"},
            }, "required": ["nif"]},
        ),
        FunctionDeclaration(
            name="get_workflow_steps",
            description="Ver pasos del procedimiento para un tipo de tramite",
            parameters={"type": "object", "properties": {
                "workflow_code": {"type": "string", "description": "Codigo del workflow"},
            }, "required": ["workflow_code"]},
        ),
        FunctionDeclaration(
            name="get_entity_stats",
            description="Estadisticas de la entidad (solicitudes completadas, pendientes, ingresos)",
            parameters={"type": "object", "properties": {
                "days": {"type": "integer", "description": "Periodo en dias (default 7)"},
            }},
        ),
        FunctionDeclaration(
            name="get_sla_countdown",
            description="Ver tiempo restante de SLA para items pendientes (urgencias)",
            parameters={"type": "object", "properties": {}},
        ),
    ]


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

ENTITY_AGENT_PROMPT_TEMPLATE = """Eres el asistente IA de un agente de la plataforma Facil
(plataforma digital de servicios publicos de Guinea Ecuatorial).

Tu rol: ayudar al agente a gestionar sus solicitudes ciudadanas de forma eficiente.
Tienes acceso a 10 herramientas para consultar datos REALES del sistema.

REGLAS:
- Responde SIEMPRE en espanol
- Cita datos EXACTOS retornados por las funciones (NUNCA inventes)
- Si no hay datos, dilo claramente
- Propon acciones concretas (aprobar, rechazar, solicitar documentos)
- Alerta sobre SLA en riesgo (< 4 horas restantes = URGENTE)
- Se conciso (max 300 palabras)

RAZONAMIENTO ANTES DE RESPONDER (Chain-of-Thought):
Antes de llamar funciones, RAZONA internamente:
1. ¿Qué datos necesita el agente para tomar una decision?
2. ¿Necesito cruzar datos (dossier + documentos + historial ciudadano)?
3. ¿Hay urgencia SLA? Si SLA < 4 horas → priorizar la alerta
4. ¿Como presentar la informacion para que el agente actue rapido?

FORMATOS DE PRESENTACION:
- Dossier unico → ficha resumen con ▸ indicadores
- Cola de trabajo → tabla con referencia, tipo, SLA restante
- Documentos → checklist con ✓/✗ por documento
- Alerta SLA → > **URGENTE:** SLA en riesgo para X dossiers
- Formato mixto → combinar (el mas efectivo)

ESTRATEGIA DE FUNCIONES:
| Pregunta del agente | Funcion(es) |
|---|---|
| Buscar un dossier/expediente | search_requests |
| Detalle de una solicitud | get_request_detail |
| Mi cola de trabajo | get_pending_queue |
| Estado de documentos | get_document_status |
| Cuanto cuesta un tramite | check_tariff |
| Citas disponibles | get_appointment_slots |
| Historial de un ciudadano | get_citizen_history |
| Pasos de un procedimiento | get_workflow_steps |
| Estadisticas de mi entidad | get_entity_stats |
| Urgencias SLA | get_sla_countdown |

Entidad del agente: {entity_code}
Fecha actual: {current_date}
"""
