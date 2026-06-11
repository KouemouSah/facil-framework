-- Migration 110: Add include_batch to workflow_menu_mapping
--
-- Batch processing pages exist at /dashboard/agent/{entity}/batch-requests/
-- but the menu system doesn't have a flag to control this sub-menu.
-- Also fixes permission_prefix inconsistency on VISADO_% (service_requests→service_request).
-- Also fixes display_order collision (FP=6, VISADO=6 → VISADO=7).
--
-- Date: 2026-02-17

BEGIN;

ALTER TABLE workflow_menu_mapping
    ADD COLUMN IF NOT EXISTS include_batch BOOLEAN DEFAULT FALSE;

-- Fix permission_prefix inconsistency: VISADO_% had 'service_requests' (plural)
-- while all others use 'service_request' (singular)
UPDATE workflow_menu_mapping
SET permission_prefix = 'service_request'
WHERE workflow_pattern = 'VISADO_%' AND permission_prefix = 'service_requests';

-- Fix display_order collision: FP=6 stays, VISADO bumped to 7
UPDATE workflow_menu_mapping
SET display_order = 7
WHERE workflow_pattern = 'VISADO_%' AND display_order = 6;

-- Also fix the 3 visado individual mappings to use service_request (singular)
UPDATE workflow_menu_mapping
SET permission_prefix = 'service_request'
WHERE workflow_pattern IN ('PRORROGA_VISADO', 'SALIDA_VISADO_VENCIDO', 'PERMANENCIA_EXTRANJERIA')
AND permission_prefix = 'service_requests';

COMMIT;
