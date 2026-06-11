-- Migration 197: Fix business role permissions
-- Business role has only 1 permission (assignment.view) — critically broken
-- Fix: add citizen baseline + accountant extras + dashboard + payment
-- Date: 2026-03-10

-- Add all permissions that business users need (idempotent)
INSERT INTO role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM roles WHERE code = 'business'),
    p.id
FROM permissions p
WHERE p.name IN (
    -- Citizen baseline (missing from business)
    'declaration.amend',
    'declaration.create',
    'declaration.delete',
    'declaration.submit',
    'declaration.update',
    'declaration.view',
    -- Accountant extras (business volume needs)
    'assignment.list',
    'declaration.batch_create',
    'declaration.batch_submit',
    'declaration.import_excel',
    -- Payment
    'payment.create',
    -- Dashboard
    'dashboard.view_own',
    'dashboard.view_own_stats'
)
AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = (SELECT id FROM roles WHERE code = 'business')
    AND rp.permission_id = p.id
);
