-- Migration 109: Seed individual workflow_menu_mapping for 3 visado codes
--
-- Problem: Pattern VISADO_% only matches VISADO_ALTERNATIVO (1/4 codes).
-- The other 3 codes (PRORROGA_VISADO, SALIDA_VISADO_VENCIDO, PERMANENCIA_EXTRANJERIA)
-- don't start with VISADO_ so they need exact-match mappings.
-- All 4 codes belong to the same menu group "visados".
--
-- Date: 2026-02-17

BEGIN;

INSERT INTO workflow_menu_mapping (
    workflow_pattern, menu_group_id, menu_title_key, menu_icon,
    display_order, include_pending, include_validation,
    include_appointments, include_history, include_escalation,
    permission_prefix, is_active
) VALUES
    ('PRORROGA_VISADO', 'visado', 'agent.nav.visas', 'Globe',
     7, TRUE, TRUE, FALSE, TRUE, TRUE, 'service_requests', TRUE),
    ('SALIDA_VISADO_VENCIDO', 'visado', 'agent.nav.visas', 'Globe',
     7, TRUE, TRUE, FALSE, TRUE, TRUE, 'service_requests', TRUE),
    ('PERMANENCIA_EXTRANJERIA', 'visado', 'agent.nav.visas', 'Globe',
     7, TRUE, TRUE, FALSE, TRUE, TRUE, 'service_requests', TRUE)
ON CONFLICT (workflow_pattern) DO NOTHING;

COMMIT;
