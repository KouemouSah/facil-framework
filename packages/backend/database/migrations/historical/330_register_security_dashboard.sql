-- =============================================================================
-- Migration 330 — register Security Monitoring dashboard (Phase C.5)
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: SECURITY_OBSERVABILITY_PLAN.md §C.5
--
-- Adds the 12th dashboard (`facil-security-monitoring`) to dashboard_registrations.
-- Source: infra/grafana/dashboards/11_security_monitoring.json (UID identical).
-- =============================================================================

BEGIN;

INSERT INTO dashboard_registrations (
    dashboard_id, provider, grafana_dashboard_uid, grafana_org_id,
    looker_report_id, is_active,
    rls_mode, embed_mode, default_time_range,
    title_es, title_fr, title_en,
    description_es, description_fr, description_en,
    category, display_order, icon_name
)
VALUES (
    'security-monitoring', 'grafana', 'facil-security-monitoring', 1,
    NULL, true,
    'admin_only', 'kiosk', 'now-24h',
    'Monitoreo de Seguridad',
    'Surveillance de Sécurité',
    'Security Monitoring',
    'IPs, dispositivos, ubicación geográfica, patrones sospechosos. Fuente: tabla request_telemetry (mig 329) + audit_logs.',
    'IPs, devices, géolocalisation, patterns suspects. Source : table request_telemetry (mig 329) + audit_logs.',
    'IPs, devices, geolocation, suspicious patterns. Source: request_telemetry table (mig 329) + audit_logs.',
    'security', 95, 'ShieldExclamationIcon'
)
ON CONFLICT (dashboard_id) DO UPDATE SET
    provider              = EXCLUDED.provider,
    grafana_dashboard_uid = EXCLUDED.grafana_dashboard_uid,
    grafana_org_id        = EXCLUDED.grafana_org_id,
    is_active             = EXCLUDED.is_active,
    rls_mode              = EXCLUDED.rls_mode,
    embed_mode            = EXCLUDED.embed_mode,
    default_time_range    = EXCLUDED.default_time_range,
    title_es              = EXCLUDED.title_es,
    title_fr              = EXCLUDED.title_fr,
    title_en              = EXCLUDED.title_en,
    description_es        = EXCLUDED.description_es,
    description_fr        = EXCLUDED.description_fr,
    description_en        = EXCLUDED.description_en,
    category              = EXCLUDED.category,
    display_order         = EXCLUDED.display_order,
    icon_name             = EXCLUDED.icon_name,
    updated_at            = NOW();

COMMIT;
