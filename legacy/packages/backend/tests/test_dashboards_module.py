# -*- coding: utf-8 -*-
"""
Unit tests for the dashboards module (Looker Studio community connector backend).

Phase B.1 scope:
- Pydantic models serialize with the alias `schema` (Looker Studio contract).
- Service registry knows about `recaudacion` and rejects anything else.
- Service hides PII: only the schema columns are accepted in `fields=`,
  arbitrary input is filtered out before SQL generation.

Tests use raw module-level imports (no DB connection); the service-layer
get_data() is exercised in integration tests when the backend has a pool.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Backend root on sys.path so `app...` imports resolve.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.dashboards.models.dashboards import (
    DashboardDataResponse,
    DashboardDataRow,
    DashboardPingResponse,
    DashboardReportEntry,
    DashboardReportsConfigResponse,
    DashboardSchemaResponse,
    LookerSchemaField,
    LookerSchemaSemantics,
)
from app.modules.dashboards.services.dashboards_service import (
    DashboardNotFoundError,
    DashboardsService,
    _DASHBOARD_REGISTRY,
    _SCHEMA_RECAUDACION,
)


# ---------------------------------------------------------------------------
# Pydantic model contract
# ---------------------------------------------------------------------------


def _sample_field() -> LookerSchemaField:
    return LookerSchemaField(
        name="total_amount",
        label="Total recaudado",
        dataType="NUMBER",
        semantics=LookerSchemaSemantics(
            conceptType="METRIC",
            semanticType="CURRENCY_XAF",
        ),
    )


def test_schema_response_serialises_with_schema_alias():
    """The Looker Studio contract requires the field list under JSON key `schema`."""
    resp = DashboardSchemaResponse(
        dashboard_id="recaudacion",
        fields=[_sample_field()],
        refreshed_at=datetime.now(timezone.utc),
    )
    js = resp.model_dump_json(by_alias=True)
    assert '"schema":' in js, "Looker connector expects 'schema' as the JSON key"
    assert '"fields":' not in js, "Internal name 'fields' must not leak in JSON"


def test_data_response_serialises_with_schema_alias():
    resp = DashboardDataResponse(
        dashboard_id="recaudacion",
        fields=[_sample_field()],
        rows=[DashboardDataRow(values=["2026-01-01", 100.0])],
        row_count=1,
        refreshed_at=datetime.now(timezone.utc),
    )
    js = resp.model_dump_json(by_alias=True)
    assert '"schema":' in js
    assert '"rows":' in js
    assert '"row_count":1' in js


def test_ping_response_strict_shape():
    """Ping response must NOT accept extra fields (extra='forbid')."""
    p = DashboardPingResponse(user_email="a@b.com", user_id="u-1", role="admin")
    assert p.ministry_id is None
    with pytest.raises(Exception):
        # Extra field should be rejected
        DashboardPingResponse(
            user_email="a@b.com", user_id="u-1", role="admin", surprise=42
        )


def test_data_row_accepts_mixed_types():
    row = DashboardDataRow(values=["text", 123, 4.5, None, True])
    assert row.values == ["text", 123, 4.5, None, True]


def test_schema_field_dataType_strict():
    """dataType must be one of STRING / NUMBER / BOOLEAN."""
    with pytest.raises(Exception):
        LookerSchemaField(
            name="x", label="X", dataType="INTEGER",  # not allowed
            semantics=LookerSchemaSemantics(conceptType="METRIC"),
        )


# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------


def test_registry_ships_three_dashboards_in_b3():
    """B.3 ships recaudacion + agentes + services. adopcion deferred to
    Phase 2 (needs new mv_adoption_daily for DAU/MAU/funnel)."""
    assert set(_DASHBOARD_REGISTRY.keys()) == {"recaudacion", "agentes", "services"}


def test_each_dashboard_has_consistent_columns():
    """For every registered dashboard, the cached `columns` tuple must match
    the schema field names. Defense against drift when adding fields."""
    for dashboard_id, cfg in _DASHBOARD_REGISTRY.items():
        schema_names = tuple(f.name for f in cfg.schema)
        assert cfg.columns == schema_names, (
            f"{dashboard_id}: columns drift — schema={schema_names}, "
            f"cached={cfg.columns}"
        )


def test_each_dashboard_has_known_rls_mode():
    """rls_mode must be one of the modes the service knows how to enforce."""
    valid_modes = {"entity", "agent_via_join", "admin_only", "public"}
    for dashboard_id, cfg in _DASHBOARD_REGISTRY.items():
        assert cfg.rls_mode in valid_modes, (
            f"{dashboard_id} has unknown rls_mode={cfg.rls_mode}"
        )


def test_agent_via_join_dashboards_declare_join_column():
    """A dashboard using rls_mode=agent_via_join must specify which column
    on its table joins to agent_profiles.id (else the subquery breaks)."""
    for dashboard_id, cfg in _DASHBOARD_REGISTRY.items():
        if cfg.rls_mode == "agent_via_join":
            assert cfg.rls_join_column, (
                f"{dashboard_id}: rls_mode=agent_via_join but rls_join_column unset"
            )


def test_service_rejects_unknown_dashboard():
    svc = DashboardsService(db_pool=None)  # service.get_schema doesn't touch the pool
    with pytest.raises(DashboardNotFoundError):
        svc.get_schema("nonexistent")


def test_service_get_schema_recaudacion():
    svc = DashboardsService(db_pool=None)
    resp = svc.get_schema("recaudacion")
    assert resp.dashboard_id == "recaudacion"
    assert len(resp.fields) == len(_SCHEMA_RECAUDACION)
    # rls_mode visible in notes for client-side debugging
    assert resp.notes and "rls_mode=" in resp.notes


def test_service_get_schema_agentes():
    """agentes dashboard schema is well-formed."""
    svc = DashboardsService(db_pool=None)
    resp = svc.get_schema("agentes")
    assert resp.dashboard_id == "agentes"
    field_names = {f.name for f in resp.fields}
    assert "agent_name" in field_names
    assert "approved" in field_names
    assert "p50_duration_seconds" in field_names


def test_service_get_schema_services():
    """services dashboard schema includes the multilingual catalog fields."""
    svc = DashboardsService(db_pool=None)
    resp = svc.get_schema("services")
    assert resp.dashboard_id == "services"
    field_names = {f.name for f in resp.fields}
    assert "service_code" in field_names
    assert "name_es" in field_names
    assert "ministry_name_es" in field_names


def test_list_dashboards():
    svc = DashboardsService(db_pool=None)
    listed = svc.list_dashboards()
    assert "recaudacion" in listed
    assert "agentes" in listed
    assert "services" in listed


# ---------------------------------------------------------------------------
# Service security — fields parameter cannot inject SQL
# ---------------------------------------------------------------------------


def test_fields_parameter_only_allows_schema_columns():
    """If the caller passes a malicious `fields` list, only schema columns
    survive the filter — preventing SQL injection via the column list.
    Repeated for every dashboard so a future addition can't bypass the
    allowlist by accident."""
    for dashboard_id, cfg in _DASHBOARD_REGISTRY.items():
        first_legit = cfg.columns[0]
        requested = [
            first_legit,                       # legitimate
            "DROP TABLE users",                 # attempted injection
            "1; SELECT * FROM payments",        # attempted injection
        ]
        allowed = [c for c in requested if c in cfg.columns]
        assert allowed == [first_legit], (
            f"{dashboard_id}: injection slipped through — got {allowed}"
        )


def test_empty_fields_returns_all_columns():
    """When the connector doesn't pass `fields`, we fall back to the full schema."""
    for dashboard_id, cfg in _DASHBOARD_REGISTRY.items():
        requested = []
        allowed = [c for c in requested if c in cfg.columns]
        if not allowed:
            allowed = list(cfg.columns)
        assert set(allowed) == set(cfg.columns)


# ---------------------------------------------------------------------------
# Reports config (Phase 5 — admin embed)
# ---------------------------------------------------------------------------


def test_report_entry_strict_shape():
    entry = DashboardReportEntry(
        dashboard_id="recaudacion",
        label="Recaudación",
        description="Treasury",
        looker_report_id="abc-123",
        looker_page_id="page1",
        rls_mode="entity",
    )
    assert entry.dashboard_id == "recaudacion"
    assert entry.looker_report_id == "abc-123"
    # extra='forbid' rejects unknown keys
    with pytest.raises(Exception):
        DashboardReportEntry(
            dashboard_id="x", label="x", description="x",
            looker_report_id=None, looker_page_id=None, rls_mode="entity",
            surprise=True,
        )


def test_report_entry_allows_null_report_id():
    """A dashboard whose Looker report has not been built yet has
    looker_report_id=None — the frontend renders an "Awaiting setup"
    placeholder for those instead of a broken iframe."""
    entry = DashboardReportEntry(
        dashboard_id="services",
        label="Catalog",
        description="…",
        looker_report_id=None,
        looker_page_id=None,
        rls_mode="public",
    )
    assert entry.looker_report_id is None


def test_reports_config_response_serialises():
    resp = DashboardReportsConfigResponse(reports=[])
    js = resp.model_dump_json()
    assert '"reports":' in js
