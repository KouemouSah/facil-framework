"""
Pydantic models for the dashboard_registrations admin API
(E1 phase 2 + Grafana E1 + mig 323 metadata).

The DTOs power 7 endpoints:
- GET    /api/v1/dashboards/reports-config              — public list (RBAC-filtered)
- GET    /api/v1/dashboards/admin/configs               — admin list
- POST   /api/v1/dashboards/admin/configs               — create new dashboard (mig 323)
- PUT    /api/v1/dashboards/admin/configs/{id}          — update provider/UID/active
- PATCH  /api/v1/dashboards/admin/configs/{id}/metadata — patch i18n metadata (mig 323)
- DELETE /api/v1/dashboards/admin/configs/{id}          — soft-delete (mig 323)
- GET    /api/v1/dashboards/admin/grafana/discover      — list Grafana API dashboards (mig 323)
- POST   /api/v1/dashboards/admin/grafana/import        — bulk import (mig 323)

Regex constraints mirror the BD CHECK constraints in migrations 317 + 319 + 323
so that an invalid input is rejected at the Pydantic layer (422) before any
BD round-trip.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Source label visible to the frontend.
DashboardConfigSource = Literal["db", "env_fallback", "unset"]

# Provider type for the embed iframe.
DashboardProvider = Literal["looker_studio", "grafana"]

# RLS mode (mig 323 CHECK chk_rls_mode_value).
DashboardRlsMode = Literal["public", "authenticated", "entity", "agent_via_join", "admin_only"]

# Embed mode (mig 323 CHECK chk_embed_mode_value).
DashboardEmbedMode = Literal["kiosk", "solo", "panel"]

# Category (mig 323 CHECK chk_category_value).
DashboardCategory = Literal["executive", "finance", "operations", "security", "business", "product"]

# Regex for a path-safe slug used as dashboard_id (URL segment + DB key).
# Stricter than _format above because dashboard_id appears in URLs and
# log lines: we forbid leading digits and length 3..40.
_DASHBOARD_ID_REGEX = r"^[a-z][a-z0-9_-]{2,39}$"

# Default Grafana time range pattern: "now" or "now-<n><unit>" with unit in s|m|h|d|w|M|y.
_TIME_RANGE_REGEX = r"^now(-[0-9]+[smhdwMy])?$"


class DashboardConfigDTO(BaseModel):
    """One dashboard config row — full BD record + computed embed URL.

    Mig 323: i18n metadata (title_*, description_*) lives in the BD now,
    not in an in-code registry. `label` and `description` are computed
    server-side from title_es / description_es for backwards compat with
    the existing frontend (which reads `label` / `description` directly).
    """

    dashboard_id: str
    label: str  # backwards compat = title_es
    description: str  # backwards compat = description_es (or "" if NULL)

    # i18n metadata (new, mig 323)
    title_es: str
    title_fr: str
    title_en: str
    description_es: Optional[str] = None
    description_fr: Optional[str] = None
    description_en: Optional[str] = None

    # Presentation
    rls_mode: DashboardRlsMode
    embed_mode: DashboardEmbedMode = "kiosk"
    panel_id: Optional[int] = None
    display_order: int = 0
    default_time_range: str = "now-90d"
    icon_name: Optional[str] = None
    category: Optional[DashboardCategory] = None

    # Provider switch
    provider: DashboardProvider = "looker_studio"

    # Looker Studio fields
    looker_report_id: Optional[str] = None
    looker_page_id: Optional[str] = None

    # Grafana fields
    grafana_dashboard_uid: Optional[str] = None
    grafana_org_id: int = 1

    is_active: bool = True
    source: DashboardConfigSource

    # Computed embed URL — backend builds it from the active provider's fields.
    embed_url: Optional[str] = None

    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")


class DashboardConfigCreateRequest(BaseModel):
    """POST body — create a new dashboard from scratch (mig 323).

    All required metadata fields must be supplied. `dashboard_id` becomes the
    permanent slug (immutable) used in URLs and audit logs.
    """

    dashboard_id: str = Field(
        ...,
        min_length=3,
        max_length=40,
        pattern=_DASHBOARD_ID_REGEX,
        description="URL-safe slug (lowercase, starts with letter, allows -_). Immutable after creation.",
    )

    provider: DashboardProvider = "looker_studio"

    # Provider config (conditionally required by validator)
    looker_report_id: Optional[str] = Field(
        default=None, min_length=8, max_length=64,
        pattern=r"^[a-zA-Z0-9_-]{8,64}$",
    )
    looker_page_id: Optional[str] = Field(
        default=None, min_length=1, max_length=32,
        pattern=r"^[a-zA-Z0-9_]{1,32}$",
    )
    grafana_dashboard_uid: Optional[str] = Field(
        default=None, min_length=4, max_length=40,
        pattern=r"^[a-zA-Z0-9_-]{4,40}$",
    )
    grafana_org_id: int = Field(default=1, ge=1, le=999)

    # i18n (required)
    title_es: str = Field(..., min_length=1, max_length=120)
    title_fr: str = Field(..., min_length=1, max_length=120)
    title_en: str = Field(..., min_length=1, max_length=120)
    description_es: Optional[str] = Field(default=None, max_length=500)
    description_fr: Optional[str] = Field(default=None, max_length=500)
    description_en: Optional[str] = Field(default=None, max_length=500)

    # Presentation
    rls_mode: DashboardRlsMode = "authenticated"
    embed_mode: DashboardEmbedMode = "kiosk"
    panel_id: Optional[int] = Field(default=None, ge=1)
    display_order: int = Field(default=50, ge=0, le=999)
    default_time_range: str = Field(
        default="now-90d", pattern=_TIME_RANGE_REGEX,
    )
    icon_name: Optional[str] = Field(
        default=None, max_length=64,
        pattern=r"^[A-Za-z][A-Za-z0-9]*Icon$",
    )
    category: Optional[DashboardCategory] = None

    is_active: bool = True

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_provider_fields(self) -> "DashboardConfigCreateRequest":
        if self.provider == "looker_studio" and not self.looker_report_id:
            raise ValueError("looker_report_id is required when provider='looker_studio'")
        if self.provider == "grafana" and not self.grafana_dashboard_uid:
            raise ValueError("grafana_dashboard_uid is required when provider='grafana'")
        if self.embed_mode != "kiosk" and self.panel_id is None:
            raise ValueError(f"panel_id is required when embed_mode='{self.embed_mode}'")
        return self


class DashboardConfigUpdateRequest(BaseModel):
    """PUT body — only the fields an admin can edit on the existing form.

    DOES NOT include metadata fields (title/description/category/etc.) —
    those are patched separately via PATCH /admin/configs/{id}/metadata.
    """

    provider: DashboardProvider = Field(default="looker_studio")

    looker_report_id: Optional[str] = Field(
        default=None, min_length=8, max_length=64,
        pattern=r"^[a-zA-Z0-9_-]{8,64}$",
    )
    looker_page_id: Optional[str] = Field(
        default=None, min_length=1, max_length=32,
        pattern=r"^[a-zA-Z0-9_]{1,32}$",
    )
    grafana_dashboard_uid: Optional[str] = Field(
        default=None, min_length=4, max_length=40,
        pattern=r"^[a-zA-Z0-9_-]{4,40}$",
    )
    grafana_org_id: int = Field(default=1, ge=1, le=999)

    is_active: bool = Field(default=True)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_provider_fields(self) -> "DashboardConfigUpdateRequest":
        if self.provider == "looker_studio" and not self.looker_report_id:
            raise ValueError("looker_report_id is required when provider='looker_studio'")
        if self.provider == "grafana" and not self.grafana_dashboard_uid:
            raise ValueError("grafana_dashboard_uid is required when provider='grafana'")
        return self


class DashboardMetadataPatchRequest(BaseModel):
    """PATCH body — partial update of i18n + presentation fields (mig 323).

    All fields optional; None means "do not change".
    """

    title_es: Optional[str] = Field(default=None, min_length=1, max_length=120)
    title_fr: Optional[str] = Field(default=None, min_length=1, max_length=120)
    title_en: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description_es: Optional[str] = Field(default=None, max_length=500)
    description_fr: Optional[str] = Field(default=None, max_length=500)
    description_en: Optional[str] = Field(default=None, max_length=500)

    rls_mode: Optional[DashboardRlsMode] = None
    embed_mode: Optional[DashboardEmbedMode] = None
    panel_id: Optional[int] = Field(default=None, ge=1)
    display_order: Optional[int] = Field(default=None, ge=0, le=999)
    default_time_range: Optional[str] = Field(
        default=None, pattern=_TIME_RANGE_REGEX,
    )
    icon_name: Optional[str] = Field(
        default=None, max_length=64,
        pattern=r"^[A-Za-z][A-Za-z0-9]*Icon$",
    )
    category: Optional[DashboardCategory] = None

    model_config = ConfigDict(extra="forbid")


class DashboardConfigsListResponse(BaseModel):
    """Response of GET /api/v1/dashboards/admin/configs."""

    configs: list[DashboardConfigDTO]

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Grafana discover/import (mig 323)
# ---------------------------------------------------------------------------

class GrafanaDiscoverEntry(BaseModel):
    """One dashboard discovered via Grafana /api/search.

    `already_imported` is True when the UID already exists in dashboard_registrations
    (so the UI can grey it out / show a checkmark).
    """

    uid: str
    title: str
    slug: Optional[str] = None
    folder_title: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    already_imported: bool = False

    model_config = ConfigDict(extra="forbid")


class GrafanaDiscoverResponse(BaseModel):
    """Response of GET /api/v1/dashboards/admin/grafana/discover."""

    grafana_base_url: Optional[str] = None
    sa_token_configured: bool = False
    dashboards: list[GrafanaDiscoverEntry] = Field(default_factory=list)
    error: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class GrafanaImportItem(BaseModel):
    """One dashboard the admin chose to import in the bulk modal."""

    uid: str = Field(..., min_length=4, max_length=40, pattern=r"^[a-zA-Z0-9_-]{4,40}$")
    dashboard_id: str = Field(..., min_length=3, max_length=40, pattern=_DASHBOARD_ID_REGEX)
    title_es: str = Field(..., min_length=1, max_length=120)
    title_fr: str = Field(..., min_length=1, max_length=120)
    title_en: str = Field(..., min_length=1, max_length=120)
    description_es: Optional[str] = Field(default=None, max_length=500)
    description_fr: Optional[str] = Field(default=None, max_length=500)
    description_en: Optional[str] = Field(default=None, max_length=500)
    category: Optional[DashboardCategory] = None
    rls_mode: DashboardRlsMode = "authenticated"
    grafana_org_id: int = Field(default=1, ge=1, le=999)
    display_order: int = Field(default=50, ge=0, le=999)
    icon_name: Optional[str] = Field(default=None, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9]*Icon$")

    model_config = ConfigDict(extra="forbid")


class GrafanaImportRequest(BaseModel):
    """POST body for bulk import."""

    items: list[GrafanaImportItem] = Field(..., min_length=1, max_length=20)

    model_config = ConfigDict(extra="forbid")


class GrafanaImportResponse(BaseModel):
    """Response of POST /admin/grafana/import — per-item outcome."""

    imported: list[str] = Field(default_factory=list)  # dashboard_ids successfully created
    skipped: list[dict] = Field(default_factory=list)  # [{dashboard_id, reason}]
    errors: list[dict] = Field(default_factory=list)   # [{dashboard_id, error}]

    model_config = ConfigDict(extra="forbid")
