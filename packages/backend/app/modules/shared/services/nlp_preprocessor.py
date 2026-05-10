"""
ML-based NLP Pre-processor for LLM Analyst Agents (Treasury + Admin).

Architecture
────────────
  0. Text normalization    : unicode NFKD (strip accents), lowercase, common typo
                              correction, abbreviation expansion — BEFORE classification
  1. Intent classification  : TF-IDF (1,2-gram) + LogisticRegression (sklearn)
                              → real calibrated probability over 11 intents
                              → trained from 524 seed examples (Treasury + Admin) at startup
                              → upgradeable at runtime from Redis (weekly retrain)
  2. Slot extraction        : regex (deterministic, O(1) per slot type)
                              entity_codes, time_period, metric, agent_name, amount
  3. Confidence score       : max(predict_proba) — true probability, not fake count
  4. intent_probabilities   : full 11-class distribution stored for ML training

Fallback chain: ML classifier → regex → GENERAL intent (sklearn not available)

FUNCTION_TO_INTENT mapping enables distant supervision:
  Gemini calls function X → intent is FUNCTION_TO_INTENT[X] — free ground truth.
"""

import io
import re
import base64
import threading
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


# ── sklearn soft dependency ───────────────────────────────────────────────────

_SKLEARN_AVAILABLE = False
try:
    from sklearn.pipeline import Pipeline                              # type: ignore
    from sklearn.feature_extraction.text import TfidfVectorizer       # type: ignore
    from sklearn.linear_model import LogisticRegression               # type: ignore
    import joblib                                                      # type: ignore
    _SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("sklearn/joblib not available — falling back to regex intent classification")


# ──────────────────────────────────────────────────────────────────────────────
# Text Normalization (typos, accents, abbreviations)
# ──────────────────────────────────────────────────────────────────────────────

# Common misspellings/typos → correct form (GE Spanish context)
_TYPO_CORRECTIONS: Dict[str, str] = {
    # Keyboard inversions
    "pagso": "pagos", "pagso": "pagos", "apgos": "pagos",
    "agentes": "agentes", "agentse": "agentes", "agenets": "agentes",
    "teasoreria": "tesoreria", "teosreria": "tesoreria", "tresoreria": "tesoreria",
    "rendimietno": "rendimiento", "rendiemiento": "rendimiento",
    "recaudacion": "recaudacion", "rekaudacion": "recaudacion", "recuadacion": "recaudacion",
    "reconcliiacion": "reconciliacion", "reconcilacion": "reconciliacion",
    "anomlaias": "anomalias", "anomlias": "anomalias", "anomalas": "anomalias",
    "tendecnia": "tendencia", "tendecia": "tendencia",
    "comparar": "comparar", "comprar": "comparar",
    "eficiecnia": "eficiencia", "eficienicia": "eficiencia",
    "productivdiad": "productividad", "produtividad": "productividad",
    "estadisitcas": "estadisticas", "estadisitcas": "estadisticas",
    "ingreos": "ingresos", "ingesos": "ingresos", "ingersos": "ingresos",
    "distibucion": "distribucion", "distribcuion": "distribucion",
    "complimiento": "cumplimiento", "cumplimeinto": "cumplimiento",
    # Phonetic (GE Spanish)
    "rekaudacion": "recaudacion", "rekonciliacion": "reconciliacion",
    "anomaliya": "anomalia", "trasacciones": "transacciones",
}

# Abbreviation expansion (common in chat-style queries)
_ABBREVIATION_MAP: Dict[str, str] = {
    "q ": "que ", "xq": "porque", "x q": "por que",
    "tb": "tambien", "tmb": "tambien",
    "pq": "porque", "dpto": "departamento",
    "info": "informacion", "stats": "estadisticas",
    "mins": "minutos", "hrs": "horas",
}

_TYPO_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _TYPO_CORRECTIONS) + r")\b",
    re.IGNORECASE,
)

_ABBREV_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _ABBREVIATION_MAP) + r")\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """
    Normalize user input for intent classification.

    Pipeline:
      1. Unicode NFKD decomposition → strip combining marks (accents)
      2. Lowercase
      3. Correct common typos
      4. Expand abbreviations
      5. Collapse whitespace

    Designed for robustness: agents type fast, make typos, skip accents.
    Original text preserved for slot extraction (entity codes are case-sensitive).
    """
    # 1. Strip accents via NFKD
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")

    # 2. Lowercase
    norm = stripped.lower()

    # 3. Correct typos
    norm = _TYPO_PATTERN.sub(lambda m: _TYPO_CORRECTIONS.get(m.group(0).lower(), m.group(0)), norm)

    # 4. Expand abbreviations
    norm = _ABBREV_PATTERN.sub(lambda m: _ABBREVIATION_MAP.get(m.group(0).lower(), m.group(0)), norm)

    # 5. Collapse whitespace
    norm = re.sub(r"\s+", " ", norm).strip()

    return norm


# ──────────────────────────────────────────────────────────────────────────────
# Intent Categories
# ──────────────────────────────────────────────────────────────────────────────

class IntentCategory(Enum):
    """11 coarse-grained intents covering treasury and admin agent domains."""
    AGENT_AVAILABILITY = "agent_availability"  # Who is online / connected
    AGENT_SPECIFIC     = "agent_specific"       # Stats for one named agent
    WORKLOAD           = "workload"             # Queue distribution / capacity
    SLA                = "sla"                  # SLA compliance / deadlines
    PERFORMANCE        = "performance"          # Rankings, rates, efficiency
    ANOMALY            = "anomaly"              # Statistical anomalies / alerts
    TREND              = "trend"                # Time-series / evolution / forecast
    REVENUE            = "revenue"              # Financial totals (treasury)
    ENTITY_COMPARE     = "entity_compare"       # Cross-entity comparison
    RECONCILIATION     = "reconciliation"       # Bank reconciliation
    GENERAL            = "general"              # Fallback — no clear signal


# ──────────────────────────────────────────────────────────────────────────────
# Extracted Slots
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractedSlots:
    """Structured slots extracted from a natural language question."""
    intent:               IntentCategory          = IntentCategory.GENERAL
    entity_codes:         List[str]               = field(default_factory=list)
    agent_name:           Optional[str]           = None
    time_period_days:     Optional[int]           = None
    metric:               Optional[str]           = None
    amount_threshold:     Optional[float]         = None
    confidence:           float                   = 0.0
    raw_time_expr:        Optional[str]           = None
    keywords_matched:     List[str]               = field(default_factory=list)
    intent_probabilities: Optional[Dict[str, float]] = None  # Full 11-class distribution


# ──────────────────────────────────────────────────────────────────────────────
# Function → Intent mapping (distant supervision)
# ──────────────────────────────────────────────────────────────────────────────

FUNCTION_TO_INTENT: Dict[str, str] = {
    # ── Treasury Analyst (17 functions) ──────────────────────────────────────
    "get_revenue_summary":          "revenue",
    "get_pending_payments_sla":     "sla",
    "get_agent_performance":        "performance",
    "get_anomaly_report":           "anomaly",
    "get_revenue_trend":            "trend",
    "get_entity_comparison":        "entity_compare",
    "get_rejection_analysis":       "performance",
    "get_payment_reconciliation":   "reconciliation",
    "get_top_services":             "revenue",
    "get_payment_method_breakdown": "revenue",
    "get_hourly_revenue":           "trend",
    "get_agent_workload":           "workload",
    "get_cashflow_forecast":        "trend",
    "get_weekly_comparison":        "trend",
    "get_payment_anomalies":        "anomaly",
    "get_ministry_revenue":         "entity_compare",
    "get_daily_stats":              "revenue",
    # ── Admin Assistant (11 functions) ────────────────────────────────────────
    "get_agent_availability_snapshot": "agent_availability",
    "get_alerts_summary":              "anomaly",
    "get_agent_summary":               "agent_specific",
    "compare_entity_agents":           "entity_compare",
    "get_workload_distribution":       "workload",
    "get_inactive_agents":             "agent_availability",
    "get_sla_report":                  "sla",
    "analyze_performance_ranking":     "performance",
    "detect_anomalies":                "anomaly",
    "analyze_entity_balance":          "entity_compare",
    "get_processing_trends":           "trend",
    # ── Supervisor (10 functions) ───────────────────────────────────────────
    "get_request_stats":        "revenue",           # request volume by status/workflow
    "get_request_pipeline":     "revenue",           # status funnel with amounts
    "get_request_sla":          "sla",               # processing times + overdue
    "get_request_rejections":   "performance",       # rejection rates by workflow
    "get_request_trends":       "trend",             # daily submission/completion
    "get_entity_agents":        "agent_availability",# agent list + workload
    "get_agent_ranking":        "performance",       # agent performance ranking
    "get_pending_detail":       "sla",               # pending requests detail
    "get_workflow_config":      "entity_compare",    # workflow docs/steps config
    "get_workflow_tariffs":     "revenue",           # tariff breakdown
}


# ──────────────────────────────────────────────────────────────────────────────
# Seed dataset (540+ examples, 45-55 per intent)
# Coverage: Treasury + Admin domains, ES/FR/EN, informal, typo-resilient
# ──────────────────────────────────────────────────────────────────────────────

_SEED_DATA: List[Tuple[str, str]] = [
    # AGENT_AVAILABILITY ──────────────────────────────────────────────────────
    ("¿Cuántos agentes están conectados ahora?", "agent_availability"),
    ("¿Qué agentes están disponibles en este momento?", "agent_availability"),
    ("Estado de presencia del equipo", "agent_availability"),
    ("¿Hay agentes activos ahora mismo?", "agent_availability"),
    ("¿Quién está en línea?", "agent_availability"),
    ("Disponibilidad actual del equipo de trabajo", "agent_availability"),
    ("¿Cuántos agentes están trabajando ahora?", "agent_availability"),
    ("¿Qué agentes han estado activos en la última hora?", "agent_availability"),
    ("Estado de conexión de los agentes hoy", "agent_availability"),
    ("¿Hay alguien disponible para asignar pagos?", "agent_availability"),
    ("¿Cuántos agentes están de baja hoy?", "agent_availability"),
    ("Agentes inactivos hoy en el sistema", "agent_availability"),
    ("¿Quién ha iniciado sesión hoy?", "agent_availability"),
    ("¿Cuántos agentes están de vacaciones esta semana?", "agent_availability"),
    ("Estado del equipo en tiempo real", "agent_availability"),
    ("Agents disponibles maintenant", "agent_availability"),
    ("How many agents are online right now?", "agent_availability"),
    ("¿Qué agentes no han trabajado hoy?", "agent_availability"),
    ("Presencia del equipo esta mañana", "agent_availability"),
    ("¿Hay agentes fuera de oficina?", "agent_availability"),
    ("¿Cuántos agentes están en misión actualmente?", "agent_availability"),
    ("Actividad reciente de los agentes del sistema", "agent_availability"),
    ("¿Están todos los agentes disponibles hoy?", "agent_availability"),
    ("Resumen de disponibilidad del equipo", "agent_availability"),
    ("¿Quién está de guardia hoy en tesorería?", "agent_availability"),
    # AGENT_SPECIFIC ──────────────────────────────────────────────────────────
    ("Información sobre el agente Juan García", "agent_specific"),
    ("¿Qué está haciendo María López ahora?", "agent_specific"),
    ("Historial de trabajo del agente Carlos", "agent_specific"),
    ("Detalles del perfil del agente responsable", "agent_specific"),
    ("¿Cuántos casos tiene asignados el agente Pedro?", "agent_specific"),
    ("Rendimiento individual del agente Martínez", "agent_specific"),
    ("¿Está disponible el agente Pérez?", "agent_specific"),
    ("Estadísticas del agente Juan esta semana", "agent_specific"),
    ("¿Cuál es la carga de trabajo del agente López?", "agent_specific"),
    ("Información detallada sobre el agente García", "agent_specific"),
    ("¿Qué validaciones ha hecho el agente María?", "agent_specific"),
    ("Estado actual del agente responsable de validación", "agent_specific"),
    ("Perfil y métricas del agente Martínez este mes", "agent_specific"),
    ("¿Cuándo fue la última actividad del agente Nguema?", "agent_specific"),
    ("¿Cuántos rechazos tiene el agente esta semana?", "agent_specific"),
    ("Historial de pagos procesados por el agente Juan", "agent_specific"),
    ("¿Ha cumplido el agente con su cuota mensual?", "agent_specific"),
    ("Detalles de actividad del agente López hoy", "agent_specific"),
    ("¿Qué tipo de pagos gestiona este agente específico?", "agent_specific"),
    ("Estadísticas mensuales del agente García", "agent_specific"),
    ("¿Es el agente María especialista en CNEDOGE?", "agent_specific"),
    ("Resume el desempeño del agente Ondó este mes", "agent_specific"),
    ("¿Cuánto tiempo trabaja el agente Nguema diariamente?", "agent_specific"),
    ("Informe individual sobre el agente Mbá", "agent_specific"),
    ("¿Qué ha procesado el agente específico hoy?", "agent_specific"),
    # WORKLOAD ────────────────────────────────────────────────────────────────
    ("¿Cómo está distribuida la carga de trabajo?", "workload"),
    ("¿Hay agentes sobrecargados en el equipo?", "workload"),
    ("Cola de pagos pendientes por agente", "workload"),
    ("Distribución de tareas entre los agentes", "workload"),
    ("¿Qué agente tiene más pagos en cola?", "workload"),
    ("Balance de carga de trabajo del equipo", "workload"),
    ("¿Hay desequilibrios en la asignación de trabajo?", "workload"),
    ("Capacidad disponible por agente hoy", "workload"),
    ("¿Cuántos pagos tiene cada agente pendientes?", "workload"),
    ("Resumen de carga del equipo para hoy", "workload"),
    ("¿Quién está libre para tomar más casos?", "workload"),
    ("Distribución de asignaciones entre entidades", "workload"),
    ("¿Hay agentes con demasiado trabajo acumulado?", "workload"),
    ("Carga actual del sistema de tesorería", "workload"),
    ("¿Cómo se distribuyen los pagos entre las entidades?", "workload"),
    ("Répartition de la charge de travail", "workload"),
    ("Workload distribution across agents today", "workload"),
    ("¿Cuántos casos activos tiene cada agente?", "workload"),
    ("¿Hay agentes en disponibilidad sin casos asignados?", "workload"),
    ("Asignaciones pendientes por proceso de validación", "workload"),
    ("¿La carga está bien distribuida entre el equipo?", "workload"),
    ("Pagos sin asignar a ningún agente", "workload"),
    ("¿Cuántos agentes están ocupados ahora mismo?", "workload"),
    ("Nivel de ocupación por departamento ministerial", "workload"),
    ("Capacidad de procesamiento disponible en el sistema", "workload"),
    ("Workload de los agentes del departamento", "workload"),
    ("¿Cuánta carga tienen los agentes de tesorería?", "workload"),
    ("Agentes más ocupados y menos ocupados hoy", "workload"),
    ("¿Qué agentes están más saturados de trabajo?", "workload"),
    ("Volumen de trabajo por agente esta semana", "workload"),
    # SLA ─────────────────────────────────────────────────────────────────────
    ("¿Hay pagos vencidos en el sistema?", "sla"),
    ("Alertas SLA activas en este momento", "sla"),
    ("¿Qué pagos están en riesgo de incumplir el SLA?", "sla"),
    ("Pagos pendientes con fecha límite próxima", "sla"),
    ("¿Cuántos pagos han superado las 48 horas?", "sla"),
    ("Estado de cumplimiento de plazos de validación", "sla"),
    ("Reporte de SLA de esta semana por agente", "sla"),
    ("¿Hay pagos críticos que requieren atención urgente?", "sla"),
    ("Pagos con SLA vencido esta semana", "sla"),
    ("¿Cuánto tiempo llevan esperando los pagos pendientes?", "sla"),
    ("Alertas de tesorería urgentes pendientes", "sla"),
    ("Pagos que necesitan revisión urgente por SLA", "sla"),
    ("¿Cuántos pagos llevan más de 5 días sin atender?", "sla"),
    ("Estado de los plazos de validación por agente", "sla"),
    ("¿Qué pagos están a punto de caducar mañana?", "sla"),
    ("Délais de paiement dépassés cette semaine", "sla"),
    ("Overdue payments requiring immediate attention", "sla"),
    ("SLA compliance report for this week", "sla"),
    ("¿Cuántos agentes tienen pagos atrasados?", "sla"),
    ("Pagos bloqueados sin procesar más de 48 horas", "sla"),
    ("¿Hay pagos en riesgo crítico esta semana?", "sla"),
    ("Dame las alertas de plazo por agente", "sla"),
    ("Tiempo promedio de resolución de pagos pendientes", "sla"),
    ("¿Hay incumplimientos de SLA esta semana?", "sla"),
    ("Pagos pendientes con más de 48 horas sin gestión", "sla"),
    # PERFORMANCE ─────────────────────────────────────────────────────────────
    ("¿Cuál es el rendimiento de los agentes de tesorería?", "performance"),
    ("Tasa de aprobación por agente este mes", "performance"),
    ("¿Quién tiene más rechazos en el equipo?", "performance"),
    ("Métricas de productividad del equipo de validación", "performance"),
    ("Tiempo promedio de validación por agente", "performance"),
    ("¿Qué agentes tienen mejor rendimiento este mes?", "performance"),
    ("Ranking de agentes por pagos procesados esta semana", "performance"),
    ("Eficiencia del equipo de tesorería este mes", "performance"),
    ("¿Cuántas validaciones ha hecho cada agente esta semana?", "performance"),
    ("Análisis de rechazos por agente y motivo", "performance"),
    ("Performance del equipo comparado al mes anterior", "performance"),
    ("¿Qué agente tiene la tasa de rechazo más alta?", "performance"),
    ("Comparativa de productividad entre agentes", "performance"),
    ("KPIs del equipo de agentes de tesorería", "performance"),
    ("¿Cuál es el tiempo promedio de revisión de pagos?", "performance"),
    ("Performance des agents ce mois-ci", "performance"),
    ("Agent performance metrics and efficiency rankings", "performance"),
    ("¿Quién ha aprobado más pagos hoy?", "performance"),
    ("Tasa de cumplimiento SLA por agente individual", "performance"),
    ("Estadísticas de trabajo y eficiencia de los agentes", "performance"),
    ("¿Hay agentes con bajo rendimiento sostenido?", "performance"),
    ("Dashboard de productividad del equipo completo", "performance"),
    ("Velocidad de procesamiento por agente esta semana", "performance"),
    ("¿Cuántos pagos ha rechazado cada agente?", "performance"),
    ("Índice de eficiencia del equipo de validación", "performance"),
    ("Ranking de rendimiento de los agentes", "performance"),
    ("Agentes más eficientes del departamento", "performance"),
    ("¿Qué agentes tienen mejor productividad?", "performance"),
    ("Evaluación de rendimiento por agente este mes", "performance"),
    ("Los agentes con menor tasa de éxito", "performance"),
    # ANOMALY ─────────────────────────────────────────────────────────────────
    ("¿Hay anomalías en los pagos hoy?", "anomaly"),
    ("Detecta patrones inusuales en los datos del sistema", "anomaly"),
    ("¿Hay pagos sospechosos o irregulares?", "anomaly"),
    ("Análisis de irregularidades en tesorería", "anomaly"),
    ("¿Hay algo raro en los datos de hoy?", "anomaly"),
    ("Alertas de fraude o inconsistencias detectadas", "anomaly"),
    ("¿Hay transacciones fuera de lo normal?", "anomaly"),
    ("Detección de anomalías en pagos de tesorería", "anomaly"),
    ("¿Qué es anormal en los datos actuales del sistema?", "anomaly"),
    ("Patrones inusuales detectados en los últimos días", "anomaly"),
    ("¿Hay agentes con comportamiento estadísticamente atípico?", "anomaly"),
    ("Inconsistencias en los pagos detectadas hoy", "anomaly"),
    ("¿Hay pagos duplicados o sospechosos en el sistema?", "anomaly"),
    ("Análisis de riesgo de fraude en pagos recibidos", "anomaly"),
    ("¿Hay outliers en los montos de pago recibidos?", "anomaly"),
    ("Anomalies détectées dans le système aujourd'hui", "anomaly"),
    ("Any suspicious or unusual payment patterns detected?", "anomaly"),
    ("¿Hay cargos inusuales o incorrectos?", "anomaly"),
    ("Alertas de calidad de datos en el sistema", "anomaly"),
    ("¿Se han detectado irregularidades esta semana?", "anomaly"),
    ("Pagos con importes atípicamente altos o bajos", "anomaly"),
    ("¿Hay rechazos masivos repentinos sin causa clara?", "anomaly"),
    ("Análisis de comportamiento anómalo en agentes", "anomaly"),
    ("Actividad sospechosa detectada en el sistema", "anomaly"),
    ("¿Hay operaciones fuera del patrón habitual?", "anomaly"),
    # TREND ───────────────────────────────────────────────────────────────────
    ("¿Cuál es la tendencia de ingresos este mes?", "trend"),
    ("Evolución de pagos en las últimas semanas", "trend"),
    ("¿Están subiendo o bajando los ingresos?", "trend"),
    ("Tendencia histórica de recaudación este año", "trend"),
    ("¿Cómo han evolucionado los cobros este trimestre?", "trend"),
    ("Comparativa de ingresos semana a semana", "trend"),
    ("¿Hay una tendencia al alza o a la baja?", "trend"),
    ("Evolución del volumen de pagos en el tiempo", "trend"),
    ("¿Cómo han cambiado los ingresos en el último mes?", "trend"),
    ("Proyección de ingresos para los próximos días", "trend"),
    ("Tendencia de la tasa de aprobación de pagos", "trend"),
    ("¿Ha mejorado el rendimiento respecto al mes anterior?", "trend"),
    ("Comparativa trimestral de ingresos por entidad", "trend"),
    ("¿Cuál es el pronóstico de recaudación para esta semana?", "trend"),
    ("Tendencia de pagos móviles vs transferencias bancarias", "trend"),
    ("Tendance des revenus ce mois-ci", "trend"),
    ("What is the revenue trend this week?", "trend"),
    ("¿Cómo ha variado el volumen de pagos este trimestre?", "trend"),
    ("Análisis de estacionalidad en los pagos del año", "trend"),
    ("¿Hay variaciones inusuales en los últimos días?", "trend"),
    ("Previsión de ingresos para la próxima semana", "trend"),
    ("¿Cuál ha sido el crecimiento respecto al año pasado?", "trend"),
    ("Evolución de pagos procesados por hora del día", "trend"),
    ("¿La recaudación ha aumentado este mes?", "trend"),
    ("Forecast de cobros para esta semana", "trend"),
    # REVENUE ─────────────────────────────────────────────────────────────────
    ("¿Cuánto hemos recaudado hoy?", "revenue"),
    ("Total de ingresos del mes en curso", "revenue"),
    ("Dame el resumen de cobros de los últimos 7 días", "revenue"),
    ("¿Cuál es el revenue de esta semana?", "revenue"),
    ("Total de pagos completados este mes", "revenue"),
    ("¿Cuántos pagos se han procesado hoy?", "revenue"),
    ("Resumen financiero de ingresos de tesorería", "revenue"),
    ("¿Cuánto dinero ha entrado esta semana?", "revenue"),
    ("Desglose de ingresos por método de pago", "revenue"),
    ("¿Qué servicios generan más ingresos?", "revenue"),
    ("Recaudación total del trimestre en FCFA", "revenue"),
    ("Balance de caja del día de hoy", "revenue"),
    ("Montante total recaudado este mes", "revenue"),
    ("¿Cuánto ha cobrado la tesorería hoy?", "revenue"),
    ("Total de transacciones completadas y aprobadas", "revenue"),
    ("Combien avons-nous encaissé ce mois?", "revenue"),
    ("What is the total revenue today?", "revenue"),
    ("Total ingresado en los últimos 30 días", "revenue"),
    ("Breakdown de servicios por volumen de recaudación", "revenue"),
    ("¿Cuál es el monto total de pagos aprobados?", "revenue"),
    ("Estadísticas de cobro de esta semana", "revenue"),
    ("Dame los ingresos por entidad ministerial", "revenue"),
    ("Resumen de tesorería diario completo", "revenue"),
    ("¿Cuántos pagos en efectivo se han recibido?", "revenue"),
    ("Total de transferencias bancarias recibidas hoy", "revenue"),
    # ENTITY_COMPARE ──────────────────────────────────────────────────────────
    ("¿Qué entidad genera más ingresos este mes?", "entity_compare"),
    ("Comparativa entre CNEDOGE y DGT", "entity_compare"),
    ("¿Cuál tiene mejor rendimiento por entidad?", "entity_compare"),
    ("Comparación de recaudación entre sedes ministeriales", "entity_compare"),
    ("¿Qué ministerio procesa más pagos?", "entity_compare"),
    ("Ranking de entidades por volumen de recaudación", "entity_compare"),
    ("¿Hay diferencias entre Malabo y Bata?", "entity_compare"),
    ("Distribución de ingresos por entidad ministerial", "entity_compare"),
    ("¿Qué sede tiene más pagos pendientes?", "entity_compare"),
    ("Comparativa de eficiencia entre entidades del sistema", "entity_compare"),
    ("¿Cuál es la entidad con más rechazos?", "entity_compare"),
    ("Desglose de cobros por ministerio", "entity_compare"),
    ("Comparativa de rendimiento entre oficinas", "entity_compare"),
    ("¿Hay diferencias significativas entre entidades?", "entity_compare"),
    ("¿Cuál es la contribución de cada entidad al total?", "entity_compare"),
    ("Comparaison entre entités ministérielles", "entity_compare"),
    ("Which entity has the highest revenue this month?", "entity_compare"),
    ("¿Cuál es la entidad más activa hoy?", "entity_compare"),
    ("Ranking de sedes por número de transacciones", "entity_compare"),
    ("¿CNEDOGE o Extranjería, cuál recauda más?", "entity_compare"),
    ("Distribución geográfica de ingresos por sede", "entity_compare"),
    ("Rendimiento comparativo entre delegaciones", "entity_compare"),
    ("¿Qué entidad tiene mejor tasa de aprobación?", "entity_compare"),
    ("Ingresos por ministerio este mes comparado", "entity_compare"),
    ("¿Cuál es la entidad más eficiente del sistema?", "entity_compare"),
    ("Comparar rendimiento de agentes por entidad", "entity_compare"),
    ("¿Qué entidad tiene agentes más productivos?", "entity_compare"),
    ("Diferencias de rendimiento entre CNEDOGE y Extranjería", "entity_compare"),
    # RECONCILIATION ──────────────────────────────────────────────────────────
    ("¿Hay pagos sin reconciliar?", "reconciliation"),
    ("Estado de la reconciliación bancaria", "reconciliation"),
    ("¿Cuántos pagos no están en el sistema bancario?", "reconciliation"),
    ("Diferencias entre banco y tesorería", "reconciliation"),
    ("Pagos recibidos pero no registrados en sistema", "reconciliation"),
    ("Estado de matching de transacciones bancarias", "reconciliation"),
    ("¿Hay discrepancias en los registros de pagos?", "reconciliation"),
    ("Reconciliación de cuentas pendiente este mes", "reconciliation"),
    ("¿Cuántos pagos están sin cuadrar?", "reconciliation"),
    ("Diferencias contables detectadas en tesorería", "reconciliation"),
    ("Pagos en duda o sin confirmar por el banco", "reconciliation"),
    ("¿Hay transacciones bancarias no emparejadas?", "reconciliation"),
    ("Estado de la conciliación bancaria del mes", "reconciliation"),
    ("Movimientos bancarios no reconciliados con tesorería", "reconciliation"),
    ("¿Hay pagos duplicados en el sistema bancario?", "reconciliation"),
    ("Réconciliation bancaire en attente ce mois-ci", "reconciliation"),
    ("Unreconciled bank payments status this week", "reconciliation"),
    ("¿Cuántos pagos mobile money no han cuadrado?", "reconciliation"),
    ("Diferencias entre registro bancario y tesorería", "reconciliation"),
    ("¿Hay errores de matching entre pagos bancarios?", "reconciliation"),
    ("Pagos sin confirmar del banco BANGE", "reconciliation"),
    ("¿Cuántas transacciones están en disputa?", "reconciliation"),
    ("Estado de reconciliación BANGE esta semana", "reconciliation"),
    ("¿Hay cobros sin entrada contable correspondiente?", "reconciliation"),
    ("Resumen de reconciliación semanal de cuentas", "reconciliation"),
    # GENERAL ─────────────────────────────────────────────────────────────────
    ("Hola", "general"),
    ("¿Qué puedes hacer?", "general"),
    ("Ayúdame con algo por favor", "general"),
    ("¿Cuál es tu función en el sistema?", "general"),
    ("Información general del sistema de tesorería", "general"),
    ("¿Cómo funciona la tesorería?", "general"),
    ("¿Qué datos tienes disponibles?", "general"),
    ("Explícame el proceso de pago detallado", "general"),
    ("¿Qué es el SLA en este contexto?", "general"),
    ("Dame una visión general de todo el sistema", "general"),
    ("¿Hay algún problema en el sistema?", "general"),
    ("¿Todo está funcionando bien hoy?", "general"),
    ("Resumen general del estado del sistema", "general"),
    ("¿Qué necesito saber hoy?", "general"),
    ("Información importante del día de trabajo", "general"),
    ("Bonjour, comment ça va?", "general"),
    ("Hello, what can you help me with today?", "general"),
    ("¿Cuál es tu nombre?", "general"),
    ("¿Puedes hacer un análisis completo de todo?", "general"),
    ("Dame todo lo que tienes disponible hoy", "general"),
    ("¿Hay algo importante que revisar hoy?", "general"),
    ("¿Qué recomiendas revisar primero?", "general"),
    ("Informe completo del día de trabajo", "general"),
    ("¿Cómo van las cosas en general hoy?", "general"),
    ("Muéstrame el dashboard completo", "general"),
    # ════════════════════════════════════════════════════════════════════════════
    # Extended seed data — Treasury/Financial Analyst domain + informal phrasing
    # ════════════════════════════════════════════════════════════════════════════
    # AGENT_AVAILABILITY (extended) ───────────────────────────────────────────
    ("¿Cuántos funcionarios están activos en el turno?", "agent_availability"),
    ("Lista de agentes conectados en tesorería", "agent_availability"),
    ("¿Cuántos validadores hay disponibles ahora?", "agent_availability"),
    ("¿Quiénes están procesando pagos en este momento?", "agent_availability"),
    ("Disponibilidad del equipo de validación de pagos", "agent_availability"),
    ("¿Tenemos suficientes agentes para la carga actual?", "agent_availability"),
    ("¿Qué agentes están de baja por enfermedad?", "agent_availability"),
    ("¿Hay cobertura suficiente de agentes hoy?", "agent_availability"),
    ("Who is currently processing payments?", "agent_availability"),
    ("Disponibilité de l'équipe de trésorerie", "agent_availability"),
    # AGENT_SPECIFIC (extended) ───────────────────────────────────────────────
    ("Rendimiento de Nguema este trimestre", "agent_specific"),
    ("¿Cuántos pagos ha procesado María hoy?", "agent_specific"),
    ("Historial de rechazos del agente Ondó", "agent_specific"),
    ("¿Cuál es la eficiencia del agente Pedro esta semana?", "agent_specific"),
    ("Métricas individuales del agente de CNEDOGE", "agent_specific"),
    ("¿Ha mejorado el agente López respecto al mes pasado?", "agent_specific"),
    ("Tiempo promedio de validación del agente Martínez", "agent_specific"),
    ("¿Cuántos SLA ha incumplido el agente García?", "agent_specific"),
    ("Performance of agent Juan this week", "agent_specific"),
    ("Statistiques de l'agent Nguema ce mois-ci", "agent_specific"),
    # WORKLOAD (extended) ─────────────────────────────────────────────────────
    ("¿Cuántos expedientes tiene cada agente sin resolver?", "workload"),
    ("Número de pagos en cola por agente de tesorería", "workload"),
    ("¿Hay agentes con workload excesivo?", "workload"),
    ("Distribución del trabajo entre los validadores", "workload"),
    ("¿Quién puede tomar más pagos ahora?", "workload"),
    ("Nivel de saturación del equipo de tesorería", "workload"),
    ("¿Están los agentes equilibrados en carga?", "workload"),
    ("Agentes sobrecargados versus agentes libres", "workload"),
    ("¿Hay expedientes sin asignar a ningún agente?", "workload"),
    ("Distribution de la charge entre les agents", "workload"),
    ("Agent workload balance for today", "workload"),
    ("Pagos acumulados sin procesar por agente", "workload"),
    ("¿Cuántos pagos tiene cada agente en su cola?", "workload"),
    ("Tareas pendientes por validador este turno", "workload"),
    ("Equilibrio de la distribución de trabajo actual", "workload"),
    # SLA (extended) ──────────────────────────────────────────────────────────
    ("Pagos que van a vencer en las próximas horas", "sla"),
    ("¿Cuántos pagos están próximos a expirar?", "sla"),
    ("Alertas de tiempo límite de validación", "sla"),
    ("¿Hay pagos en riesgo de superar las 48 horas?", "sla"),
    ("Estado de cumplimiento de plazos hoy", "sla"),
    ("Pagos con deadline esta tarde", "sla"),
    ("¿Qué pagos necesitan atención urgente por plazo?", "sla"),
    ("Reporte de incumplimientos de SLA esta semana", "sla"),
    ("¿Cuántos pagos han caducado sin ser procesados?", "sla"),
    ("Pagos expirados que requieren escalación", "sla"),
    ("Délais dépassés pour les paiements en cours", "sla"),
    ("Payment SLA violations this week", "sla"),
    ("¿Cuántos pagos llevan más de 24 horas pendientes?", "sla"),
    ("Pagos con plazo vencido por entidad", "sla"),
    ("Tiempo restante para los pagos más urgentes", "sla"),
    # PERFORMANCE (extended) ──────────────────────────────────────────────────
    ("¿Quién aprueba más pagos por hora?", "performance"),
    ("Tasa de éxito del equipo de tesorería", "performance"),
    ("¿Cuál es el agente más rápido validando?", "performance"),
    ("Comparativa de productividad mensual de agentes", "performance"),
    ("KPIs de rendimiento del equipo de validación", "performance"),
    ("¿Cuál es la tasa de rechazo global?", "performance"),
    ("Tiempo medio de resolución de pagos este mes", "performance"),
    ("¿Hay agentes con rendimiento por debajo del estándar?", "performance"),
    ("Ranking semanal de agentes por volumen procesado", "performance"),
    ("Métricas de calidad del equipo de tesorería", "performance"),
    ("¿Quién ha mejorado más respecto al mes pasado?", "performance"),
    ("Eficiencia operativa del departamento de pagos", "performance"),
    ("¿Cuál es la media de pagos procesados por agente?", "performance"),
    ("Análisis de productividad del equipo esta semana", "performance"),
    ("Classement des agents par performance ce mois", "performance"),
    ("Top performing agents this month", "performance"),
    # ANOMALY (extended) ──────────────────────────────────────────────────────
    ("¿Se ha detectado algo extraño en los pagos de hoy?", "anomaly"),
    ("Montos inusualmente altos registrados hoy", "anomaly"),
    ("¿Hay pagos fuera del rango normal?", "anomaly"),
    ("Detección de fraude potencial en el sistema", "anomaly"),
    ("¿Hay actividad sospechosa en las transacciones?", "anomaly"),
    ("Pagos con importes atípicos respecto a la media", "anomaly"),
    ("¿Se detectan irregularidades en los rechazos?", "anomaly"),
    ("Comportamiento anómalo en las transacciones de hoy", "anomaly"),
    ("¿Hay patrones de rechazo inusuales?", "anomaly"),
    ("Análisis de outliers en pagos recibidos", "anomaly"),
    ("Suspicious payment patterns detected today?", "anomaly"),
    ("Détection d'anomalies dans les paiements du jour", "anomaly"),
    ("¿Se han detectado montos duplicados o sospechosos?", "anomaly"),
    ("Alertas de comportamiento anormal en agentes", "anomaly"),
    ("¿Hay algo fuera de lo común en los datos financieros?", "anomaly"),
    # TREND (extended) ────────────────────────────────────────────────────────
    ("¿Han aumentado los ingresos esta semana?", "trend"),
    ("Evolución de pagos procesados por día", "trend"),
    ("Comparativa de recaudación mes a mes", "trend"),
    ("¿Cuál es la proyección de cobros para mañana?", "trend"),
    ("Gráfico de evolución de ingresos diarios", "trend"),
    ("¿La recaudación va al alza o a la baja?", "trend"),
    ("Análisis de estacionalidad de pagos", "trend"),
    ("¿Cómo ha cambiado el volumen de transacciones?", "trend"),
    ("Previsión de ingresos basada en datos históricos", "trend"),
    ("¿Hay un patrón cíclico en los pagos?", "trend"),
    ("Revenue trend analysis for this quarter", "trend"),
    ("Tendance des recettes ce trimestre", "trend"),
    ("Evolución semanal de la tasa de aprobación", "trend"),
    ("¿Va mejor o peor que la semana pasada?", "trend"),
    ("Proyección de recaudación para cierre de mes", "trend"),
    # REVENUE (extended) ──────────────────────────────────────────────────────
    ("¿Cuánta plata ha entrado hoy?", "revenue"),
    ("Total cobrado esta semana en todas las entidades", "revenue"),
    ("Desglose de cobros por tipo de servicio", "revenue"),
    ("¿Cuántos FCFA se han recaudado este mes?", "revenue"),
    ("Total de pagos aprobados y completados hoy", "revenue"),
    ("Resumen de caja del día", "revenue"),
    ("¿Cuánto dinero entró por mobile money hoy?", "revenue"),
    ("Total de transferencias bancarias completadas", "revenue"),
    ("Monto total de servicios de pasaporte cobrados", "revenue"),
    ("¿Cuánto se ha cobrado por servicios de residencia?", "revenue"),
    ("Daily revenue breakdown by payment method", "revenue"),
    ("Recettes totales de la journée par méthode de paiement", "revenue"),
    ("Total recaudado por entidad ministerial hoy", "revenue"),
    ("¿Cuáles son los servicios que más ingresos generan?", "revenue"),
    ("Balance financiero del día de tesorería", "revenue"),
    # ENTITY_COMPARE (extended) ───────────────────────────────────────────────
    ("¿CNEDOGE recauda más que DGT?", "entity_compare"),
    ("Comparativa de pagos entre Malabo y Bata", "entity_compare"),
    ("¿Qué ministerio tiene mejor rendimiento de agentes?", "entity_compare"),
    ("Ranking de entidades por volumen de cobros", "entity_compare"),
    ("¿Hay diferencias significativas entre sedes?", "entity_compare"),
    ("Comparación de eficiencia entre departamentos", "entity_compare"),
    ("¿Cuál entidad procesa pagos más rápido?", "entity_compare"),
    ("Rendimiento comparativo entre entidades este mes", "entity_compare"),
    ("¿Qué sede tiene peor tasa de rechazo?", "entity_compare"),
    ("Distribución de ingresos por ministerio y sede", "entity_compare"),
    ("Which entity has the best approval rate?", "entity_compare"),
    ("Comparaison des performances entre entités", "entity_compare"),
    ("¿La Extranjería procesa más que CNEDOGE?", "entity_compare"),
    ("Análisis comparativo de carga entre sedes", "entity_compare"),
    ("¿Qué entidad necesita más recursos?", "entity_compare"),
    # RECONCILIATION (extended) ───────────────────────────────────────────────
    ("¿Cuántos pagos BANGE no han cuadrado?", "reconciliation"),
    ("Estado de conciliación de transferencias bancarias", "reconciliation"),
    ("Pagos registrados en sistema pero no en banco", "reconciliation"),
    ("¿Hay diferencias contables pendientes de resolver?", "reconciliation"),
    ("Movimientos bancarios sin emparejar esta semana", "reconciliation"),
    ("Estado de matching de pagos con BANGE", "reconciliation"),
    ("¿Cuántas discrepancias hay entre banco y sistema?", "reconciliation"),
    ("Pagos de mobile money sin confirmar por banco", "reconciliation"),
    ("¿Hay pagos duplicados entre nuestro sistema y el banco?", "reconciliation"),
    ("Reporte de conciliación semanal BANGE", "reconciliation"),
    ("Bank reconciliation report for this week", "reconciliation"),
    ("Rapprochement bancaire en attente", "reconciliation"),
    ("Pagos completados en sistema pero no confirmados", "reconciliation"),
    ("¿Cuántos pagos están en disputa con el banco?", "reconciliation"),
    ("Estado general de reconciliación de todas las cuentas", "reconciliation"),
    # GENERAL (extended) ──────────────────────────────────────────────────────
    ("Buenos días", "general"),
    ("Gracias por la información", "general"),
    ("Ok entendido", "general"),
    ("¿Cómo te llamas?", "general"),
    ("¿Eres una inteligencia artificial?", "general"),
    ("¿Qué tipo de análisis puedes hacer?", "general"),
    ("Dame un resumen ejecutivo", "general"),
    ("¿Cuál es la situación general?", "general"),
    ("Enséñame lo más importante del día", "general"),
    ("¿Qué ha pasado hoy?", "general"),
    ("Good morning, what's the situation?", "general"),
    ("Bonjour, quel est l'état du système?", "general"),
    ("¿Hay alertas o problemas que revisar?", "general"),
    ("Dame el panorama completo", "general"),
    ("¿Qué debo priorizar hoy?", "general"),
    # ════════════════════════════════════════════════════════════════════════════
    # Admin Agent domain — agent management, HR, permissions, entity operations
    # Vocabulary distinct from treasury: "asignar", "suspender", "permisos",
    # "roles", "entidad", "turno", "baja", "formación"
    # ════════════════════════════════════════════════════════════════════════════
    # AGENT_AVAILABILITY (admin context) ──────────────────────────────────────
    ("¿Cuántos funcionarios están en su puesto hoy?", "agent_availability"),
    ("Presencia del personal administrativo ahora", "agent_availability"),
    ("¿Hay supervisores conectados al sistema?", "agent_availability"),
    ("¿Qué personal está de turno esta mañana?", "agent_availability"),
    ("¿Cuántos agentes han fichado hoy?", "agent_availability"),
    ("¿Hay personal suficiente cubriendo el turno?", "agent_availability"),
    ("Listado de personal activo en cada entidad ahora", "agent_availability"),
    ("¿Cuántos funcionarios están de formación hoy?", "agent_availability"),
    ("Personal ausente sin justificación esta semana", "agent_availability"),
    ("¿Hay entidades sin cobertura de agentes ahora?", "agent_availability"),
    # AGENT_SPECIFIC (admin context) ──────────────────────────────────────────
    ("Perfil completo del funcionario Nguema Obiang", "agent_specific"),
    ("¿Cuántas solicitudes ha procesado el agente de CNEDOGE?", "agent_specific"),
    ("Historial de asignaciones del agente Mbá", "agent_specific"),
    ("¿El agente Ondó tiene permisos de supervisor?", "agent_specific"),
    ("Evaluación completa del funcionario García este trimestre", "agent_specific"),
    ("¿A qué entidad está asignado el agente Pedro?", "agent_specific"),
    ("Últimas acciones del agente López en el sistema", "agent_specific"),
    ("¿El agente Martínez ha cumplido sus objetivos mensuales?", "agent_specific"),
    ("Historial de ausencias del funcionario Nguema", "agent_specific"),
    ("¿Cuántos roles tiene asignados el agente García?", "agent_specific"),
    # WORKLOAD (admin context) ────────────────────────────────────────────────
    ("Distribución de solicitudes entre funcionarios", "workload"),
    ("¿Hay agentes con demasiadas solicitudes asignadas?", "workload"),
    ("Cola de expedientes por entidad y agente", "workload"),
    ("¿Cuántas solicitudes tiene cada agente de pasaportes?", "workload"),
    ("Nivel de ocupación del personal por departamento", "workload"),
    ("¿Hay agentes sin tareas asignadas actualmente?", "workload"),
    ("Distribución de expedientes entre las entidades", "workload"),
    ("¿La carga de expedientes está bien repartida?", "workload"),
    ("Agentes con más solicitudes acumuladas sin resolver", "workload"),
    ("Equilibrio de asignaciones entre supervisores", "workload"),
    # SLA (admin context) ─────────────────────────────────────────────────────
    ("¿Hay solicitudes que llevan más de 5 días sin respuesta?", "sla"),
    ("Expedientes de pasaporte con plazo vencido", "sla"),
    ("¿Cuántas solicitudes de residencia están atrasadas?", "sla"),
    ("Alertas de demora en expedientes de la entidad CNEDOGE", "sla"),
    ("¿Hay solicitudes críticas sin atender esta semana?", "sla"),
    ("Tiempo promedio de respuesta por tipo de solicitud", "sla"),
    ("Expedientes con deadline próximo en las próximas 24h", "sla"),
    ("¿Qué entidad tiene más solicitudes vencidas?", "sla"),
    ("Plazos de resolución incumplidos por departamento", "sla"),
    ("Solicitudes bloqueadas que necesitan escalación urgente", "sla"),
    # PERFORMANCE (admin context) ─────────────────────────────────────────────
    ("¿Quién procesa más solicitudes por día?", "performance"),
    ("Ranking de funcionarios por expedientes resueltos", "performance"),
    ("Tasa de rechazo de solicitudes por agente", "performance"),
    ("¿Qué agente tiene el mejor tiempo de respuesta?", "performance"),
    ("KPIs del equipo de gestión de pasaportes", "performance"),
    ("Eficiencia del personal de CNEDOGE este mes", "performance"),
    ("Métricas de calidad del equipo de residencia", "performance"),
    ("¿Hay funcionarios con rendimiento por debajo del mínimo?", "performance"),
    ("Productividad del equipo de extranjería esta semana", "performance"),
    ("¿Quién ha mejorado más en las últimas semanas?", "performance"),
    # ANOMALY (admin context) ─────────────────────────────────────────────────
    ("¿Hay agentes con comportamiento irregular?", "anomaly"),
    ("Patrones de rechazo inusuales en un agente", "anomaly"),
    ("¿Hay funcionarios que rechazan demasiadas solicitudes?", "anomaly"),
    ("Actividad sospechosa en el procesamiento de expedientes", "anomaly"),
    ("¿Se detectan anomalías en los tiempos de respuesta?", "anomaly"),
    ("Agentes con tasas de error significativamente altas", "anomaly"),
    ("¿Hay patrones inusuales en las asignaciones?", "anomaly"),
    ("Comportamiento atípico del personal este mes", "anomaly"),
    ("¿Hay solicitudes aprobadas sin la documentación completa?", "anomaly"),
    ("Anomalías en los horarios de conexión del personal", "anomaly"),
    # TREND (admin context) ───────────────────────────────────────────────────
    ("Evolución de solicitudes procesadas por semana", "trend"),
    ("¿Ha mejorado el tiempo de respuesta este mes?", "trend"),
    ("Tendencia de solicitudes de pasaporte este trimestre", "trend"),
    ("¿Están aumentando las solicitudes de residencia?", "trend"),
    ("Evolución del volumen de expedientes por entidad", "trend"),
    ("¿La tasa de aprobación ha cambiado este mes?", "trend"),
    ("Comparativa de solicitudes mes a mes por tipo", "trend"),
    ("Tendencia de carga de trabajo del equipo", "trend"),
    ("¿Cómo ha evolucionado el rendimiento del equipo?", "trend"),
    ("Proyección de solicitudes para la próxima semana", "trend"),
    # ENTITY_COMPARE (admin context) ──────────────────────────────────────────
    ("¿Qué entidad procesa más solicitudes de pasaporte?", "entity_compare"),
    ("Comparativa de rendimiento entre CNEDOGE y Extranjería", "entity_compare"),
    ("¿Cuál es la entidad más eficiente en gestión?", "entity_compare"),
    ("Ranking de departamentos por tiempo de resolución", "entity_compare"),
    ("¿La DGT procesa más rápido que CNEDOGE?", "entity_compare"),
    ("Diferencias en tasa de rechazo entre entidades", "entity_compare"),
    ("¿Qué sede tiene menos personal disponible?", "entity_compare"),
    ("Comparación del volumen de solicitudes Malabo vs Bata", "entity_compare"),
    ("¿Qué entidad necesita reforzar su equipo?", "entity_compare"),
    ("Análisis comparativo de calidad entre departamentos", "entity_compare"),
]


# ──────────────────────────────────────────────────────────────────────────────
# Intent Classifier
# ──────────────────────────────────────────────────────────────────────────────

class IntentClassifier:
    """
    TF-IDF (1,2-gram) + LogisticRegression intent classifier.

    - Trained from 500+ seed examples (35-45 × 11 intents) at module import.
    - Upgradeable at runtime: load_from_redis() pulls a retrained model
      produced by the weekly cron (Phase 3).
    - Thread-safe: uses threading.Lock for model swaps.
    - ~100ms to train from seeds; ~0.3ms per prediction.
    - Fallback: if sklearn unavailable, predict() returns GENERAL with 0.0.

    Confidence is max(predict_proba) — a real calibrated probability,
    not the fake regex-counting score from Level 2.
    """

    def __init__(self):
        self._pipeline: Optional[Any] = None
        self._classes: List[str] = []
        self._lock = threading.Lock()
        if _SKLEARN_AVAILABLE:
            self._train_from_seeds()

    def _train_from_seeds(self) -> None:
        """Train the classifier from the embedded seed dataset. Thread-safe."""
        with self._lock:
            if self._pipeline is not None:
                return
            try:
                texts  = [normalize_text(t) for t, _ in _SEED_DATA]
                labels = [l for _, l in _SEED_DATA]
                pipeline = Pipeline([
                    ("tfidf", TfidfVectorizer(
                        analyzer="word",
                        ngram_range=(1, 2),
                        max_features=8_000,
                        sublinear_tf=True,
                        strip_accents="unicode",
                        min_df=1,
                        token_pattern=r"(?u)\b\w+\b",   # single chars included (ñ, etc.)
                    )),
                    ("clf", LogisticRegression(
                        C=5.0,
                        max_iter=1_000,
                        solver="lbfgs",
                        class_weight="balanced",
                    )),
                ])
                pipeline.fit(texts, labels)
                self._pipeline = pipeline
                self._classes = list(pipeline.classes_)
                logger.info(
                    f"IntentClassifier trained: {len(texts)} samples, "
                    f"{len(self._classes)} intents, sklearn available"
                )
            except Exception as exc:
                logger.warning(f"IntentClassifier training failed (non-fatal): {exc}")

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """
        Predict intent for a question.

        Returns: (intent_value, confidence, probabilities)
          - intent_value : IntentCategory.value string
          - confidence   : max probability (calibrated, ∈ [0,1])
          - probabilities: full 11-class distribution {intent_value: prob}

        Falls back to ("general", 0.0, {}) if model unavailable.
        """
        if self._pipeline is None or not _SKLEARN_AVAILABLE:
            return "general", 0.0, {}
        try:
            normalized = normalize_text(text)
            proba     = self._pipeline.predict_proba([normalized])[0]
            best_idx  = int(proba.argmax())
            intent_v  = self._classes[best_idx]
            confidence = float(proba[best_idx])
            probs      = {cls: float(p) for cls, p in zip(self._classes, proba)}
            return intent_v, confidence, probs
        except Exception as exc:
            logger.warning(f"IntentClassifier.predict failed: {exc}")
            return "general", 0.0, {}

    def retrain(self, texts: List[str], labels: List[str]) -> Optional[Any]:
        """
        Retrain on new data (seed + real examples combined).
        Called by the weekly cron endpoint (Phase 3).
        Returns the trained Pipeline or None on failure.
        """
        if not _SKLEARN_AVAILABLE:
            return None
        try:
            seed_texts  = [normalize_text(t) for t, _ in _SEED_DATA]
            seed_labels = [l for _, l in _SEED_DATA]
            # Normalize real examples too (same pipeline as predict)
            norm_texts  = [normalize_text(t) for t in texts]
            # Real examples weighted 3× more than seeds
            all_texts  = seed_texts + norm_texts * 3
            all_labels = seed_labels + labels * 3

            pipeline = Pipeline([
                ("tfidf", TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    max_features=10_000,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    min_df=1,
                    token_pattern=r"(?u)\b\w+\b",
                )),
                ("clf", LogisticRegression(
                    C=2.0,
                    max_iter=1_000,
                    solver="lbfgs",
                    class_weight="balanced",
                )),
            ])
            pipeline.fit(all_texts, all_labels)
            with self._lock:
                self._pipeline = pipeline
                self._classes = list(pipeline.classes_)
            logger.info(
                f"IntentClassifier retrained: {len(all_texts)} samples "
                f"({len(texts)} real + {len(seed_texts)} seeds)"
            )
            return pipeline
        except Exception as exc:
            logger.error(f"IntentClassifier retrain failed: {exc}")
            return None

    async def load_from_redis(self) -> bool:
        """
        Try to upgrade to a better retrained model stored in Redis.
        Called by BaseAnalystService on first question (one-shot upgrade).
        Returns True if upgraded, False otherwise.
        """
        if not _SKLEARN_AVAILABLE:
            return False
        try:
            from app.core.cache import get_cache
            cache    = get_cache()
            model_b64 = await cache.get("nlp:intent_classifier:v1")
            if not model_b64 or not isinstance(model_b64, str):
                return False
            buf      = io.BytesIO(base64.b64decode(model_b64))
            pipeline = joblib.load(buf)
            with self._lock:
                self._pipeline = pipeline
                self._classes  = list(pipeline.classes_)
            logger.info("IntentClassifier upgraded to retrained model from Redis")
            return True
        except Exception as exc:
            logger.debug(f"IntentClassifier Redis upgrade skipped: {exc}")
            return False

    async def save_to_redis(self, pipeline) -> None:
        """Persist a retrained model to Redis (7-day TTL). Called after retrain cron."""
        if not _SKLEARN_AVAILABLE:
            return
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            buf   = io.BytesIO()
            joblib.dump(pipeline, buf)
            model_b64 = base64.b64encode(buf.getvalue()).decode()
            await cache.set("nlp:intent_classifier:v1", model_b64, ttl=7 * 24 * 3600)
            logger.info("IntentClassifier model persisted to Redis (7d TTL)")
        except Exception as exc:
            logger.warning(f"IntentClassifier Redis save failed: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# Module-level classifier singleton
# ──────────────────────────────────────────────────────────────────────────────

_intent_classifier = IntentClassifier()


# ──────────────────────────────────────────────────────────────────────────────
# NLP Preprocessor
# ──────────────────────────────────────────────────────────────────────────────

class NLPPreprocessor:
    """
    NLP pre-processor: user question → ExtractedSlots.

    Intent detection: ML classifier (sklearn TF-IDF + LR)
      → real calibrated probability; fallback to regex if sklearn unavailable
    Slot extraction: regex (deterministic, fast)
      → entity_codes, time_period_days, metric, agent_name, amount_threshold
    Confidence: max(predict_proba) — drives slot inheritance threshold
    """

    # Known entity codes — used for regex slot extraction only.
    # Keep this in sync with the `entities` table (or load dynamically from cache).
    ENTITY_CODES: frozenset = frozenset({
        "CNEDOGE", "CNEDOGE_PASAPORTE", "CNEDOGE_RESIDENCIA",
        "DGT", "ITVE", "ITV", "MINFP", "ONRC", "TESORO",
        "COMISARIA", "EXTRANJERIA", "POLICIA", "OFIVE",
    })

    # ── Fallback regex patterns (used when sklearn unavailable) ───────────────
    _FALLBACK_INTENT_PATTERNS: List[tuple] = [
        (IntentCategory.AGENT_AVAILABILITY, [
            r"cu[aá]ntos?\s+agentes?\s*(est[aá]n?|hay|trabajan?|conectados?|disponibles?|activos?)",
            r"\bagentes?\s+(conectados?|en\s+l[ií]nea|online|activos?\s+ahora|inactivos?\s+hoy)",
            r"qui[eé]n[es]?\s+(est[aá]n?|trabaja[n]?)\s*(ahora|hoy|en\s+este\s+momento)",
            r"\bdisponibilidad\s+actual\b|\bestado\s+de\s+presencia\b",
        ]),
        (IntentCategory.AGENT_SPECIFIC, [
            r"(?:agente|funcionario)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
            r"c[oó]mo\s+(?:está|va|lleva)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
            r"\bindividual\b.*\bagente\b|\bagente\b.*\bperfil\b",
        ]),
        (IntentCategory.RECONCILIATION, [
            r"\breconciliaci[oó]n\b|\bsin\s+(?:re)?conciliar\b",
            r"\btransacciones?\s+bancarias?\b|\bsin\s+cuadrar\b",
            r"\bdiscrepancias?\b|\bmatching\b|\bno\s+est[aá]n?\s+en\s+el\s+sistema\b",
        ]),
        (IntentCategory.SLA, [
            r"\bSLA\b|\b(vencidos?|en\s+riesgo|atrasados?|caducar?)\b",
            r"\bpagos?\s+(pendientes?|atrasados?)\b|\bincumplimiento\b|\bplazo[s]?\b",
            r"\boverdue\b|\bdeadline\b|\b48\s*(?:horas?|h)\b",
        ]),
        (IntentCategory.PERFORMANCE, [
            r"\branking\b|\btasa\s+de\s+(?:[eé]xito|rechazo|aprobaci[oó]n)\b",
            r"\bm[aá]s\s+(?:eficiente|productivo)\b|\bKPI[s]?\b|\bm[eé]trica[s]?\b",
            r"\bproductividad\b|\beficiencia\b|\brendimiento\b.*\bagente\b",
        ]),
        (IntentCategory.ANOMALY, [
            r"\banomal[ií]as?\b|\bpatrones?\s+inusuales?\b|\boutlier[s]?\b",
            r"\b(?:sospechoso|irregular|inusual|at[ií]pico)\b",
            r"\bdetect[a-z]+\s+(?:problemas?|patrones?|anomal[ií]as?)\b",
        ]),
        (IntentCategory.WORKLOAD, [
            r"\bcarga\s+de\s+trabajo\b|\bworkload\b|\bdistribuci[oó]n\s+de\s+(?:la\s+)?carga\b",
            r"\bsobrecargados?\b|\bdesequilibrio\b|\bcola\s+de\s+(?:pagos?|trabajo)\b",
        ]),
        (IntentCategory.TREND, [
            r"\btendencia\b|\bevoluci[oó]n\b|\bforecast\b|\bpron[oó]stico\b",
            r"\bal\s+alza\b|\ba\s+la\s+baja\b|\bsubiendo\b|\bbajando\b|\bcomparativa\s+\w+\s+a\s+\w+\b",
        ]),
        (IntentCategory.REVENUE, [
            r"\bingresos?\b|\brecaudaci[oó]n\b|\bfacturaci[oó]n\b|\bcobros?\b",
            r"\bmonto\s+total\b|\btotal\s+(?:cobrado|recaudado|ingresado)\b|\bbalance\s+de\s+caja\b",
        ]),
        (IntentCategory.ENTITY_COMPARE, [
            r"\bcomparar?\b|\bcomparativa\b|\bversus\b|\bvs\.?\s+",
            r"\bpor\s+entidad\b|\btodasl?\s+(?:las\s+)?entidades?\b|\bmejor\s+entidad\b",
            r"\bentre\s+\w+\s+y\s+\w+\b",  # "entre CNEDOGE y DGT"
        ]),
    ]

    # ── Time period patterns ──────────────────────────────────────────────────
    _TIME_PATTERNS: List[tuple] = [
        (r"\b(hoy|d[ií]a\s+de\s+hoy|este\s+d[ií]a|tiempo\s+real)\b",                 0),
        (r"\b(ayer)\b",                                                                 1),
        (r"\b(esta\s+semana|[úu]ltim[oa]s?\s+7\s+d[ií]as?)\b",                        7),
        (r"\b([úu]ltim[oa]s?\s+(\d+)\s+d[ií]as?)\b",                                  None),   # group 2 = N
        (r"\b([úu]ltim[oa]s?\s+(\d+)\s+semanas?)\b",                                  None),   # group 2 = N*7
        (r"\b(este\s+mes|[úu]ltim[oa]s?\s+30\s+d[ií]as?|mes\s+en\s+curso)\b",         30),
        (r"\b([úu]ltim[oa]s?\s+90\s+d[ií]as?|este\s+trimestre)\b",                    90),
        (r"\b(este\s+a[nñ]o|[úu]ltim[oa]s?\s+365\s+d[ií]as?)\b",                    365),
        (r"\b(hace\s+(\d+)\s+d[ií]as?)\b",                                             None),   # group 2 = N
        (r"\b(hace\s+una?\s+semana)\b",                                                 7),
        (r"\b(hace\s+un\s+mes)\b",                                                     30),
        (r"\b(en\s+tiempo\s+real|ahora\s+mismo|en\s+este\s+momento)\b",                0),
        # French
        (r"\b(aujourd['\u2019]?hui)\b",                                                 0),
        (r"\b(cette\s+semaine|7\s+derniers?\s+jours?)\b",                              7),
        (r"\b(ce\s+mois|30\s+derniers?\s+jours?)\b",                                  30),
        (r"\b(les?\s+(\d+)\s+derniers?\s+jours?)\b",                                   None),
    ]

    # ── Metric patterns ───────────────────────────────────────────────────────
    _METRIC_PATTERNS: List[tuple] = [
        ("success_rate",    [r"\btasa\s+de\s+[eé]xito\b", r"\btasa\s+de\s+aprobaci[oó]n\b", r"\bsuccess\b"]),
        ("quality",         [r"\bcalidad\b", r"\bquality\b"]),
        ("sla_compliance",  [r"\bcumplimiento\s+SLA\b", r"\bdeadline\b"]),
        ("productivity",    [r"\bproductividad\b", r"\bexpedientes?\s+procesados?\b", r"\bvolumen\b"]),
    ]

    # ── Stop words for agent name extraction ──────────────────────────────────
    _AGENT_NAME_STOPS: frozenset = frozenset({
        "los", "las", "agentes", "entidades", "pagos", "días", "datos",
        "rendimiento", "estadísticas", "información", "análisis",
    })

    # ── Public API ────────────────────────────────────────────────────────────

    def extract_slots(self, question: str) -> ExtractedSlots:
        """
        Extract structured slots from a natural language question.

        Intent: ML classifier (TF-IDF + LR) → real probability
        Other slots: regex (deterministic, fast)
        Confidence: max(predict_proba) from ML classifier
        """
        q_lower = question.lower()
        slots   = ExtractedSlots()

        # 1. Intent classification via ML classifier
        intent_val, confidence, probs = _intent_classifier.predict(question)

        if probs:
            # ML available — use real probabilities
            try:
                slots.intent               = IntentCategory(intent_val)
                slots.confidence           = confidence
                slots.intent_probabilities = probs
            except ValueError:
                slots.intent    = IntentCategory.GENERAL
                slots.confidence = 0.0
        else:
            # Fallback: regex scoring (sklearn unavailable)
            best_intent = IntentCategory.GENERAL
            best_score  = 0
            for intent_cat, patterns in self._FALLBACK_INTENT_PATTERNS:
                score = sum(
                    1 for p in patterns
                    if re.search(p, q_lower, re.IGNORECASE)
                )
                if score > best_score:
                    best_score  = score
                    best_intent = intent_cat
            slots.intent    = best_intent
            slots.confidence = min(0.4 + best_score * 0.15, 0.75) if best_score > 0 else 0.1

        # 2. Entity code extraction (case-insensitive, whole-word)
        for code in self.ENTITY_CODES:
            if re.search(rf"\b{re.escape(code)}\b", question, re.IGNORECASE):
                slots.entity_codes.append(code.upper())

        # 3. Time period extraction (first match wins)
        for pattern, value in self._TIME_PATTERNS:
            match = re.search(pattern, q_lower, re.IGNORECASE)
            if match:
                slots.raw_time_expr = match.group(0)
                if value is not None:
                    slots.time_period_days = value
                else:
                    try:
                        groups = match.groups()
                        n = next(int(g) for g in groups[1:] if g and g.isdigit())
                        if "semana" in pattern or "semaine" in pattern:
                            n *= 7
                        slots.time_period_days = n
                    except StopIteration:
                        slots.time_period_days = 7
                break

        # 4. Metric extraction
        for metric_key, patterns in self._METRIC_PATTERNS:
            if any(re.search(p, q_lower, re.IGNORECASE) for p in patterns):
                slots.metric = metric_key
                break

        # 5. Agent name extraction — heuristic: capitalized bigram after indicator
        for pattern in (
            r"(?:agente|funcionario)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
            r"(?:sobre|del\s+agente)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
            r"(?:c[oó]mo\s+(?:est[aá]|va|lleva))\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
        ):
            m = re.search(pattern, question, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                if candidate.lower() not in self._AGENT_NAME_STOPS and len(candidate) > 3:
                    slots.agent_name = candidate
                    break

        # 6. Amount threshold (ignore ≤ 100 — likely days/percentages)
        amount_match = re.search(
            r"(\d[\d\s,\.]*)\s*(XAF|FCFA|mil(?:es)?|mill?ones?)?",
            question, re.IGNORECASE,
        )
        if amount_match:
            try:
                raw    = amount_match.group(1).replace(" ", "").replace(",", "").replace(".", "")
                amount = float(raw)
                unit   = (amount_match.group(2) or "").lower()
                if "mil" in unit:
                    amount *= 1_000
                elif "millon" in unit or "million" in unit:
                    amount *= 1_000_000
                if amount > 100:
                    slots.amount_threshold = amount
            except (ValueError, AttributeError):
                pass

        # 7. keywords_matched: top matched TF-IDF terms (informational)
        if probs and slots.intent != IntentCategory.GENERAL:
            slots.keywords_matched = [slots.intent.value]

        return slots

    def build_enriched_prompt(
        self,
        question: str,
        slots: ExtractedSlots,
        memory_context: Optional[Dict[str, Any]] = None,
        few_shot_section: Optional[str] = None,
    ) -> str:
        """
        Build structured prompt: extracted context + few-shot + conversation context + question.

        Only includes context sections when confidence ≥ threshold to avoid
        confusing Gemini with low-confidence guesses.

        Args:
            few_shot_section: Pre-formatted few-shot examples string (from FewShotRetriever).
                              Injected between extracted context and conversation memory.
        """
        lines: List[str] = []

        # ── Extracted slots ───────────────────────────────────────────────────
        ctx: List[str] = []
        if slots.intent != IntentCategory.GENERAL:
            ctx.append(f"Intención detectada: {slots.intent.value} (confianza {slots.confidence:.0%})")
        if slots.entity_codes:
            ctx.append(f"Entidades mencionadas: {', '.join(slots.entity_codes)}")
        if slots.agent_name:
            ctx.append(f"Agente específico: {slots.agent_name}")
        if slots.time_period_days is not None:
            label = slots.raw_time_expr or f"últimos {slots.time_period_days} días"
            ctx.append(
                f"Período: {label} ({slots.time_period_days}d)"
                if slots.time_period_days > 0
                else "Período: tiempo real (ahora)"
            )
        if slots.metric:
            ctx.append(f"Métrica solicitada: {slots.metric}")

        if ctx and slots.confidence >= 0.3:
            lines.append("[CONTEXTO EXTRAÍDO]")
            lines.extend(f"- {c}" for c in ctx)
            lines.append("")

        # ── Few-shot examples (dynamic, from past successful queries) ─────────
        if few_shot_section:
            lines.append(few_shot_section)

        # ── Conversation memory ───────────────────────────────────────────────
        if memory_context:
            mem: List[str] = []
            if memory_context.get("entity_codes") and not slots.entity_codes:
                mem.append(f"Entidades del turno anterior: {', '.join(memory_context['entity_codes'])}")
            if memory_context.get("time_period_days") is not None and slots.time_period_days is None:
                mem.append(f"Período del turno anterior: {memory_context['time_period_days']} días")
            if memory_context.get("metric") and not slots.metric:
                mem.append(f"Métrica previa: {memory_context['metric']}")
            if memory_context.get("agent_name") and not slots.agent_name:
                mem.append(f"Agente previo: {memory_context['agent_name']}")
            if memory_context.get("key_findings"):
                mem.append(f"Hallazgo previo: {memory_context['key_findings'][:150]}")
            if mem:
                lines.append("[CONTEXTO CONVERSACIONAL]")
                lines.extend(f"- {m}" for m in mem)
                lines.append("")

        lines.append(f"PREGUNTA: {question}")
        return "\n".join(lines)

    def get_injected_kwargs(self, slots: ExtractedSlots) -> Dict[str, Any]:
        """
        Return kwargs to inject into SQL function calls (NLP-derived defaults).
        Only when confidence ≥ threshold — avoids false positive injection.
        Lowest precedence: entity_kwargs (auth) > fn_args (Gemini) > these.
        """
        kwargs: Dict[str, Any] = {}
        if slots.entity_codes and len(slots.entity_codes) == 1 and slots.confidence >= 0.4:
            kwargs["entity_code"] = slots.entity_codes[0]
        if slots.agent_name and slots.confidence >= 0.5:
            kwargs["agent_name"] = slots.agent_name
        if slots.time_period_days is not None and slots.confidence >= 0.35:
            kwargs["period_days"] = slots.time_period_days
            kwargs["days"]        = slots.time_period_days
        if slots.metric and slots.confidence >= 0.4:
            kwargs["metric"] = slots.metric
        return kwargs

    async def ensure_redis_upgrade(self) -> None:
        """
        One-shot Redis model upgrade. Call on first question per instance.
        No-op on all subsequent calls or if no better model in Redis.
        """
        await _intent_classifier.load_from_redis()


# ── Module-level singleton ────────────────────────────────────────────────────
nlp_preprocessor = NLPPreprocessor()
