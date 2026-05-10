"""
Pydantic models for dashboards endpoints.

The shape matches what the Looker Studio Community Connector expects in its
`getSchema()` and `getData()` responses (see
https://developers.google.com/looker-studio/connector/reference#getschema,
https://developers.google.com/looker-studio/connector/reference#getdata).
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Looker Studio field semantic type subset we use today.
# Full list: https://developers.google.com/looker-studio/connector/reference#semantictype
LookerSemanticType = Literal[
    "TEXT",
    "URL",
    "BOOLEAN",
    "NUMBER",
    "PERCENT",
    "CURRENCY_XAF",
    "CURRENCY_USD",
    "CURRENCY_EUR",
    "DURATION",
    "YEAR",
    "YEAR_MONTH",
    "YEAR_MONTH_DAY",
    "YEAR_MONTH_DAY_HOUR",
    "YEAR_MONTH_DAY_SECOND",
    "COUNTRY",
    "LATITUDE_LONGITUDE",
]

LookerDataType = Literal["STRING", "NUMBER", "BOOLEAN"]
LookerConceptType = Literal["DIMENSION", "METRIC"]


class LookerSchemaSemantics(BaseModel):
    """Looker semantic descriptor for a field."""

    conceptType: LookerConceptType
    semanticType: Optional[LookerSemanticType] = None

    model_config = ConfigDict(extra="forbid")


class LookerSchemaField(BaseModel):
    """One column the connector exposes to Looker Studio."""

    name: str = Field(..., description="Stable identifier — used as the SQL alias")
    label: str = Field(..., description="Human-readable label rendered in chart legends")
    dataType: LookerDataType
    semantics: LookerSchemaSemantics
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class DashboardSchemaResponse(BaseModel):
    """Response of GET /api/v1/dashboards/{id}/schema"""

    dashboard_id: str
    schema_version: int = 1
    fields: list[LookerSchemaField] = Field(..., alias="schema")
    refreshed_at: datetime
    notes: Optional[str] = None

    # alias='schema' is the JSON key expected by the Looker Studio connector
    # (see https://developers.google.com/looker-studio/connector/reference#getschema).
    # Internally we name the field `fields` to avoid shadowing BaseModel.schema().
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DashboardDataRow(BaseModel):
    """One row of the dataset returned to Looker."""

    values: list[Any] = Field(
        ..., description="Cell values in the same order as the schema fields. None for NULL."
    )

    model_config = ConfigDict(extra="forbid")


class DashboardDataResponse(BaseModel):
    """Response of GET /api/v1/dashboards/{id}/data"""

    dashboard_id: str
    fields: list[LookerSchemaField] = Field(..., alias="schema")
    rows: list[DashboardDataRow]
    row_count: int
    filters_applied: list[str] = Field(
        default_factory=list,
        description="Human-readable list of filters Looker passed; useful for B.2 RLS audit.",
    )
    refreshed_at: datetime

    # alias='schema' is the Looker connector's expected JSON key.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DashboardPingResponse(BaseModel):
    """Response of GET /api/v1/dashboards/_ping — confirms connector auth works.

    NOTE on `ministry_id`: this field is **legacy / audit-only**. The RLS engine
    (services/rls.py) does NOT use ministry_id; it filters via `entity_codes`
    resolved from `agent_profiles.entity_id → entities.code`. The field is
    kept here for backwards compatibility with an early connector skeleton
    and for human-readable hint in the audit log; do NOT introduce new
    ministry-based logic. See `LOOKER_STUDIO_STATE_REPORT_2026_05_02.md` §2.2.
    """

    user_email: str
    user_id: str
    role: Optional[str] = None
    ministry_id: Optional[int] = Field(
        default=None,
        description=(
            "Legacy hint — may be the first ministry id of a multi-entity user "
            "or None. NOT used for RLS filtering (which is entity-based). "
            "Kept for backwards compat with the early connector design."
        ),
    )

    model_config = ConfigDict(extra="forbid")


class DashboardReportEntry(BaseModel):
    """Embed metadata for one report exposed at /admin/dashboards.

    Looker Studio fields (legacy): `looker_report_id` and `looker_page_id`
    come from the Looker Studio UI URL.

    Grafana E1 (2026-05-04): adds `provider`, `grafana_dashboard_uid`,
    `grafana_org_id`, and `embed_url`. The frontend reads `embed_url` directly
    when available — it's pre-built by the backend service from the active
    provider's config so the iframe just needs to be set to it.

    Mig 323 (2026-05-05): metadata now BD-driven. `label` and `description` are
    backwards-compat aliases (= title_es / description_es) so the existing
    frontend code keeps working while the new code uses the i18n triplets
    + category + display_order + icon_name + embed_mode fields.
    """

    dashboard_id: str = Field(..., description="Stable id matching the BD row")
    label: str = Field(..., description="Human-readable name (= title_es for back-compat)")
    description: str = Field(..., description="One-line subtitle (= description_es or '')")
    rls_mode: str = Field(..., description="public / authenticated / entity / agent_via_join / admin_only")

    # Mig 323 — i18n triplets (frontend picks the locale)
    title_es: str = Field(default="")
    title_fr: str = Field(default="")
    title_en: str = Field(default="")
    description_es: Optional[str] = None
    description_fr: Optional[str] = None
    description_en: Optional[str] = None

    # Mig 323 — presentation
    category: Optional[str] = None
    display_order: int = 0
    icon_name: Optional[str] = None
    embed_mode: str = "kiosk"
    panel_id: Optional[int] = None
    default_time_range: str = "now-90d"

    # Provider switch — looker_studio (default) or grafana
    provider: str = Field(
        default="looker_studio",
        description="Active provider for the iframe embed: looker_studio | grafana.",
    )

    # Looker Studio fields
    looker_report_id: Optional[str] = Field(
        default=None,
        description="Looker Studio report ID. Null when provider != looker_studio or unset.",
    )
    looker_page_id: Optional[str] = Field(default=None)

    # Grafana fields
    grafana_dashboard_uid: Optional[str] = Field(
        default=None,
        description="Grafana dashboard UID. Null when provider != grafana or unset.",
    )
    grafana_org_id: int = Field(default=1)

    # Backend-computed iframe URL based on the active provider's config.
    embed_url: Optional[str] = Field(
        default=None,
        description="Pre-built iframe URL. Null when the active provider has no config yet.",
    )

    model_config = ConfigDict(extra="forbid")


class DashboardReportsConfigResponse(BaseModel):
    """Response of GET /api/v1/dashboards/reports-config — lists the embeddable
    Looker reports the caller is authorised to see.
    """

    reports: list[DashboardReportEntry]

    model_config = ConfigDict(extra="forbid")
