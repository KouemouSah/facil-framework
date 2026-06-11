-- =============================================================================
-- Migration 326 — register AI Observability dashboard (Phase A.5)
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: .claude/plans/AI_OBSERVABILITY_PLAN.md §A.5
--
-- Adds the 11th dashboard (`facil-ai-observability`) to dashboard_registrations
-- so it appears in the /admin/dashboards listing alongside the 10 business
-- dashboards seeded by mig 323.
--
-- Source: infra/grafana/dashboards/10_ai_observability.json (UID identical).
-- Pushed to kouemousah.grafana.net via packages/backend/scripts/push_grafana_dashboards.py.
--
-- BD verified 2026-05-05:
--   - dashboard_registrations exists with mig 323 metadata columns
--   - facil-ai-observability does NOT yet exist
--   - 11 rows currently (10 grafana + 1 looker services)
--
-- Idempotent: ON CONFLICT DO UPDATE preserves admin tweaks (display_order,
-- rls_mode change) but always refreshes the embed wiring.
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
    'ai-observability', 'grafana', 'facil-ai-observability', 1,
    NULL, true,
    'admin_only', 'kiosk', 'now-7d',
    'Observabilidad IA (Gemini)',
    'Observabilité IA (Gemini)',
    'AI Observability (Gemini)',
    'Coste, latencia, tasa de errores y top prompts de los 18 puntos de llamada Gemini (RAG, OCR, clasificación, enriquecimiento, asignación, etc.).',
    'Coût, latence, taux d''erreur et top prompts des 18 points d''appel Gemini (RAG, OCR, classification, enrichissement, routage, etc.).',
    'Cost, latency, error rate, and top prompts across the 18 Gemini call sites (RAG, OCR, classification, enrichment, routing, etc.).',
    'security', 100, 'CpuChipIcon'
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

-- ---------------------------------------------------------------------------
-- VERIFICATION:
--   SELECT dashboard_id, provider, grafana_dashboard_uid, rls_mode, category,
--          title_es FROM dashboard_registrations
--   WHERE dashboard_id = 'ai-observability';
--   -- expected: 1 row, provider=grafana, uid=facil-ai-observability,
--   --           rls_mode=admin_only, category=security
-- ---------------------------------------------------------------------------

-- ROLLBACK:
-- BEGIN;
--   DELETE FROM dashboard_registrations WHERE dashboard_id = 'ai-observability';
-- COMMIT;
