-- Migration 251: Field collection double validation + reconciliation
-- Date: 2026-03-21
-- Adds: field_collected workflow status (already added to enum via Python)
--       supervisor reconciliation endpoint permissions
--       index for supervisor reconciliation queue

BEGIN;

-- Index for supervisor reconciliation queue (field collections pending validation)
CREATE INDEX IF NOT EXISTS idx_sp_field_reconciliation
    ON service_payments(entity_code, collected_by, created_at DESC)
    WHERE collection_type = 'field'
      AND workflow_status = 'field_collected';

-- Permission for supervisor reconciliation
INSERT INTO permissions (name, resource, action, description, module_name)
VALUES ('inspection.reconcile_validate', 'inspection', 'reconcile_validate',
        'Validate field cash reconciliation (supervisor)', 'inspections')
ON CONFLICT (name) DO NOTHING;

-- Assign to supervisor roles
SET LOCAL app.current_user_id = '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2';

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_ayuntamiento', 'supervisor_camara',
    'supervisor_min_comercio', 'supervisor_min_hacienda',
    'supervisor_min_informacion', 'supervisor_min_turismo',
    'supervisor_min_agricultura', 'supervisor_min_electricidad',
    'supervisor_tesoro'
)
AND p.name = 'inspection.reconcile_validate'
ON CONFLICT DO NOTHING;

COMMIT;
