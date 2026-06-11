"""
Dashboards service — business logic for the Looker Studio community connector.

Phase B.3 architecture: each dashboard owns a `DashboardConfig` describing
its schema, source table, optional date column, and how RLS applies. The
service is a thin orchestrator that:
1. Dispatches on `dashboard_id` to the right config.
2. Applies the RLS mode (entity / admin_only / public / agent_via_join).
3. Builds parameterised SQL with date + RLS filters.
4. Returns a `DashboardDataResponse` shaped for the Looker connector.

Dashboards live today:
  - recaudacion       (mv_treasury_daily_kpis, entity-RLS, daily)
  - agentes           (mv_agent_daily_workload, agent_via_join entity-RLS, daily)
  - services          (mv_services_translated, public catalog, no date)

Dashboards still on the roadmap:
  - adopcion          (needs new mv_adoption_daily — see Looker plan Phase 2)

The MVs are owned by `postgres` and refreshed by existing scheduler jobs;
see Memory rule #22 (don't depend on MVs as the single source of truth).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

import asyncpg
from loguru import logger

from app.modules.dashboards.models import (
    DashboardDataResponse,
    DashboardDataRow,
    DashboardSchemaResponse,
    LookerSchemaField,
    LookerSchemaSemantics,
)
from app.modules.dashboards.services.rls import (
    DashboardAccessContext,
    DashboardAccessDenied,
    build_access_filter,
)


class DashboardNotFoundError(Exception):
    """Raised when a dashboard_id has no implementation."""


# ---------------------------------------------------------------------------
# Schema definitions per dashboard
# ---------------------------------------------------------------------------


def _dim(name: str, label: str, semantic: Optional[str] = None) -> LookerSchemaField:
    return LookerSchemaField(
        name=name, label=label, dataType="STRING",
        semantics=LookerSchemaSemantics(conceptType="DIMENSION", semanticType=semantic),
    )


def _date_dim(name: str, label: str) -> LookerSchemaField:
    return _dim(name, label, semantic="YEAR_MONTH_DAY")


def _metric(name: str, label: str, semantic: Optional[str] = None) -> LookerSchemaField:
    return LookerSchemaField(
        name=name, label=label, dataType="NUMBER",
        semantics=LookerSchemaSemantics(conceptType="METRIC", semanticType=semantic),
    )


_SCHEMA_RECAUDACION: list[LookerSchemaField] = [
    _date_dim("report_date", "Date"),
    _dim("ministry_name", "Ministry"),
    _dim("entity_name", "Entity"),
    _dim("payment_method", "Method"),
    _dim("workflow_code", "Workflow"),
    _dim("service_name", "Service"),
    _metric("payment_count", "Payments"),
    _metric("completed_count", "Completed"),
    _metric("rejected_count", "Rejected"),
    _metric("total_amount", "Total recaudado", "CURRENCY_XAF"),
    _metric("avg_amount", "Avg payment", "CURRENCY_XAF"),
    _metric("avg_processing_minutes", "Avg processing (min)"),
    _metric("sla_breached_count", "SLA breached"),
]


_SCHEMA_AGENTES: list[LookerSchemaField] = [
    _date_dim("report_date", "Date"),
    _dim("agent_name", "Agent"),
    _metric("approved", "Approved"),
    _metric("rejected", "Rejected"),
    _metric("total_actions", "Total actions"),
    _metric("avg_duration_seconds", "Avg duration (s)"),
    _metric("p50_duration_seconds", "p50 duration (s)"),
]


_SCHEMA_SERVICES: list[LookerSchemaField] = [
    _dim("service_code", "Code"),
    _dim("name_es", "Nombre (ES)"),
    _dim("ministry_name_es", "Ministerio"),
    _dim("category_name_es", "Categoría"),
    _dim("status", "Status"),
    _dim("calculation_method", "Calculation"),
    _metric("view_count", "Views"),
    _metric("calculation_count", "Calculations"),
    _metric("tasa_expedicion", "Tasa expedición", "CURRENCY_XAF"),
    _metric("tasa_renovacion", "Tasa renovación", "CURRENCY_XAF"),
    _metric("processing_time_days", "Processing days"),
]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DashboardConfig:
    """How to fetch and protect one Looker-facing dashboard."""

    schema: list[LookerSchemaField]
    table: str
    date_column: Optional[str] = None
    # RLS modes (B.3):
    #   "entity"          → filter table.entity_code via build_access_filter
    #   "agent_via_join"  → filter via subquery on agent_profiles → entities.code
    #                       (used when MV has agent_profile_id but not entity_code)
    #   "admin_only"      → 403 unless access.is_staff
    #   "public"          → no filter, any authenticated user OK (e.g. catalog)
    rls_mode: str = "entity"
    # For agent_via_join: the column on `table` that joins to agent_profiles.id.
    rls_join_column: Optional[str] = None
    # Pre-computed list of column names (matches schema order). Cached so we
    # don't recompute on every request.
    columns: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        # Frozen dataclass → use object.__setattr__ to populate cached cols.
        if not self.columns:
            object.__setattr__(self, "columns", tuple(f.name for f in self.schema))


_DASHBOARD_REGISTRY: dict[str, DashboardConfig] = {
    "recaudacion": DashboardConfig(
        schema=_SCHEMA_RECAUDACION,
        table="mv_treasury_daily_kpis",
        date_column="report_date",
        rls_mode="entity",
    ),
    "agentes": DashboardConfig(
        schema=_SCHEMA_AGENTES,
        table="mv_agent_daily_workload",
        date_column="report_date",
        rls_mode="agent_via_join",
        rls_join_column="agent_profile_id",
    ),
    "services": DashboardConfig(
        schema=_SCHEMA_SERVICES,
        table="mv_services_translated",
        date_column=None,                # catalog, no time series
        rls_mode="public",
    ),
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DashboardsService:
    """Reads aggregated MVs and reshapes rows for the Looker connector."""

    def __init__(self, db_pool: asyncpg.Pool):
        self._pool = db_pool

    # -- Public API --------------------------------------------------------

    def list_dashboards(self) -> list[str]:
        return list(_DASHBOARD_REGISTRY.keys())

    def get_schema(self, dashboard_id: str) -> DashboardSchemaResponse:
        cfg = self._cfg(dashboard_id)
        return DashboardSchemaResponse(
            dashboard_id=dashboard_id,
            schema_version=1,
            fields=cfg.schema,   # serialised as JSON key 'schema' via alias
            refreshed_at=datetime.now(timezone.utc),
            notes=f"rls_mode={cfg.rls_mode}",
        )

    async def get_data(
        self,
        dashboard_id: str,
        *,
        access: DashboardAccessContext,
        fields: Optional[list[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> DashboardDataResponse:
        cfg = self._cfg(dashboard_id)

        # ---- 1. RLS gate before any SQL build ----------------------------
        self._enforce_rls_gate(cfg, access)

        # ---- 2. Column allowlist (anti-injection on `fields=`) -----------
        requested = fields or list(cfg.columns)
        allowed = [c for c in requested if c in cfg.columns]
        if not allowed:
            allowed = list(cfg.columns)

        # ---- 3. Build WHERE clauses --------------------------------------
        params: list[Any] = []
        wheres: list[str] = []
        filters_applied: list[str] = []

        if cfg.date_column:
            if start_date is not None:
                params.append(start_date)
                wheres.append(f"{cfg.date_column} >= ${len(params)}")
                filters_applied.append(f"start_date={start_date.isoformat()}")
            if end_date is not None:
                params.append(end_date)
                wheres.append(f"{cfg.date_column} <= ${len(params)}")
                filters_applied.append(f"end_date={end_date.isoformat()}")

        rls_clause, rls_params, rls_filter_label = self._build_rls_clause(
            cfg, access, next_param_index=len(params) + 1,
        )
        if rls_clause is not None:
            wheres.append(rls_clause)
            params.extend(rls_params)
        if rls_filter_label:
            filters_applied.append(rls_filter_label)

        # ---- 4. Assemble SQL ---------------------------------------------
        select_cols = ", ".join(allowed)
        sql = f"SELECT {select_cols} FROM {cfg.table}"
        if wheres:
            sql += " WHERE " + " AND ".join(wheres)
        if cfg.date_column:
            sql += f" ORDER BY {cfg.date_column} DESC"
        # 50K row hard cap — daily-aggregated MVs never come close.
        sql += " LIMIT 50000"

        # ---- 5. Execute --------------------------------------------------
        async with self._pool.acquire() as conn:
            try:
                records = await conn.fetch(sql, *params)
            except asyncpg.PostgresError as exc:
                logger.error(
                    "dashboards_service.get_data failed: dashboard={} err={}",
                    dashboard_id, exc,
                )
                raise

        rows = [
            DashboardDataRow(values=[record[c] for c in allowed])
            for record in records
        ]
        schema_fields = [f for f in cfg.schema if f.name in allowed]

        return DashboardDataResponse(
            dashboard_id=dashboard_id,
            fields=schema_fields,    # JSON key 'schema' via alias
            rows=rows,
            row_count=len(rows),
            filters_applied=filters_applied,
            refreshed_at=datetime.now(timezone.utc),
        )

    # -- Internals ---------------------------------------------------------

    def _cfg(self, dashboard_id: str) -> DashboardConfig:
        cfg = _DASHBOARD_REGISTRY.get(dashboard_id)
        if cfg is None:
            raise DashboardNotFoundError(
                f"Unknown dashboard_id '{dashboard_id}'. "
                f"Registered: {list(_DASHBOARD_REGISTRY.keys())}."
            )
        return cfg

    def _enforce_rls_gate(
        self, cfg: DashboardConfig, access: DashboardAccessContext
    ) -> None:
        """Raise DashboardAccessDenied if the user cannot read this dashboard
        in this RLS mode. Runs BEFORE any SQL is built — defense in depth.
        """
        if cfg.rls_mode == "public":
            return                       # any authenticated user OK
        if cfg.rls_mode == "admin_only":
            if not access.is_staff:
                raise DashboardAccessDenied(access)
            return
        # entity / agent_via_join — both require has_access (entity_codes set
        # OR is_staff). Forbidden = no agent profile + not admin.
        if not access.has_access:
            raise DashboardAccessDenied(access)

    def _build_rls_clause(
        self,
        cfg: DashboardConfig,
        access: DashboardAccessContext,
        *,
        next_param_index: int,
    ) -> tuple[Optional[str], list[Any], Optional[str]]:
        """Return (where_clause, params, filter_label) for the RLS step.

        - public         → (None, [], "rls=public:open")
        - admin_only     → (None, [], "rls=admin_only:bypass") (gate enforced earlier)
        - entity         → delegate to build_access_filter (label "rls=…")
        - agent_via_join → subquery against agent_profiles + entities
        """
        if cfg.rls_mode == "public":
            return None, [], "rls=public:open"

        if cfg.rls_mode == "admin_only":
            # Already gated; both staff and non-staff are filtered the same
            # way (no extra clause), but log the bypass for auditability.
            return None, [], "rls=admin_only:bypass"

        if cfg.rls_mode == "agent_via_join":
            # Staff bypass — show every row.
            if access.is_staff:
                return None, [], "rls=staff:bypass"
            if not access.entity_codes:
                # Should be unreachable because _enforce_rls_gate raised first.
                raise DashboardAccessDenied(access)
            join_col = cfg.rls_join_column or "agent_profile_id"
            clause = (
                f"{join_col} IN ("
                f"  SELECT ap.id FROM agent_profiles ap"
                f"  JOIN entities e ON e.id = ap.entity_id"
                f"  WHERE e.code = ANY(${next_param_index}::text[])"
                f"    AND ap.deactivated_at IS NULL"
                f")"
            )
            return clause, [list(access.entity_codes)], f"rls={access.describe()}"

        # Default: "entity" mode — filter on table.entity_code
        clause, params = build_access_filter(access, next_param_index=next_param_index)
        if clause is None:
            return None, [], "rls=staff:bypass"
        return clause, params, f"rls={access.describe()}"
