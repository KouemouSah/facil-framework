"""
Treasury Analyst Service — Gemini function-calling for treasury financial Q&A.

The LLM NEVER generates SQL. It ROUTES to predefined safe functions and
FORMATS the response with financial analysis.

Language: Spanish by default (Equatorial Guinea treasury context).
Inherits shared 2-call Gemini flow from BaseAnalystService.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.core.ai_telemetry import traced_generate_sync
from app.modules.shared.services.base_analyst_service import (
    BaseAnalystService,
    VERTEX_AI_AVAILABLE,
    GEMINI_TIMEOUT_SECOND_CALL,
)

if VERTEX_AI_AVAILABLE:
    from vertexai.generative_models import (
        FunctionDeclaration,
        GenerationConfig,
    )


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT_TEMPLATE = """Eres el Analista Financiero Senior del Tesoro Público de Guinea Ecuatorial
en la plataforma Facil, experto en fiscalidad CEMAC/BEAC y gestión de pagos gubernamentales.

CONTEXTO TEMPORAL: Hoy es {current_date} ({day_of_week}). Cuando digas "ayer", "esta semana",
"este mes" o "últimos 7 días", refiérete a fechas reales calculadas desde hoy.

Tu rol: analizar datos REALES de pagos, ingresos, agentes de tesorería, SLA y anomalías
para ayudar al supervisor del tesoro a tomar decisiones financieras informadas.

REGLAS ESTRICTAS:
- Responde SIEMPRE en español
- Cita cifras EXACTAS retornadas por las funciones (NUNCA inventes datos)
- Si los datos son insuficientes, dilo claramente
- Analiza tendencias de ingresos, anomalías de pagos, problemas SLA, rendimiento agentes
- Propón acciones concretas, priorizadas y con plazo cuando sea pertinente
- Sé factual y conciso (máximo 800 palabras)
- Los montos están en XAF (Franco CFA de África Central)
- NO hagas suposiciones sobre datos que no tienes

RAZONAMIENTO ANTES DE RESPONDER (Chain-of-Thought):
Antes de llamar funciones, RAZONA internamente:
1. ¿Qué datos necesito para responder completamente a esta pregunta?
2. ¿Qué funciones debo llamar y en qué orden?
3. ¿Necesito combinar datos de varias funciones para una visión completa?
4. ¿Cómo presentar los resultados de la forma más clara para un supervisor de tesorería?

FORMATOS DE PRESENTACIÓN — elige el más apropiado:
- Dato único → negrita inline: El ingreso total es **5.234.000 XAF**
- 3+ filas con columnas → tabla markdown (alinear números a la derecha)
- Alerta/advertencia → > **Atención:** SLA en riesgo para 3 entidades
- Resumen ejecutivo → ficha con ▸ indicadores clave (KPIs)
- Tendencia → tabla comparativa (periodo anterior vs actual, % variación)
- Formato mixto → combinar (el más efectivo para análisis financieros complejos)
Principio: cada KPI en su propia línea, totales en negrita, variaciones con ↑/↓.

ESTRATEGIA DE FUNCIONES — MUY IMPORTANTE:
- Para preguntas AMPLIAS ("resumen de ingresos", "estado financiero", "reporte completo"):
  DEBES llamar MÚLTIPLES funciones simultáneamente.
  Ejemplo: "resumen financiero" → get_revenue_summary + get_sla_status + get_anomaly_summary + get_payment_trends
  Ejemplo: "comparar entidades" → get_entity_comparison + get_revenue_by_service
  Ejemplo: "estado pagos pendientes" → get_sla_status + get_payment_aging + get_workflow_pipeline
  Ejemplo: "rendimiento agentes" → get_agent_performance + get_rejection_analysis
- Para preguntas ESPECÍFICAS, llama solo la función relevante
- SIEMPRE llama al menos una función. NUNCA respondas sin datos.

FORMATO DE RESPUESTA — REGLA OBLIGATORIA:
Para CUALQUIER dato numérico comparativo (agentes, entidades, servicios, períodos, anomalías),
USA SIEMPRE tablas markdown con alineación a la derecha para los números:

| Entidad | Transacciones | Monto (XAF) | % Total |
|---------|-------------:|------------:|--------:|
| TESORO  |            5 |     250,000 |   55.6% |
| CNEDOGE |            3 |     200,000 |   44.4% |

- Usa encabezados ## y ### para estructurar
- Usa **negrita** para KPIs principales
- Usa `código` para códigos de entidad, workflow o referencias técnicas
- Formatea montos con separador de miles: 1,250,000 XAF
- Al final, incluye "### Recomendaciones" con acciones concretas, priorizadas

DETECCIÓN DE ALERTAS — REGLA CONDICIONAL:
Al analizar los datos recibidos, verifica si existen estas situaciones ANTES de redactar tu respuesta:
1. Caída >10% en ingresos vs período anterior (datos de get_period_comparison) → ⚠️ ALERTA INGRESOS
2. SLA de algún agente por debajo del 85% (datos de get_agent_performance) → ⚠️ ALERTA SLA
3. Flujo de caja negativo: egresos > ingresos en los últimos 7 días (datos de get_cash_flow_daily) → ⚠️ ALERTA FLUJO
4. Anomalías abiertas con severidad 'critical' o 'high' (datos de get_anomaly_summary/details) → ⚠️ ALERTA ANOMALÍA
Si detectas CUALQUIERA de estas alertas, colócalas al INICIO de tu respuesta en un bloque:
> ⚠️ **ALERTAS DETECTADAS**
> - [descripción de cada alerta con cifras exactas]
Nota: solo alerta sobre datos que REALMENTE recibiste. No inventes alertas.

MARCO DE ANÁLISIS:
- Variance analysis: compara actual vs período anterior (usa get_period_comparison)
- Trend detection: identifica tendencias al alza/baja en get_payment_trends o get_cash_flow_daily
- Benchmarking: compara entidades entre sí con get_entity_comparison
- Risk assessment: evalúa false positive rates con get_anomaly_details

FUNCIONES DISPONIBLES (15):
- get_revenue_summary: ingresos totales, pendientes, rechazados, por método y entidad
- get_revenue_by_service: ingresos por tipo de servicio (workflow_code)
- get_agent_performance: validaciones/rechazos/tiempo/SLA por agente
- get_sla_status: pagos pendientes con clasificación breached/critical/warning/ok
- get_anomaly_summary: anomalías por tipo/severidad/estado (vista general)
- get_payment_trends: tendencia diaria de volúmenes y montantes
- get_reconciliation_status: rapprochement bancaire (reconciliadas vs no)
- get_top_payers: principales contribuyentes por montante
- get_entity_comparison: comparación de revenue/volumen entre entidades (NUEVO)
- get_payment_aging: distribución de antigüedad de pagos pendientes (NUEVO)
- get_workflow_pipeline: funnel de estados de pagos (NUEVO)
- get_period_comparison: comparación período actual vs anterior con delta % (NUEVO)
- get_cash_flow_daily: flujo diario ingresos/egresos con acumulado (NUEVO)
- get_rejection_analysis: patrones de rechazo por agente y motivo (NUEVO)
- get_anomaly_details: drill-down anomalías con tasa false positive (NUEVO)
- get_revenue_forecast: proyección de ingresos basada en tendencia histórica (NUEVO)
- get_workload_forecast: proyección de carga de trabajo futura (NUEVO)

RAZONAMIENTO EN CADENA (Chain-of-Tools):
Si al analizar los resultados de la primera ronda detectas que necesitas más contexto,
PUEDES solicitar funciones adicionales. Ejemplos:
- get_anomaly_summary muestra pico → solicita get_anomaly_details para identificar responsable
- get_revenue_summary muestra caída → solicita get_entity_comparison para saber cuál entidad baja
- get_agent_performance muestra SLA bajo → solicita get_rejection_analysis para entender por qué
Solo solicita funciones adicionales si realmente aportan valor. No encadenes por encadenar.

REGLA DE PRECISIÓN NUMÉRICA:
NUNCA redondees ni modifiques montos en el texto. Cita SIEMPRE el valor EXACTO retornado
por la función. Si la función retorna 445,230 XAF, escribe 445,230 XAF (NO "unos 450,000 XAF").

REGLA DE PREVISIONES:
Cuando uses get_revenue_forecast o get_workload_forecast, verifica el campo "confidence":
- confidence="high" (>90 data points): análisis fiable, puedes hacer recomendaciones
- confidence="medium" (30-90 data points): tendencia indicativa, menciona la limitación
- confidence="low" (<30 data points): OBLIGATORIO añadir: "⚠️ Previsión basada en datos
  insuficientes (N puntos). Esta proyección es INDICATIVA y no debe usarse para decisiones
  financieras. Se requieren al menos 12 meses de datos para previsiones fiables."

CONTEXTO DE DRILL-DOWN:
Si recibes contexto de una pregunta anterior, úsalo para resolver referencias como
"la segunda entidad", "ese agente", "el mes anterior del tabla". Nunca ignores el contexto."""


# ============================================================================
# FUNCTION DECLARATIONS
# ============================================================================

_FUNC_DECLS: list = []
if VERTEX_AI_AVAILABLE:
    _FUNC_DECLS = [
        FunctionDeclaration(
            name="get_revenue_summary",
            description="Resumen de ingresos: montante total, transacciones, promedio, desglose por estado y método de pago.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_revenue_by_service",
            description="Ingresos desglosados por tipo de servicio (workflow_code). Top servicios por montante.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_agent_performance",
            description="Rendimiento de agentes de tesorería: validaciones, rechazos, tiempo promedio, tasa SLA.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_sla_status",
            description="Estado actual SLA: pagos pendientes con clasificación breached/critical/warning/ok.",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_anomaly_summary",
            description="Resumen de anomalías detectadas: por tipo, severidad, estado (open/resolved).",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_payment_trends",
            description="Tendencia diaria de pagos: volúmenes y montantes por día. Útil para detectar patrones.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_reconciliation_status",
            description="Estado del rapprochement bancaire: transacciones reconciliadas vs no reconciliadas.",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_top_payers",
            description="Principales contribuyentes (empresas o usuarios) por montante pagado.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                    "limit": {"type": "integer", "description": "Número de resultados (default 10)"},
                },
            },
        ),
        # ---- 7 NEW TOOLS ----
        FunctionDeclaration(
            name="get_entity_comparison",
            description="Comparación de ingresos y volúmenes entre entidades. Revenue, transacciones, promedio, min, max por entidad.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_payment_aging",
            description="Distribución de antigüedad de pagos pendientes: <4h, 4-12h, 12-24h, 24-48h, >48h. Promedio horas.",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_workflow_pipeline",
            description="Funnel de estados de pagos: cantidad y monto por workflow_status (últimos 90 días).",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_period_comparison",
            description="Comparación período actual vs anterior: transacciones, montos, deltas porcentuales.",
            parameters={
                "type": "object",
                "properties": {
                    "current_days": {"type": "integer", "description": "Tamaño del período en días (default 30). Compara con el período anterior equivalente."},
                },
            },
        ),
        FunctionDeclaration(
            name="get_cash_flow_daily",
            description="Flujo de caja diario: ingresos (completed) vs egresos (cancelled/expired), con acumulado.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_rejection_analysis",
            description="Análisis de rechazos: patrones por agente, motivos de rechazo, reenvíos. Detecta agentes con tasa de rechazo alta.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Período en días (default 30)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_anomaly_details",
            description="Drill-down detallado de anomalías: por tipo y severidad, con tasa de false positive, anomalías abiertas, acciones recientes.",
            parameters={
                "type": "object",
                "properties": {
                    "anomaly_type": {"type": "string", "description": "Filtrar por tipo (ej: amount_mismatch, duplicate_suspected). Omitir para todos."},
                    "severity": {"type": "string", "description": "Filtrar por severidad (low, medium, high, critical). Omitir para todas."},
                },
            },
        ),
        # ---- 2 FORECAST TOOLS ----
        FunctionDeclaration(
            name="get_revenue_forecast",
            description="Proyección de ingresos futuros basada en tendencia histórica. Incluye media móvil 7d, tendencia lineal, y nivel de confianza según cantidad de datos.",
            parameters={
                "type": "object",
                "properties": {
                    "days_history": {"type": "integer", "description": "Días de historial para el cálculo (default 90). Más datos = mayor confianza."},
                },
            },
        ),
        FunctionDeclaration(
            name="get_workload_forecast",
            description="Proyección de carga de trabajo futura: volumen de pagos pendientes estimado. Incluye tendencia y nivel de confianza.",
            parameters={
                "type": "object",
                "properties": {
                    "days_history": {"type": "integer", "description": "Días de historial para el cálculo (default 90)."},
                },
            },
        ),
    ]


# ============================================================================
# ENTITY SCOPING HELPER
# ============================================================================

def _needs_site_filter(kwargs: dict) -> bool:
    """Check if site filtering is needed (satellite site only)."""
    return not kwargs.get("_is_main_office", True) and bool(kwargs.get("_entity_location_id"))


def _site_scope_validated(kwargs: dict, sp_alias: str, param_offset: int):
    """Site-scope COMPLETED payments via validated_by_agent_id column.

    TESORO-specific: service_payments.assigned_agent_id = ENTITY agent (CNEDOGE),
    NOT the TESORO agent who validated. The TESORO agent is in validated_by_agent_id.
    For satellite sites, filter by payments validated BY agents at that site.

    Uses direct column (fast) instead of PVA subselect, thanks to migration 172
    which fixed validated_by_agent_id to store users.id (not agent_profiles.id).

    Args:
        kwargs: Entity context (**kwargs from function call)
        sp_alias: SQL alias for service_payments (e.g., "sp" or "service_payments")
        param_offset: Number of params already used ($1..$N)

    Returns:
        (sql_clause: str, params: list) — empty if no scoping needed
    """
    if not _needs_site_filter(kwargs):
        return "", []

    location_id = kwargs["_entity_location_id"]
    param_num = param_offset + 1
    clause = (
        f"AND {sp_alias}.validated_by_agent_id IN ("
        f"SELECT ap_s.user_id FROM agent_profiles ap_s "
        f"WHERE ap_s.entity_location_id = ${param_num})"
    )
    return clause, [location_id]


def _site_scope_direct(kwargs: dict, alias: str, param_offset: int, id_col: str = "agent_user_id"):
    """Site-scope via direct agent column (for PVA-based queries).

    Used when the table already has the TESORO agent's user_id directly
    (e.g., payment_validation_audit.agent_user_id).

    Args:
        kwargs: Entity context (**kwargs from function call)
        alias: SQL table alias (e.g., "pva")
        param_offset: Number of params already used ($1..$N)
        id_col: Column with agent UUID (default: agent_user_id)

    Returns:
        (sql_clause: str, params: list) — empty if no scoping needed
    """
    if not _needs_site_filter(kwargs):
        return "", []

    location_id = kwargs["_entity_location_id"]
    param_num = param_offset + 1
    clause = (
        f"AND {alias}.{id_col} IN ("
        f"SELECT ap_s.user_id FROM agent_profiles ap_s "
        f"WHERE ap_s.entity_location_id = ${param_num})"
    )
    return clause, [location_id]


def _site_scope_via_request(kwargs: dict, table_alias: str, param_offset: int,
                            fk_col: str = "service_request_id"):
    """Site-scope any table via its service_request's entity_location_id.

    Used for tables that link to service_requests but lack entity_location_id
    directly (service_payments, payment_anomalies, etc.).

    Args:
        kwargs: Entity context (**kwargs from function call)
        table_alias: SQL alias for the source table (e.g., "sp", "pa", "service_payments")
        param_offset: Number of params already used ($1..$N)
        fk_col: Column linking to service_requests.id (default: "service_request_id")

    Returns:
        (sql_clause: str, params: list) — empty if no scoping needed
    """
    if not _needs_site_filter(kwargs):
        return "", []

    location_id = kwargs["_entity_location_id"]
    param_num = param_offset + 1
    clause = (
        f"AND {table_alias}.{fk_col} IN ("
        f"SELECT sr_s.id FROM service_requests sr_s "
        f"WHERE sr_s.entity_location_id = ${param_num})"
    )
    return clause, [location_id]


# ============================================================================
# SAFE SQL FUNCTIONS (predefined queries — LLM never generates SQL)
# ============================================================================

async def _get_revenue_summary(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    # Bug 1 fix dynamic (2026-05-06): entity scope is now dynamic — taken from
    # kwargs['_entity_code'] (set by caller from tctx.entity_code). When None
    # (admin global scope), no entity clause is applied and the chatbot sees
    # all entities. Otherwise the supervisor sees only own-entity data.
    target_entity = kwargs.get("_entity_code")

    # Helper to build an entity clause + params relative to current $N offset.
    def _ent_clause(alias: str, current_offset: int):
        if not target_entity:
            return "", []
        return f"AND {alias}.entity_code = ${current_offset + 1}", [target_entity]

    # Completed revenue → PVA-based site scope + dynamic entity scope.
    # Order of params after $1 (days): site-scope first (offset=1 → $2),
    # then entity-scope (offset=1+len(sp_v) → $3 if site scope active, else $2).
    sc_v, sp_v = _site_scope_validated(kwargs, "service_payments", 1)
    e_clause, e_params = _ent_clause("service_payments", 1 + len(sp_v))
    row = await db.fetchrow(f"""
        SELECT
            COALESCE(SUM(total_amount) FILTER (WHERE workflow_status = 'completed'), 0) AS completed_amount,
            COUNT(*) FILTER (WHERE workflow_status = 'completed') AS completed_count,
            COALESCE(AVG(total_amount) FILTER (WHERE workflow_status = 'completed'), 0) AS avg_amount
        FROM service_payments
        WHERE created_at >= NOW() - make_interval(days => $1)
          {sc_v} {e_clause}
    """, days, *sp_v, *e_params)
    # Pending payments → no site scope (centralized queue) + dynamic entity scope
    pe_clause, pe_params = _ent_clause("service_payments", 1)
    pending_row = await db.fetchrow(f"""
        SELECT
            COALESCE(SUM(total_amount), 0) AS pending_amount,
            COUNT(*) AS pending_count
        FROM service_payments
        WHERE workflow_status IN ('pending_agent_review', 'agent_reviewing')
          AND requires_agent_validation = true
          AND created_at >= NOW() - make_interval(days => $1)
          {pe_clause}
    """, days, *pe_params)
    # Rejected count → no site scope + dynamic entity scope
    re_clause, re_params = _ent_clause("service_payments", 1)
    rejected_count = await db.fetchval(f"""
        SELECT COUNT(*) FROM service_payments
        WHERE workflow_status = 'rejected_by_agent'
          AND created_at >= NOW() - make_interval(days => $1)
          {re_clause}
    """, days, *re_params)
    sc2, sp2 = _site_scope_validated(kwargs, "service_payments", 1)
    me_clause, me_params = _ent_clause("service_payments", 1 + len(sp2))
    methods = await db.fetch(f"""
        SELECT payment_method::text AS method, COUNT(*) AS count,
               COALESCE(SUM(total_amount), 0) AS amount
        FROM service_payments
        WHERE workflow_status = 'completed' AND validated_at >= NOW() - make_interval(days => $1)
          {sc2} {me_clause}
        GROUP BY payment_method ORDER BY amount DESC
    """, days, *sp2, *me_params)
    sc3, sp3 = _site_scope_validated(kwargs, "sp", 1)
    be_clause, be_params = _ent_clause("sp", 1 + len(sp3))
    by_entity = await db.fetch(f"""
        SELECT sp.entity_code, e.name AS entity_name,
               COUNT(*) AS count, COALESCE(SUM(sp.total_amount), 0) AS amount
        FROM service_payments sp
        LEFT JOIN entities e ON e.code = sp.entity_code
        WHERE sp.workflow_status = 'completed' AND sp.validated_at >= NOW() - make_interval(days => $1)
          {sc3} {be_clause}
        GROUP BY sp.entity_code, e.name ORDER BY amount DESC
    """, days, *sp3, *be_params)
    return {
        "period_days": days,
        "completed": {"amount": float(row["completed_amount"]), "count": row["completed_count"], "avg": float(row["avg_amount"])},
        "pending": {"amount": float(pending_row["pending_amount"]), "count": pending_row["pending_count"]},
        "rejected_count": rejected_count or 0,
        "by_method": [{"method": m["method"], "count": m["count"], "amount": float(m["amount"])} for m in methods],
        "by_entity": [{"entity_code": r["entity_code"], "entity_name": r["entity_name"], "count": r["count"], "amount": float(r["amount"])} for r in by_entity],
    }


async def _get_revenue_by_service(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    # Bug 1 fix dynamic (2026-05-06): entity scope is now driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")

    def _ent_clause(alias: str, current_offset: int):
        if not target_entity:
            return "", []
        return f"AND {alias}.entity_code = ${current_offset + 1}", [target_entity]

    sc, sp_params = _site_scope_validated(kwargs, "sp", 1)
    e_clause, e_params = _ent_clause("sp", 1 + len(sp_params))
    rows = await db.fetch(f"""
        SELECT sr.workflow_code, COALESCE(fs.name_es, sr.workflow_code) AS service_name,
               COUNT(*) AS count, COALESCE(SUM(sp.total_amount), 0) AS amount
        FROM service_payments sp
        JOIN service_requests sr ON sr.id = sp.service_request_id
        LEFT JOIN fiscal_services fs ON fs.id = sr.fiscal_service_id
        WHERE sp.workflow_status = 'completed' AND sp.validated_at >= NOW() - make_interval(days => $1)
          {sc} {e_clause}
        GROUP BY sr.workflow_code, fs.name_es ORDER BY amount DESC LIMIT 10
    """, days, *sp_params, *e_params)
    sc2, sp2 = _site_scope_validated(kwargs, "sp", 1)
    e2_clause, e2_params = _ent_clause("sp", 1 + len(sp2))
    by_entity = await db.fetch(f"""
        SELECT sp.entity_code, e.name AS entity_name,
               COUNT(*) AS count, COALESCE(SUM(sp.total_amount), 0) AS amount
        FROM service_payments sp
        LEFT JOIN entities e ON e.code = sp.entity_code
        WHERE sp.workflow_status = 'completed' AND sp.validated_at >= NOW() - make_interval(days => $1)
          {sc2} {e2_clause}
        GROUP BY sp.entity_code, e.name ORDER BY amount DESC LIMIT 10
    """, days, *sp2, *e2_params)
    return {
        "period_days": days,
        "services": [{"code": r["workflow_code"], "name": r["service_name"], "count": r["count"], "amount": float(r["amount"])} for r in rows],
        "by_entity": [{"entity_code": r["entity_code"], "entity_name": r["entity_name"], "count": r["count"], "amount": float(r["amount"])} for r in by_entity],
    }


async def _get_agent_performance(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")

    def _ent_clause(alias: str, current_offset: int):
        if not target_entity:
            return "", []
        return f"AND {alias}.entity_code = ${current_offset + 1}", [target_entity]

    sc, sp_params = _site_scope_direct(kwargs, "pva", 1, id_col="agent_user_id")
    e_clause, e_params = _ent_clause("sp", 1 + len(sp_params))
    rows = await db.fetch(f"""
        SELECT u.full_name AS agent_name,
               COUNT(*) FILTER (WHERE pva.action = 'approve') AS validations,
               COUNT(*) FILTER (WHERE pva.action = 'reject') AS rejections,
               COALESCE(AVG(pva.action_duration_seconds) / 60.0, 0) AS avg_minutes,
               COUNT(*) FILTER (WHERE sp.sla_escalated = false OR sp.sla_escalated IS NULL)::float /
                   NULLIF(COUNT(*), 0) * 100 AS sla_rate
        FROM payment_validation_audit pva
        JOIN users u ON u.id = pva.agent_user_id
        JOIN service_payments sp ON sp.id = pva.payment_id
        WHERE pva.created_at >= NOW() - make_interval(days => $1) AND pva.agent_user_id IS NOT NULL
          {sc} {e_clause}
        GROUP BY u.full_name ORDER BY (COUNT(*) FILTER (WHERE pva.action = 'approve') + COUNT(*) FILTER (WHERE pva.action = 'reject')) DESC
    """, days, *sp_params, *e_params)
    return {
        "period_days": days,
        "agents": [{"name": r["agent_name"], "validations": r["validations"], "rejections": r["rejections"],
                     "avg_minutes": round(float(r["avg_minutes"]), 1), "sla_rate": round(float(r["sla_rate"]) if r["sla_rate"] else 100, 1)} for r in rows],
    }


async def _get_sla_status(db, **kwargs) -> Dict[str, Any]:
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")

    # Pending payments — site-scoped via service_request entity_location_id
    sc, sp = _site_scope_via_request(kwargs, "service_payments", 0)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${len(sp) + len(e_params)}"
    row = await db.fetchrow(f"""
        SELECT
            COUNT(*) AS total_pending,
            COUNT(*) FILTER (WHERE sla_target_date IS NOT NULL AND sla_target_date < NOW()) AS breached,
            COUNT(*) FILTER (WHERE sla_target_date IS NOT NULL AND sla_target_date BETWEEN NOW() AND NOW() + INTERVAL '2 hours') AS critical,
            COUNT(*) FILTER (WHERE sla_target_date IS NOT NULL AND sla_target_date BETWEEN NOW() + INTERVAL '2 hours' AND NOW() + INTERVAL '6 hours') AS warning,
            COUNT(*) FILTER (WHERE sla_target_date IS NULL OR sla_target_date > NOW() + INTERVAL '6 hours') AS on_time
        FROM service_payments
        WHERE workflow_status IN ('pending_agent_review', 'agent_reviewing')
          AND requires_agent_validation = true
          {sc}
          {e_clause}
    """, *sp, *e_params)
    total = row["total_pending"] or 0
    return {
        "total_pending": total,
        "breached": row["breached"],
        "critical": row["critical"],
        "warning": row["warning"],
        "on_time": row["on_time"],
        "sla_respect_rate": round((total - row["breached"]) / max(total, 1) * 100, 1),
    }


async def _get_anomaly_summary(db, **kwargs) -> Dict[str, Any]:
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no EXISTS subselect).
    # Otherwise: only anomalies whose service_payment belongs to the entity.
    target_entity = kwargs.get("_entity_code")
    # Site-scoped via service_request_id → service_requests.entity_location_id
    # Satellite agents see only anomalies from their site's requests
    sc, sp = _site_scope_via_request(kwargs, "pa", 0, fk_col="service_request_id")

    # The entity EXISTS subselect needs a $N placeholder if active.
    # The same param value is reused across the 3 queries — each query gets
    # its own param tuple so we recompute the placeholder index per-query.
    def _entity_exists_clause(starting_offset: int):
        if not target_entity:
            return "", []
        return (
            f"AND (pa.entity_type != 'service_payment' OR EXISTS ("
            f"SELECT 1 FROM service_payments sp2 "
            f"WHERE sp2.id = pa.entity_id AND sp2.entity_code = ${starting_offset + 1}))",
            [target_entity],
        )

    e_clause_1, e_params_1 = _entity_exists_clause(len(sp))
    rows = await db.fetch(f"""
        SELECT pa.anomaly_type, pa.severity, pa.status, COUNT(*) AS count
        FROM payment_anomalies pa
        WHERE true
          {e_clause_1} {sc}
        GROUP BY pa.anomaly_type, pa.severity, pa.status
        ORDER BY count DESC
    """, *sp, *e_params_1)
    e_clause_2, e_params_2 = _entity_exists_clause(len(sp))
    total = await db.fetchval(f"""
        SELECT COUNT(*) FROM payment_anomalies pa
        WHERE true
          {e_clause_2} {sc}
    """, *sp, *e_params_2)
    e_clause_3, e_params_3 = _entity_exists_clause(len(sp))
    open_count = await db.fetchval(f"""
        SELECT COUNT(*) FROM payment_anomalies pa
        WHERE pa.status NOT IN ('resolved', 'false_positive')
          {e_clause_3} {sc}
    """, *sp, *e_params_3)
    return {
        "total": total or 0,
        "open": open_count or 0,
        "by_type": [{"type": r["anomaly_type"], "severity": r["severity"], "status": r["status"], "count": r["count"]} for r in rows],
    }


async def _get_payment_trends(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")
    sc, sp_params = _site_scope_validated(kwargs, "service_payments", 1)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${1 + len(sp_params) + len(e_params)}"
    rows = await db.fetch(f"""
        SELECT DATE(validated_at) AS date, COUNT(*) AS count,
               COALESCE(SUM(total_amount), 0) AS amount
        FROM service_payments
        WHERE workflow_status = 'completed' AND validated_at >= NOW() - make_interval(days => $1)
          {sc} {e_clause}
        GROUP BY DATE(validated_at) ORDER BY date
    """, days, *sp_params, *e_params)
    return {
        "period_days": days,
        "daily": [{"date": str(r["date"]), "count": r["count"], "amount": float(r["amount"])} for r in rows],
    }


async def _get_reconciliation_status(db, **kwargs) -> Dict[str, Any]:
    # Bank reconciliation is system-level — no site scoping
    row = await db.fetchrow("""
        SELECT
            (SELECT COUNT(*) FROM bank_transactions WHERE service_payment_id IS NULL) AS unreconciled,
            (SELECT COUNT(*) FROM bank_transactions WHERE service_payment_id IS NOT NULL) AS reconciled,
            (SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE service_payment_id IS NULL) AS unreconciled_amount,
            (SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE service_payment_id IS NOT NULL) AS reconciled_amount
    """)
    return {
        "unreconciled_count": row["unreconciled"],
        "reconciled_count": row["reconciled"],
        "unreconciled_amount": float(row["unreconciled_amount"]),
        "reconciled_amount": float(row["reconciled_amount"]),
    }


async def _get_top_payers(db, days: int = 30, limit: int = 10, **kwargs) -> Dict[str, Any]:
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")
    sc, sp_params = _site_scope_validated(kwargs, "sp", 2)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND sp.entity_code = ${2 + len(sp_params) + len(e_params)}"
    rows = await db.fetch(f"""
        SELECT u.full_name AS payer_name, u.email,
               COUNT(*) AS payment_count,
               COALESCE(SUM(sp.total_amount), 0) AS total_paid
        FROM service_payments sp
        JOIN users u ON u.id = sp.user_id
        WHERE sp.workflow_status = 'completed' AND sp.validated_at >= NOW() - make_interval(days => $1)
          {sc} {e_clause}
        GROUP BY u.id, u.full_name, u.email
        ORDER BY total_paid DESC LIMIT $2
    """, days, limit, *sp_params, *e_params)
    return {
        "period_days": days,
        "payers": [{"name": r["payer_name"], "email": r["email"], "payments": r["payment_count"],
                     "total": float(r["total_paid"])} for r in rows],
    }


# ============================================================================
# NEW SQL FUNCTIONS (7 tools — Phase 2)
# ============================================================================

async def _get_entity_comparison(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    """Revenue and volume comparison across entities.

    When kwargs['_entity_code'] is set (entity-scoped supervisor), the result
    is trivially 1 row (own entity) — that is the correct intent. When None
    (admin global), all entities are returned for cross-entity comparison.
    """
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (compares all entities).
    target_entity = kwargs.get("_entity_code")
    sc, sp_params = _site_scope_validated(kwargs, "sp", 1)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND sp.entity_code = ${1 + len(sp_params) + len(e_params)}"
    rows = await db.fetch(f"""
        SELECT sp.entity_code, e.name AS entity_name,
               COUNT(*) AS tx_count,
               COALESCE(SUM(sp.total_amount), 0) AS total_amount,
               COALESCE(AVG(sp.total_amount), 0) AS avg_amount,
               COALESCE(MIN(sp.total_amount), 0) AS min_amount,
               COALESCE(MAX(sp.total_amount), 0) AS max_amount
        FROM service_payments sp
        LEFT JOIN entities e ON e.code = sp.entity_code
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at >= NOW() - make_interval(days => $1)
          {sc} {e_clause}
        GROUP BY sp.entity_code, e.name
        ORDER BY total_amount DESC
    """, days, *sp_params, *e_params)
    grand_total = sum(float(r["total_amount"]) for r in rows) or 1
    return {
        "period_days": days,
        "entities": [{
            "entity_code": r["entity_code"],
            "entity_name": r["entity_name"],
            "tx_count": r["tx_count"],
            "total_amount": float(r["total_amount"]),
            "avg_amount": round(float(r["avg_amount"]), 0),
            "min_amount": float(r["min_amount"]),
            "max_amount": float(r["max_amount"]),
            "pct_total": round(float(r["total_amount"]) / grand_total * 100, 1),
        } for r in rows],
    }


async def _get_payment_aging(db, **kwargs) -> Dict[str, Any]:
    """Time-in-status distribution for pending payments."""
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")
    # Pending payments — site-scoped via service_request entity_location_id
    sc, sp = _site_scope_via_request(kwargs, "service_payments", 0)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${len(sp) + len(e_params)}"
    row = await db.fetchrow(f"""
        SELECT
            COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 < 4) AS lt_4h,
            COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 BETWEEN 4 AND 12) AS h4_12,
            COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 BETWEEN 12 AND 24) AS h12_24,
            COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 BETWEEN 24 AND 48) AS h24_48,
            COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 > 48) AS gt_48h,
            COUNT(*) AS total,
            COALESCE(AVG(EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600), 0) AS avg_hours
        FROM service_payments
        WHERE workflow_status IN ('pending_agent_review', 'agent_reviewing')
          AND requires_agent_validation = true
          {sc}
          {e_clause}
    """, *sp, *e_params)
    return {
        "total_pending": row["total"] or 0,
        "lt_4h": row["lt_4h"] or 0,
        "h4_12": row["h4_12"] or 0,
        "h12_24": row["h12_24"] or 0,
        "h24_48": row["h24_48"] or 0,
        "gt_48h": row["gt_48h"] or 0,
        "avg_hours": round(float(row["avg_hours"]), 1),
    }


async def _get_workflow_pipeline(db, **kwargs) -> Dict[str, Any]:
    """Status funnel counts for the last 90 days — site-scoped via service_request."""
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")
    sc, sp = _site_scope_via_request(kwargs, "service_payments", 0)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${len(sp) + len(e_params)}"
    rows = await db.fetch(f"""
        SELECT workflow_status::text AS status,
               COUNT(*) AS count,
               COALESCE(SUM(total_amount), 0) AS amount
        FROM service_payments
        WHERE created_at >= NOW() - INTERVAL '90 days'
          {sc}
          {e_clause}
        GROUP BY workflow_status
        ORDER BY count DESC
    """, *sp, *e_params)
    return {
        "period": "90 days",
        "statuses": [{
            "status": r["status"],
            "count": r["count"],
            "amount": float(r["amount"]),
        } for r in rows],
    }


async def _get_period_comparison(db, current_days: int = 30, **kwargs) -> Dict[str, Any]:
    """Compare current period vs previous equivalent period."""
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause). Both CTEs
    # reference the same $N placeholder for the entity_code value.
    target_entity = kwargs.get("_entity_code")
    sc, sp_params = _site_scope_validated(kwargs, "service_payments", 1)
    # sc is used in both CTEs — same param placeholder.
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${1 + len(sp_params) + len(e_params)}"
    row = await db.fetchrow(f"""
        WITH current_period AS (
            SELECT COUNT(*) AS tx_count, COALESCE(SUM(total_amount), 0) AS total_amount
            FROM service_payments
            WHERE workflow_status = 'completed'
              AND validated_at >= NOW() - make_interval(days => $1)
              {sc} {e_clause}
        ),
        previous_period AS (
            SELECT COUNT(*) AS tx_count, COALESCE(SUM(total_amount), 0) AS total_amount
            FROM service_payments
            WHERE workflow_status = 'completed'
              AND validated_at >= NOW() - make_interval(days => $1 * 2)
              AND validated_at < NOW() - make_interval(days => $1)
              {sc} {e_clause}
        )
        SELECT
            c.tx_count AS current_count, c.total_amount AS current_amount,
            p.tx_count AS previous_count, p.total_amount AS previous_amount,
            CASE WHEN p.total_amount > 0
                THEN ROUND(((c.total_amount - p.total_amount) / p.total_amount * 100)::numeric, 1)
                ELSE 0 END AS amount_delta_pct,
            CASE WHEN p.tx_count > 0
                THEN ROUND(((c.tx_count - p.tx_count)::numeric / p.tx_count * 100)::numeric, 1)
                ELSE 0 END AS count_delta_pct
        FROM current_period c, previous_period p
    """, current_days, *sp_params, *e_params)
    return {
        "period_days": current_days,
        "current": {"count": row["current_count"], "amount": float(row["current_amount"])},
        "previous": {"count": row["previous_count"], "amount": float(row["previous_amount"])},
        "delta": {
            "amount_pct": float(row["amount_delta_pct"]),
            "count_pct": float(row["count_delta_pct"]),
        },
    }


async def _get_cash_flow_daily(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    """Daily cash flow: inflow (completed) vs outflow (cancelled/expired)."""
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")
    sc, sp_params = _site_scope_validated(kwargs, "service_payments", 1)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${1 + len(sp_params) + len(e_params)}"
    rows = await db.fetch(f"""
        SELECT DATE(validated_at) AS date,
               COALESCE(SUM(total_amount) FILTER (WHERE workflow_status = 'completed'), 0) AS inflow,
               COALESCE(SUM(total_amount) FILTER (
                   WHERE workflow_status IN ('cancelled_by_user', 'cancelled_by_agent', 'expired')
               ), 0) AS outflow
        FROM service_payments
        WHERE validated_at >= NOW() - make_interval(days => $1)
          AND validated_at IS NOT NULL
          {sc} {e_clause}
        GROUP BY DATE(validated_at)
        ORDER BY date
    """, days, *sp_params, *e_params)
    cumulative = 0.0
    daily = []
    for r in rows:
        inflow = float(r["inflow"])
        outflow = float(r["outflow"])
        cumulative += inflow - outflow
        daily.append({
            "date": str(r["date"]),
            "inflow": inflow,
            "outflow": outflow,
            "net": inflow - outflow,
            "cumulative": round(cumulative, 0),
        })
    return {"period_days": days, "daily": daily}


async def _get_rejection_analysis(db, days: int = 30, **kwargs) -> Dict[str, Any]:
    """Rejection patterns by agent and by reason."""
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no EXISTS subselect).
    target_entity = kwargs.get("_entity_code")

    def _entity_exists(agent_alias: str, starting_offset: int):
        """Build EXISTS clause restricting to agents of target_entity.

        agent_alias = column expression for pva.agent_user_id.
        """
        if not target_entity:
            return "", []
        return (
            f"AND EXISTS ("
            f"SELECT 1 FROM agent_profiles ap2 "
            f"JOIN entities e2 ON e2.id = ap2.entity_id "
            f"WHERE ap2.user_id = {agent_alias} "
            f"AND e2.code = ${starting_offset + 1} "
            f"AND ap2.is_active = true)",
            [target_entity],
        )

    sc, sp_params = _site_scope_direct(kwargs, "pva", 1, id_col="agent_user_id")
    e_clause, e_params = _entity_exists("pva.agent_user_id", 1 + len(sp_params))
    agent_rows = await db.fetch(f"""
        SELECT u.full_name AS agent_name,
               COUNT(*) FILTER (WHERE pva.action = 'reject') AS rejections,
               COUNT(*) AS total_actions,
               ROUND(
                   COUNT(*) FILTER (WHERE pva.action = 'reject')::numeric
                   / NULLIF(COUNT(*), 0) * 100, 1
               ) AS rejection_rate
        FROM payment_validation_audit pva
        JOIN users u ON u.id = pva.agent_user_id
        WHERE pva.created_at >= NOW() - make_interval(days => $1)
          AND pva.agent_user_id IS NOT NULL
          {sc} {e_clause}
        GROUP BY u.full_name
        HAVING COUNT(*) FILTER (WHERE pva.action = 'reject') > 0
        ORDER BY rejections DESC
    """, days, *sp_params, *e_params)
    sc2, sp2 = _site_scope_direct(kwargs, "payment_validation_audit", 1, id_col="agent_user_id")
    e2_clause, e2_params = _entity_exists("payment_validation_audit.agent_user_id", 1 + len(sp2))
    reason_rows = await db.fetch(f"""
        SELECT unnest(rejection_reasons) AS reason, COUNT(*) AS count
        FROM payment_validation_audit
        WHERE action = 'reject'
          AND created_at >= NOW() - make_interval(days => $1)
          AND rejection_reasons IS NOT NULL
          AND array_length(rejection_reasons, 1) > 0
          {sc2} {e2_clause}
        GROUP BY reason
        ORDER BY count DESC LIMIT 15
    """, days, *sp2, *e2_params)
    sc3, sp3 = _site_scope_validated(kwargs, "service_payments", 1)
    e3_clause = ""
    e3_params: list = []
    if target_entity:
        e3_params.append(target_entity)
        e3_clause = f"AND service_payments.entity_code = ${1 + len(sp3) + len(e3_params)}"
    resubmit_row = await db.fetchrow(f"""
        SELECT COUNT(*) FILTER (WHERE rejection_count > 0) AS resubmitted,
               COUNT(*) FILTER (WHERE rejection_count > 1) AS multi_rejected,
               AVG(rejection_count) FILTER (WHERE rejection_count > 0) AS avg_rejections
        FROM service_payments
        WHERE created_at >= NOW() - make_interval(days => $1)
          {sc3} {e3_clause}
    """, days, *sp3, *e3_params)
    return {
        "period_days": days,
        "by_agent": [{
            "agent": r["agent_name"],
            "rejections": r["rejections"],
            "total_actions": r["total_actions"],
            "rejection_rate": float(r["rejection_rate"]),
        } for r in agent_rows],
        "by_reason": [{"reason": r["reason"], "count": r["count"]} for r in reason_rows],
        "resubmissions": {
            "resubmitted_count": resubmit_row["resubmitted"] or 0,
            "multi_rejected_count": resubmit_row["multi_rejected"] or 0,
            "avg_rejections": round(float(resubmit_row["avg_rejections"] or 0), 1),
        },
    }


async def _get_anomaly_details(
    db, anomaly_type: str = None, severity: str = None, **kwargs
) -> Dict[str, Any]:
    """Detailed anomaly drill-down with false positive rates. Site-scoped."""
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no EXISTS subselect).
    target_entity = kwargs.get("_entity_code")
    conditions: List[str] = []
    params: list = []
    idx = 1
    if anomaly_type:
        conditions.append(f"pa.anomaly_type::text = ${idx}")
        params.append(anomaly_type)
        idx += 1
    if severity:
        conditions.append(f"pa.severity::text = ${idx}")
        params.append(severity)
        idx += 1
    # Entity scoping (parameterized, only if target_entity set)
    if target_entity:
        conditions.append(
            "(pa.entity_type != 'service_payment' OR EXISTS ("
            "SELECT 1 FROM service_payments sp2 "
            f"WHERE sp2.id = pa.entity_id AND sp2.entity_code = ${idx}))"
        )
        params.append(target_entity)
        idx += 1
    # Site scoping via service_request_id
    sc, sp_site = _site_scope_via_request(kwargs, "pa", idx - 1, fk_col="service_request_id")
    if sc:
        # Strip leading "AND " since we build WHERE dynamically
        conditions.append(sc.strip().removeprefix("AND "))
        params.extend(sp_site)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.fetch(f"""
        SELECT pa.anomaly_type::text AS anomaly_type,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE pa.status = 'false_positive') AS false_positives,
               COUNT(*) FILTER (WHERE pa.status = 'open') AS open_count,
               COUNT(*) FILTER (WHERE pa.status = 'investigating') AS investigating,
               COUNT(*) FILTER (WHERE pa.status = 'resolved') AS resolved,
               COUNT(*) FILTER (WHERE pa.status = 'escalated') AS escalated_count,
               ROUND(
                   COUNT(*) FILTER (WHERE pa.status = 'false_positive')::numeric
                   / NULLIF(COUNT(*), 0) * 100, 1
               ) AS fp_rate
        FROM payment_anomalies pa
        {where_clause}
        GROUP BY pa.anomaly_type
        ORDER BY open_count DESC
    """, *params)

    # Recent actions — also site-scoped + dynamic entity scope
    sc_aa, sp_aa = _site_scope_via_request(kwargs, "pa", 0, fk_col="service_request_id")
    aa_params: list = list(sp_aa)
    aa_e_clause = ""
    if target_entity:
        aa_params.append(target_entity)
        aa_e_clause = (
            "AND (pa.entity_type != 'service_payment' OR EXISTS ("
            "SELECT 1 FROM service_payments sp2 "
            f"WHERE sp2.id = pa.entity_id AND sp2.entity_code = ${len(aa_params)}))"
        )
    aa_where = f"WHERE true {sc_aa} {aa_e_clause}"
    recent = await db.fetch(f"""
        SELECT aa.action, aa.from_status::text, aa.to_status::text,
               aa.comment, aa.performed_at,
               pa.anomaly_type::text
        FROM anomaly_actions aa
        JOIN payment_anomalies pa ON pa.id = aa.anomaly_id
        {aa_where}
        ORDER BY aa.performed_at DESC LIMIT 10
    """, *aa_params)

    return {
        "filters": {"anomaly_type": anomaly_type, "severity": severity},
        "by_type": [{
            "type": r["anomaly_type"],
            "total": r["total"],
            "open": r["open_count"],
            "investigating": r["investigating"],
            "resolved": r["resolved"],
            "escalated": r["escalated_count"],
            "false_positives": r["false_positives"],
            "fp_rate": float(r["fp_rate"]) if r["fp_rate"] else 0,
        } for r in rows],
        "recent_actions": [{
            "action": r["action"],
            "from_status": r["from_status"],
            "to_status": r["to_status"],
            "anomaly_type": r["anomaly_type"],
            "comment": r["comment"],
            "performed_at": str(r["performed_at"]),
        } for r in recent],
    }


# ============================================================================
# FORECAST FUNCTIONS (2 tools — with data sufficiency assessment)
# ============================================================================

async def _get_revenue_forecast(db, days_history: int = 90, **kwargs) -> Dict[str, Any]:
    """Revenue projection based on historical trend.

    Uses simple linear regression + 7-day moving average.
    Returns confidence level based on data point count.
    """
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")
    sc, sp_params = _site_scope_validated(kwargs, "service_payments", 1)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${1 + len(sp_params) + len(e_params)}"
    rows = await db.fetch(f"""
        SELECT DATE(validated_at) AS date,
               COUNT(*) AS tx_count,
               COALESCE(SUM(total_amount), 0) AS amount
        FROM service_payments
        WHERE workflow_status = 'completed'
          AND validated_at >= NOW() - make_interval(days => $1)
          {sc} {e_clause}
        GROUP BY DATE(validated_at)
        ORDER BY date
    """, days_history, *sp_params, *e_params)

    data_points = len(rows)

    # Confidence assessment
    if data_points >= 90:
        confidence = "high"
        confidence_msg = "Datos suficientes para proyección fiable"
    elif data_points >= 30:
        confidence = "medium"
        confidence_msg = f"Tendencia indicativa ({data_points} días de datos). Se recomienda 90+ días."
    else:
        confidence = "low"
        confidence_msg = (
            f"Solo {data_points} puntos de datos disponibles. "
            f"Se requieren al menos 90 días (idealmente 12 meses) para previsiones fiables."
        )

    if data_points < 2:
        return {
            "days_history": days_history,
            "data_points": data_points,
            "confidence": confidence,
            "confidence_msg": confidence_msg,
            "forecast": None,
            "message": "Datos insuficientes para calcular proyección (mínimo 2 días).",
        }

    # Calculate daily amounts
    daily_amounts = [float(r["amount"]) for r in rows]
    daily_counts = [r["tx_count"] for r in rows]

    # 7-day moving average (or available window)
    window = min(7, data_points)
    ma_amounts = daily_amounts[-window:]
    ma_avg = sum(ma_amounts) / len(ma_amounts) if ma_amounts else 0

    # Simple linear trend: slope of daily amounts
    n = len(daily_amounts)
    x_mean = (n - 1) / 2.0
    y_mean = sum(daily_amounts) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(daily_amounts))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0

    # Forecast: project 7, 14, 30 days forward
    last_val = daily_amounts[-1] if daily_amounts else 0
    forecasts = {}
    for proj_days in [7, 14, 30]:
        projected_daily = last_val + slope * proj_days
        projected_daily = max(projected_daily, 0)  # No negative revenue
        forecasts[f"next_{proj_days}d"] = {
            "projected_daily_avg": round(projected_daily, 0),
            "projected_total": round(projected_daily * proj_days, 0),
        }

    # Overall stats
    total_amount = sum(daily_amounts)
    avg_daily = total_amount / data_points if data_points else 0

    return {
        "days_history": days_history,
        "data_points": data_points,
        "confidence": confidence,
        "confidence_msg": confidence_msg,
        "historical": {
            "total_amount": round(total_amount, 0),
            "avg_daily_amount": round(avg_daily, 0),
            "avg_daily_txns": round(sum(daily_counts) / data_points, 1) if data_points else 0,
            "moving_avg_7d": round(ma_avg, 0),
        },
        "trend": {
            "direction": "up" if slope > 0 else ("down" if slope < 0 else "flat"),
            "daily_change": round(slope, 0),
            "pct_change_per_week": round(slope * 7 / max(avg_daily, 1) * 100, 1),
        },
        "forecast": forecasts,
    }


async def _get_workload_forecast(db, days_history: int = 90, **kwargs) -> Dict[str, Any]:
    """Workload projection: volume of incoming payment requests.

    Tracks daily new payments (all statuses) to project future workload.
    Site-scoped via service_request entity_location_id.
    """
    # Bug 1 fix dynamic (2026-05-06): entity scope driven by
    # kwargs['_entity_code']. None = global admin (no clause).
    target_entity = kwargs.get("_entity_code")
    sc, sp = _site_scope_via_request(kwargs, "service_payments", 1)
    e_clause = ""
    e_params: list = []
    if target_entity:
        e_params.append(target_entity)
        e_clause = f"AND service_payments.entity_code = ${1 + len(sp) + len(e_params)}"
    rows = await db.fetch(f"""
        SELECT DATE(created_at) AS date,
               COUNT(*) AS new_payments,
               COUNT(*) FILTER (WHERE requires_agent_validation = true) AS requiring_validation
        FROM service_payments
        WHERE created_at >= NOW() - make_interval(days => $1)
          {sc}
          {e_clause}
        GROUP BY DATE(created_at)
        ORDER BY date
    """, days_history, *sp, *e_params)

    data_points = len(rows)

    if data_points >= 90:
        confidence = "high"
        confidence_msg = "Datos suficientes para proyección fiable"
    elif data_points >= 30:
        confidence = "medium"
        confidence_msg = f"Tendencia indicativa ({data_points} días de datos)"
    else:
        confidence = "low"
        confidence_msg = f"Solo {data_points} puntos de datos. Previsión no fiable."

    if data_points < 2:
        return {
            "days_history": days_history,
            "data_points": data_points,
            "confidence": confidence,
            "confidence_msg": confidence_msg,
            "forecast": None,
            "message": "Datos insuficientes para proyección de carga de trabajo.",
        }

    daily_volumes = [r["new_payments"] for r in rows]
    daily_validations = [r["requiring_validation"] for r in rows]

    # Moving averages
    window = min(7, data_points)
    ma_volume = sum(daily_volumes[-window:]) / window
    ma_validations = sum(daily_validations[-window:]) / window

    # Trend
    n = len(daily_volumes)
    x_mean = (n - 1) / 2.0
    y_mean = sum(daily_volumes) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(daily_volumes))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0

    # Current pending backlog — site-scoped + dynamic entity scope
    sc_p, sp_p = _site_scope_via_request(kwargs, "service_payments", 0)
    p_e_clause = ""
    p_e_params: list = []
    if target_entity:
        p_e_params.append(target_entity)
        p_e_clause = f"AND service_payments.entity_code = ${len(sp_p) + len(p_e_params)}"
    pending = await db.fetchval(f"""
        SELECT COUNT(*) FROM service_payments
        WHERE workflow_status IN ('pending_agent_review', 'agent_reviewing')
          AND requires_agent_validation = true
          {sc_p}
          {p_e_clause}
    """, *sp_p, *p_e_params)

    # Forecast
    forecasts = {}
    for proj_days in [7, 14, 30]:
        projected_daily = max(ma_volume + slope * proj_days / 2, 0)
        forecasts[f"next_{proj_days}d"] = {
            "projected_daily_avg": round(projected_daily, 1),
            "projected_total_new": round(projected_daily * proj_days, 0),
            "projected_requiring_validation": round(ma_validations * proj_days, 0),
        }

    return {
        "days_history": days_history,
        "data_points": data_points,
        "confidence": confidence,
        "confidence_msg": confidence_msg,
        "current_backlog": pending or 0,
        "historical": {
            "avg_daily_new": round(sum(daily_volumes) / data_points, 1),
            "avg_daily_validations": round(sum(daily_validations) / data_points, 1),
            "moving_avg_7d_volume": round(ma_volume, 1),
            "moving_avg_7d_validations": round(ma_validations, 1),
        },
        "trend": {
            "direction": "up" if slope > 0 else ("down" if slope < 0 else "flat"),
            "daily_change": round(slope, 2),
        },
        "forecast": forecasts,
    }


# Function map (str → async callable) — 17 tools
FUNCTION_MAP: Dict[str, Callable] = {
    # Original 8
    "get_revenue_summary": _get_revenue_summary,
    "get_revenue_by_service": _get_revenue_by_service,
    "get_agent_performance": _get_agent_performance,
    "get_sla_status": _get_sla_status,
    "get_anomaly_summary": _get_anomaly_summary,
    "get_payment_trends": _get_payment_trends,
    "get_reconciliation_status": _get_reconciliation_status,
    "get_top_payers": _get_top_payers,
    # New 7
    "get_entity_comparison": _get_entity_comparison,
    "get_payment_aging": _get_payment_aging,
    "get_workflow_pipeline": _get_workflow_pipeline,
    "get_period_comparison": _get_period_comparison,
    "get_cash_flow_daily": _get_cash_flow_daily,
    "get_rejection_analysis": _get_rejection_analysis,
    "get_anomaly_details": _get_anomaly_details,
    # Forecast 2
    "get_revenue_forecast": _get_revenue_forecast,
    "get_workload_forecast": _get_workload_forecast,
}


# ============================================================================
# SERVICE CLASS
# ============================================================================

class TreasuryAnalystService(BaseAnalystService):
    """Gemini function-calling service for treasury financial Q&A."""

    def _get_system_prompt(self) -> str:
        now = datetime.now(timezone.utc)
        days_es = [
            "lunes", "martes", "miércoles", "jueves",
            "viernes", "sábado", "domingo",
        ]
        return SYSTEM_PROMPT_TEMPLATE.format(
            current_date=now.strftime("%Y-%m-%d"),
            day_of_week=days_es[now.weekday()],
        )

    def _get_function_declarations(self) -> list:
        return _FUNC_DECLS

    def _get_function_map(self) -> Dict[str, Callable]:
        return FUNCTION_MAP

    def _get_service_name(self) -> str:
        return "Treasury Analyst"

    def _get_agent_type(self) -> str:
        return "treasury"

    def _get_second_call_max_tokens(self) -> int:
        return 4096

    def _get_max_tool_rounds(self) -> int:
        """Allow up to 3 rounds: initial tools → conditional drill-down → analysis."""
        return 3

    def _build_artifacts(self, tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build typed artifacts from SQL tool results (deterministic, no LLM)."""
        artifacts: List[Dict[str, Any]] = []

        def _fmt(v, is_amount=False) -> str:
            """Format numeric value for display."""
            if v is None:
                return "—"
            if is_amount:
                return f"{float(v):,.0f}"
            if isinstance(v, float):
                return f"{v:.1f}" if v != int(v) else str(int(v))
            return str(v)

        for tool_name, data in tool_results.items():
            if isinstance(data, dict) and "error" in data:
                continue

            if tool_name == "get_revenue_summary":
                c = data.get("completed", {})
                p = data.get("pending", {})
                artifacts.append({
                    "type": "kpi_grid",
                    "title": f"Resumen de Ingresos ({data.get('period_days', 30)} días)",
                    "metrics": [
                        {"label": "Ingresos Completados", "value": f"{_fmt(c.get('amount'), True)} XAF"},
                        {"label": "Transacciones", "value": _fmt(c.get("count"))},
                        {"label": "Promedio", "value": f"{_fmt(c.get('avg'), True)} XAF"},
                        {"label": "Pendientes", "value": _fmt(p.get("count"))},
                    ],
                })
                if data.get("by_entity"):
                    artifacts.append({
                        "type": "table",
                        "title": "Ingresos por Entidad",
                        "headers": ["Entidad", "Código", "Transacciones", "Monto (XAF)"],
                        "rows": [
                            [e.get("entity_name") or "—", e.get("entity_code") or "—",
                             _fmt(e.get("count")), _fmt(e.get("amount"), True)]
                            for e in data["by_entity"]
                        ],
                        "alignments": ["left", "left", "right", "right"],
                    })

            elif tool_name == "get_revenue_by_service":
                if data.get("services"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Ingresos por Servicio ({data.get('period_days', 30)} días)",
                        "headers": ["Servicio", "Código", "Transacciones", "Monto (XAF)"],
                        "rows": [
                            [s.get("name") or "—", s.get("code") or "—",
                             _fmt(s.get("count")), _fmt(s.get("amount"), True)]
                            for s in data["services"]
                        ],
                        "alignments": ["left", "left", "right", "right"],
                    })

            elif tool_name == "get_agent_performance":
                if data.get("agents"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Rendimiento de Agentes ({data.get('period_days', 30)} días)",
                        "headers": ["Agente", "Validaciones", "Rechazos", "Tiempo Prom. (min)", "SLA %"],
                        "rows": [
                            [a.get("name") or "—", _fmt(a.get("validations")),
                             _fmt(a.get("rejections")), _fmt(a.get("avg_minutes")),
                             f"{_fmt(a.get('sla_rate'))}%"]
                            for a in data["agents"]
                        ],
                        "alignments": ["left", "right", "right", "right", "right"],
                    })

            elif tool_name == "get_sla_status":
                artifacts.append({
                    "type": "kpi_grid",
                    "title": "Estado SLA",
                    "metrics": [
                        {"label": "Tasa SLA", "value": f"{_fmt(data.get('sla_respect_rate'))}%"},
                        {"label": "Vencidos", "value": _fmt(data.get("breached"))},
                        {"label": "Críticos", "value": _fmt(data.get("critical"))},
                        {"label": "Pendientes Total", "value": _fmt(data.get("total_pending"))},
                    ],
                })

            elif tool_name == "get_anomaly_summary":
                artifacts.append({
                    "type": "kpi_grid",
                    "title": "Anomalías",
                    "metrics": [
                        {"label": "Total", "value": _fmt(data.get("total"))},
                        {"label": "Abiertas", "value": _fmt(data.get("open"))},
                    ],
                })
                if data.get("by_type"):
                    artifacts.append({
                        "type": "table",
                        "title": "Anomalías por Tipo",
                        "headers": ["Tipo", "Severidad", "Estado", "Cantidad"],
                        "rows": [
                            [t.get("type") or "—", t.get("severity") or "—",
                             t.get("status") or "—", _fmt(t.get("count"))]
                            for t in data["by_type"]
                        ],
                        "alignments": ["left", "left", "left", "right"],
                    })

            elif tool_name == "get_payment_trends":
                if data.get("daily"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Tendencia de Pagos ({data.get('period_days', 30)} días)",
                        "headers": ["Fecha", "Transacciones", "Monto (XAF)"],
                        "rows": [
                            [d.get("date") or "—", _fmt(d.get("count")), _fmt(d.get("amount"), True)]
                            for d in data["daily"]
                        ],
                        "alignments": ["left", "right", "right"],
                    })

            elif tool_name == "get_reconciliation_status":
                artifacts.append({
                    "type": "kpi_grid",
                    "title": "Estado Reconciliación Bancaria",
                    "metrics": [
                        {"label": "Reconciliadas", "value": _fmt(data.get("reconciled_count"))},
                        {"label": "No Reconciliadas", "value": _fmt(data.get("unreconciled_count"))},
                        {"label": "Monto Reconciliado", "value": f"{_fmt(data.get('reconciled_amount'), True)} XAF"},
                        {"label": "Monto Sin Reconciliar", "value": f"{_fmt(data.get('unreconciled_amount'), True)} XAF"},
                    ],
                })

            elif tool_name == "get_top_payers":
                if data.get("payers"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Top Contribuyentes ({data.get('period_days', 30)} días)",
                        "headers": ["Contribuyente", "Email", "Pagos", "Total (XAF)"],
                        "rows": [
                            [p.get("name") or "—", p.get("email") or "—",
                             _fmt(p.get("payments")), _fmt(p.get("total"), True)]
                            for p in data["payers"]
                        ],
                        "alignments": ["left", "left", "right", "right"],
                    })

            elif tool_name == "get_entity_comparison":
                if data.get("entities"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Comparación Entidades ({data.get('period_days', 30)} días)",
                        "headers": ["Entidad", "Código", "Transacciones", "Total (XAF)", "Promedio (XAF)", "% Total"],
                        "rows": [
                            [e.get("entity_name") or "—", e.get("entity_code") or "—",
                             _fmt(e.get("tx_count")), _fmt(e.get("total_amount"), True),
                             _fmt(e.get("avg_amount"), True), f"{_fmt(e.get('pct_total'))}%"]
                            for e in data["entities"]
                        ],
                        "alignments": ["left", "left", "right", "right", "right", "right"],
                    })

            elif tool_name == "get_payment_aging":
                artifacts.append({
                    "type": "table",
                    "title": "Antigüedad Pagos Pendientes",
                    "headers": ["Rango", "Cantidad"],
                    "rows": [
                        ["< 4 horas", _fmt(data.get("lt_4h"))],
                        ["4–12 horas", _fmt(data.get("h4_12"))],
                        ["12–24 horas", _fmt(data.get("h12_24"))],
                        ["24–48 horas", _fmt(data.get("h24_48"))],
                        ["> 48 horas", _fmt(data.get("gt_48h"))],
                    ],
                    "alignments": ["left", "right"],
                })
                artifacts.append({
                    "type": "kpi_grid",
                    "title": "Resumen Aging",
                    "metrics": [
                        {"label": "Total Pendientes", "value": _fmt(data.get("total_pending"))},
                        {"label": "Promedio (horas)", "value": _fmt(data.get("avg_hours"))},
                    ],
                })

            elif tool_name == "get_workflow_pipeline":
                if data.get("statuses"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Pipeline de Workflow ({data.get('period', '90 days')})",
                        "headers": ["Estado", "Cantidad", "Monto (XAF)"],
                        "rows": [
                            [s.get("status") or "—", _fmt(s.get("count")), _fmt(s.get("amount"), True)]
                            for s in data["statuses"]
                        ],
                        "alignments": ["left", "right", "right"],
                    })

            elif tool_name == "get_period_comparison":
                cur = data.get("current", {})
                prev = data.get("previous", {})
                delta = data.get("delta", {})
                artifacts.append({
                    "type": "table",
                    "title": f"Comparación Períodos ({data.get('period_days', 30)} días)",
                    "headers": ["Métrica", "Período Actual", "Período Anterior", "Delta %"],
                    "rows": [
                        ["Transacciones", _fmt(cur.get("count")), _fmt(prev.get("count")),
                         f"{_fmt(delta.get('count_pct'))}%"],
                        ["Monto (XAF)", _fmt(cur.get("amount"), True), _fmt(prev.get("amount"), True),
                         f"{_fmt(delta.get('amount_pct'))}%"],
                    ],
                    "alignments": ["left", "right", "right", "right"],
                })
                change_pct = delta.get("amount_pct", 0)
                artifacts.append({
                    "type": "kpi_grid",
                    "title": "Variación Ingresos",
                    "metrics": [
                        {"label": "Ingresos Actuales", "value": f"{_fmt(cur.get('amount'), True)} XAF",
                         "change_pct": float(change_pct) if change_pct else None},
                    ],
                })

            elif tool_name == "get_cash_flow_daily":
                if data.get("daily"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Flujo de Caja Diario ({data.get('period_days', 30)} días)",
                        "headers": ["Fecha", "Ingresos (XAF)", "Egresos (XAF)", "Neto (XAF)", "Acumulado (XAF)"],
                        "rows": [
                            [d.get("date") or "—", _fmt(d.get("inflow"), True),
                             _fmt(d.get("outflow"), True), _fmt(d.get("net"), True),
                             _fmt(d.get("cumulative"), True)]
                            for d in data["daily"]
                        ],
                        "alignments": ["left", "right", "right", "right", "right"],
                    })

            elif tool_name == "get_rejection_analysis":
                if data.get("by_agent"):
                    artifacts.append({
                        "type": "table",
                        "title": f"Rechazos por Agente ({data.get('period_days', 30)} días)",
                        "headers": ["Agente", "Rechazos", "Acciones Total", "Tasa Rechazo %"],
                        "rows": [
                            [a.get("agent") or "—", _fmt(a.get("rejections")),
                             _fmt(a.get("total_actions")), f"{_fmt(a.get('rejection_rate'))}%"]
                            for a in data["by_agent"]
                        ],
                        "alignments": ["left", "right", "right", "right"],
                    })
                if data.get("by_reason"):
                    artifacts.append({
                        "type": "table",
                        "title": "Motivos de Rechazo",
                        "headers": ["Motivo", "Cantidad"],
                        "rows": [
                            [r.get("reason") or "—", _fmt(r.get("count"))]
                            for r in data["by_reason"]
                        ],
                        "alignments": ["left", "right"],
                    })
                resub = data.get("resubmissions", {})
                if resub.get("resubmitted_count", 0) > 0:
                    artifacts.append({
                        "type": "kpi_grid",
                        "title": "Reenvíos",
                        "metrics": [
                            {"label": "Reenviados", "value": _fmt(resub.get("resubmitted_count"))},
                            {"label": "Multi-Rechazados", "value": _fmt(resub.get("multi_rejected_count"))},
                            {"label": "Prom. Rechazos", "value": _fmt(resub.get("avg_rejections"))},
                        ],
                    })

            elif tool_name == "get_anomaly_details":
                if data.get("by_type"):
                    artifacts.append({
                        "type": "table",
                        "title": "Detalle de Anomalías",
                        "headers": ["Tipo", "Total", "Abiertas", "Investigando", "Resueltas", "FP", "Tasa FP %"],
                        "rows": [
                            [t.get("type") or "—", _fmt(t.get("total")),
                             _fmt(t.get("open")), _fmt(t.get("investigating")),
                             _fmt(t.get("resolved")), _fmt(t.get("false_positives")),
                             f"{_fmt(t.get('fp_rate'))}%"]
                            for t in data["by_type"]
                        ],
                        "alignments": ["left", "right", "right", "right", "right", "right", "right"],
                    })
                if data.get("recent_actions"):
                    artifacts.append({
                        "type": "table",
                        "title": "Acciones Recientes sobre Anomalías",
                        "headers": ["Acción", "Tipo Anomalía", "De", "A", "Fecha"],
                        "rows": [
                            [a.get("action") or "—", a.get("anomaly_type") or "—",
                             a.get("from_status") or "—", a.get("to_status") or "—",
                             (a.get("performed_at") or "—")[:16]]
                            for a in data["recent_actions"]
                        ],
                        "alignments": ["left", "left", "left", "left", "left"],
                    })

            elif tool_name == "get_revenue_forecast":
                hist = data.get("historical", {})
                trend = data.get("trend", {})
                confidence = data.get("confidence", "low")
                confidence_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
                artifacts.append({
                    "type": "kpi_grid",
                    "title": f"Previsión Ingresos ({confidence_icon} {confidence})",
                    "metrics": [
                        {"label": "Media Diaria", "value": f"{_fmt(hist.get('avg_daily_amount'), True)} XAF"},
                        {"label": "Media Móvil 7d", "value": f"{_fmt(hist.get('moving_avg_7d'), True)} XAF"},
                        {"label": "Tendencia", "value": trend.get("direction", "—")},
                        {"label": "Δ Semanal", "value": f"{_fmt(trend.get('pct_change_per_week'))}%",
                         "change_pct": trend.get("pct_change_per_week")},
                    ],
                })
                fc = data.get("forecast")
                if fc:
                    artifacts.append({
                        "type": "table",
                        "title": "Proyección de Ingresos",
                        "headers": ["Período", "Prom. Diario (XAF)", "Total Proyectado (XAF)"],
                        "rows": [
                            [label, _fmt(fc[key].get("projected_daily_avg"), True),
                             _fmt(fc[key].get("projected_total"), True)]
                            for label, key in [
                                ("Próximos 7 días", "next_7d"),
                                ("Próximos 14 días", "next_14d"),
                                ("Próximos 30 días", "next_30d"),
                            ]
                            if key in fc
                        ],
                        "alignments": ["left", "right", "right"],
                    })
                if confidence == "low":
                    artifacts.append({
                        "type": "summary",
                        "title": "Advertencia de Fiabilidad",
                        "content": data.get("confidence_msg", "Datos insuficientes"),
                        "severity": "warning",
                    })

            elif tool_name == "get_workload_forecast":
                hist = data.get("historical", {})
                trend = data.get("trend", {})
                confidence = data.get("confidence", "low")
                confidence_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
                artifacts.append({
                    "type": "kpi_grid",
                    "title": f"Previsión Carga Trabajo ({confidence_icon} {confidence})",
                    "metrics": [
                        {"label": "Backlog Actual", "value": _fmt(data.get("current_backlog"))},
                        {"label": "Prom. Diario Nuevos", "value": _fmt(hist.get("avg_daily_new"))},
                        {"label": "MA 7d Validaciones", "value": _fmt(hist.get("moving_avg_7d_validations"))},
                        {"label": "Tendencia", "value": trend.get("direction", "—")},
                    ],
                })
                fc = data.get("forecast")
                if fc:
                    artifacts.append({
                        "type": "table",
                        "title": "Proyección Carga de Trabajo",
                        "headers": ["Período", "Prom. Diario", "Total Nuevos", "Requieren Validación"],
                        "rows": [
                            [label, _fmt(fc[key].get("projected_daily_avg")),
                             _fmt(fc[key].get("projected_total_new")),
                             _fmt(fc[key].get("projected_requiring_validation"))]
                            for label, key in [
                                ("Próximos 7 días", "next_7d"),
                                ("Próximos 14 días", "next_14d"),
                                ("Próximos 30 días", "next_30d"),
                            ]
                            if key in fc
                        ],
                        "alignments": ["left", "right", "right", "right"],
                    })
                if confidence == "low":
                    artifacts.append({
                        "type": "summary",
                        "title": "Advertencia de Fiabilidad",
                        "content": data.get("confidence_msg", "Datos insuficientes"),
                        "severity": "warning",
                    })

        return artifacts

    async def generate_briefing(self, db, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate automated briefing from pre-computed data.

        Args:
            db: Database connection
            context: Entity context (entity_code, entity_location_id, is_main_office)
        """
        self._ensure_initialized()

        # Build entity kwargs for site scoping
        entity_kwargs = self._build_entity_kwargs(context or {})

        # Gather key metrics in parallel — each with its own pooled connection.
        from app.database.connection import db_manager

        async def _safe_revenue():
            async with db_manager.get_connection() as conn:
                return await _get_revenue_summary(conn, days=7, **entity_kwargs)

        async def _safe_sla():
            async with db_manager.get_connection() as conn:
                return await _get_sla_status(conn, **entity_kwargs)

        async def _safe_anomalies():
            async with db_manager.get_connection() as conn:
                return await _get_anomaly_summary(conn, **entity_kwargs)

        async def _safe_trends():
            async with db_manager.get_connection() as conn:
                return await _get_payment_trends(conn, days=7, **entity_kwargs)

        revenue, sla, anomalies, trends = await asyncio.gather(
            _safe_revenue(),
            _safe_sla(),
            _safe_anomalies(),
            _safe_trends(),
        )

        # Determine priority
        priority = "normal"
        if sla["breached"] > 0 or anomalies["open"] > 3:
            priority = "urgent"
        elif sla["critical"] > 0 or sla["warning"] > 0 or anomalies["open"] > 0:
            priority = "attention"

        if not self._model:
            # Fallback without LLM — derive basic recommendations from data
            fallback_recs = []
            if sla["breached"] > 0:
                fallback_recs.append(f"Revisar {sla['breached']} pago(s) con SLA vencido urgentemente")
            if anomalies["open"] > 0:
                fallback_recs.append(f"Investigar {anomalies['open']} anomalía(s) abierta(s)")
            if revenue["pending"]["count"] > 10:
                fallback_recs.append(f"Gestionar {revenue['pending']['count']} pagos pendientes de validación")
            if not fallback_recs:
                fallback_recs.append("Situación normal — continuar monitoreo estándar")

            return {
                "briefing": (
                    f"**Ingresos 7 días**: {revenue['completed']['amount']:,.0f} XAF "
                    f"({revenue['completed']['count']} transacciones). "
                    f"**Pendientes**: {revenue['pending']['count']}. "
                    f"**SLA**: {sla['sla_respect_rate']}% respeto ({sla['breached']} vencidos). "
                    f"**Anomalías**: {anomalies['open']} abiertas."
                ),
                "priority": priority,
                "recommendations": fallback_recs,
            }

        # Use LLM for natural language briefing — structured JSON response
        data_summary = json.dumps(
            {"revenue_7d": revenue, "sla": sla, "anomalies": anomalies, "trends_7d": trends},
            default=str, ensure_ascii=False,
        )

        briefing_prompt = (
            f"Analiza los datos financieros del Tesoro y responde ÚNICAMENTE con un objeto JSON válido "
            f"(sin bloques de código markdown, sin texto adicional).\n\n"
            f"Formato exacto requerido:\n"
            f'{{"briefing": "<resumen ejecutivo 100-150 palabras: ingresos, SLA, anomalías, tendencias>", '
            f'"recommendations": ["<acción concreta 1>", "<acción concreta 2>", "<acción concreta 3>"]}}\n\n'
            f"Reglas:\n"
            f"- briefing: narrativa fluida en español, markdown básico (**negrita**), cifras exactas en XAF\n"
            f"- recommendations: array de 2-4 acciones concretas y priorizadas, basadas SOLO en los datos\n"
            f"- Si no hay anomalías ni alertas, recommendations puede tener 1-2 acciones preventivas\n"
            f"- NUNCA inventes datos que no aparezcan en los datos proporcionados\n\n"
            f"DATOS:\n{data_summary}"
        )

        briefing_text = ""
        recommendations: list = []

        try:
            response = await asyncio.wait_for(
                traced_generate_sync(
                    self._model, briefing_prompt,
                    feature="analyst_treasury",
                    generation_config=GenerationConfig(temperature=0.2, max_output_tokens=600),
                ),
                timeout=GEMINI_TIMEOUT_SECOND_CALL,
            )
            try:
                raw = (response.text or "").strip()
                # Strip markdown code fences if present
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.strip()
                parsed = json.loads(raw)
                briefing_text = parsed.get("briefing", "").strip()
                recommendations = [
                    str(r) for r in parsed.get("recommendations", []) if r
                ]
            except (ValueError, AttributeError, json.JSONDecodeError) as e:
                logger.warning(f"Treasury briefing JSON parse failed: {e}, using raw text")
                # Fallback: use raw text as briefing if JSON parsing fails
                try:
                    briefing_text = (response.text or "").strip()
                except (ValueError, AttributeError):
                    briefing_text = ""
        except Exception as e:
            logger.error(f"Treasury briefing LLM failed: {e}")

        if not briefing_text:
            briefing_text = (
                f"**Ingresos 7 días**: {revenue['completed']['amount']:,.0f} XAF "
                f"({revenue['completed']['count']} transacciones). "
                f"**Pendientes**: {revenue['pending']['count']}. "
                f"**SLA**: {sla['sla_respect_rate']}% respeto."
            )

        return {
            "briefing": briefing_text,
            "priority": priority,
            "recommendations": recommendations,
            "data": {"revenue": revenue, "sla": sla, "anomalies_open": anomalies["open"]},
        }


# Singleton
treasury_analyst_service = TreasuryAnalystService()
