-- Migration 103: Complete workflow_menu_mapping with missing patterns
-- Purpose: Seed menu mapping entries for FP (Función Pública) and VISADO workflows
-- that were missing from the initial migration 063.
-- Date: 2026-02-14
--
-- Note: The workflow_sync_service handles full synchronization at app startup.
-- This migration provides the initial seed data only for first deploy before
-- the sync service runs.
--
-- Category resolution is 100% dynamic via PredefinedWorkflow.menu_group:
-- - FP workflows: menu_group = "FP" (default from prefix)
-- - VISADO workflows: menu_group = "VISADO" (overridden in TramitesVisadoWorkflow)
-- No prefix-based fallback patterns needed.

BEGIN;

-- =============================================================================
-- 1. Add missing workflow_menu_mapping entries (2 patterns, GAP-04)
-- =============================================================================
-- Existing patterns (migration 063): PASAPORTE_%, RESIDENCIA_%, CONDUCIR_%, VEHICULO_%, CONTRATO_%
-- Missing: FP_% and VISADO_%

INSERT INTO workflow_menu_mapping (
    workflow_pattern, menu_group_id, menu_title_key, menu_icon,
    display_order, include_appointments, permission_prefix
) VALUES
    -- Función Pública: FP_VERIFICACION, FP_CARNET, FP_PROMOCION, FP_PERMISO, FP_CERTIFICADO
    ('FP_%', 'fp', 'agent.nav.fp', 'Briefcase', 6, TRUE, 'service_requests'),

    -- Visados: PRORROGA_VISADO, VISADO_ALTERNATIVO, PERMANENCIA_EXTRANJERIA, SALIDA_VISADO_VENCIDO
    -- All 4 codes resolve to menu_group="VISADO" via TramitesVisadoWorkflow.menu_group override
    ('VISADO_%', 'visados', 'agent.nav.visas', 'Globe', 7, FALSE, 'service_requests')
ON CONFLICT (workflow_pattern) DO NOTHING;

-- Clean up any stale fallback patterns that may exist from earlier migrations
DELETE FROM workflow_menu_mapping
WHERE workflow_pattern IN ('PRORROGA_%', 'PERMANENCIA_%', 'SALIDA_%')
  AND menu_group_id = 'visados';

COMMIT;
