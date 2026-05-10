/**
 * Types for the dashboards-admin module — mirrors backend
 * app.modules.dashboards.models.{DashboardReportEntry, DashboardConfigDTO, ...}.
 *
 * Keep in sync with:
 *   packages/backend/app/modules/dashboards/models/dashboards.py
 *   packages/backend/app/modules/dashboards/models/dashboard_config.py
 *
 * Mig 323 (2026-05-05): metadata is now BD-driven (i18n triplets, category,
 * embed_mode, panel_id, display_order, default_time_range, icon_name).
 * `label` and `description` are backwards-compat aliases (= title_es / description_es).
 */

export type DashboardRlsMode =
  | 'public'
  | 'authenticated'
  | 'entity'
  | 'agent_via_join'
  | 'admin_only'

export type DashboardEmbedMode = 'kiosk' | 'solo' | 'panel'

export type DashboardCategory =
  | 'executive'
  | 'finance'
  | 'operations'
  | 'security'
  | 'business'
  | 'product'

export type DashboardConfigSource = 'db' | 'env_fallback' | 'unset'

export type DashboardProvider = 'looker_studio' | 'grafana'

export interface DashboardReportEntry {
  dashboard_id: string
  /** = title_es (backwards-compat). Use title_<locale> for new code. */
  label: string
  /** = description_es. */
  description: string
  rls_mode: DashboardRlsMode

  // Mig 323 — i18n triplets
  title_es: string
  title_fr: string
  title_en: string
  description_es: string | null
  description_fr: string | null
  description_en: string | null

  // Mig 323 — presentation
  category: DashboardCategory | null
  display_order: number
  icon_name: string | null
  embed_mode: DashboardEmbedMode
  panel_id: number | null
  default_time_range: string

  provider: DashboardProvider
  looker_report_id: string | null
  looker_page_id: string | null
  grafana_dashboard_uid: string | null
  grafana_org_id: number

  embed_url: string | null
}

export interface DashboardReportsConfigResponse {
  reports: DashboardReportEntry[]
}

export interface DashboardConfigDTO {
  dashboard_id: string
  label: string
  description: string

  // Mig 323 — i18n
  title_es: string
  title_fr: string
  title_en: string
  description_es: string | null
  description_fr: string | null
  description_en: string | null

  // Mig 323 — presentation
  rls_mode: DashboardRlsMode
  embed_mode: DashboardEmbedMode
  panel_id: number | null
  display_order: number
  default_time_range: string
  icon_name: string | null
  category: DashboardCategory | null

  provider: DashboardProvider
  looker_report_id: string | null
  looker_page_id: string | null
  grafana_dashboard_uid: string | null
  grafana_org_id: number

  is_active: boolean
  source: DashboardConfigSource
  embed_url: string | null

  updated_by: string | null
  updated_at: string | null
  created_at: string | null
}

export interface DashboardConfigUpdateRequest {
  provider: DashboardProvider
  looker_report_id?: string | null
  looker_page_id?: string | null
  grafana_dashboard_uid?: string | null
  grafana_org_id?: number
  is_active: boolean
}

export interface DashboardConfigCreateRequest {
  dashboard_id: string
  provider: DashboardProvider
  looker_report_id?: string | null
  looker_page_id?: string | null
  grafana_dashboard_uid?: string | null
  grafana_org_id?: number

  title_es: string
  title_fr: string
  title_en: string
  description_es?: string | null
  description_fr?: string | null
  description_en?: string | null

  rls_mode?: DashboardRlsMode
  embed_mode?: DashboardEmbedMode
  panel_id?: number | null
  display_order?: number
  default_time_range?: string
  icon_name?: string | null
  category?: DashboardCategory | null

  is_active?: boolean
}

export interface DashboardMetadataPatchRequest {
  title_es?: string
  title_fr?: string
  title_en?: string
  description_es?: string | null
  description_fr?: string | null
  description_en?: string | null
  rls_mode?: DashboardRlsMode
  embed_mode?: DashboardEmbedMode
  panel_id?: number | null
  display_order?: number
  default_time_range?: string
  icon_name?: string | null
  category?: DashboardCategory | null
}

export interface DashboardConfigsListResponse {
  configs: DashboardConfigDTO[]
}

// ---------------------------------------------------------------------------
// Grafana discover/import (mig 323)
// ---------------------------------------------------------------------------

export interface GrafanaDiscoverEntry {
  uid: string
  title: string
  slug: string | null
  folder_title: string | null
  tags: string[]
  already_imported: boolean
}

export interface GrafanaDiscoverResponse {
  grafana_base_url: string | null
  sa_token_configured: boolean
  dashboards: GrafanaDiscoverEntry[]
  error: string | null
}

export interface GrafanaImportItem {
  uid: string
  dashboard_id: string
  title_es: string
  title_fr: string
  title_en: string
  description_es?: string | null
  description_fr?: string | null
  description_en?: string | null
  category?: DashboardCategory | null
  rls_mode?: DashboardRlsMode
  grafana_org_id?: number
  display_order?: number
  icon_name?: string | null
}

export interface GrafanaImportRequest {
  items: GrafanaImportItem[]
}

export interface GrafanaImportResponse {
  imported: string[]
  skipped: Array<{ dashboard_id: string; reason: string }>
  errors: Array<{ dashboard_id: string; error: string }>
}
