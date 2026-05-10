-- Migration 099: Add RESIDENCIA workflow codes to CNEDOGE for Phase 2 appointments
-- Phase 2 (con nota de ingreso): users go to CNEDOGE for permit collection and payment
-- Entity routing is driven by entities.workflow_codes JSONB (never hardcoded in code)

-- Add RESIDENCIA_PRIMERA_VEZ to CNEDOGE if not already present
UPDATE entities
SET workflow_codes = COALESCE(workflow_codes, '[]'::jsonb) || '["RESIDENCIA_PRIMERA_VEZ"]'::jsonb,
    updated_at = NOW()
WHERE code = 'CNEDOGE'
  AND NOT (COALESCE(workflow_codes, '[]'::jsonb) @> '"RESIDENCIA_PRIMERA_VEZ"');

-- Add RESIDENCIA_RENOVACION to CNEDOGE if not already present
UPDATE entities
SET workflow_codes = COALESCE(workflow_codes, '[]'::jsonb) || '["RESIDENCIA_RENOVACION"]'::jsonb,
    updated_at = NOW()
WHERE code = 'CNEDOGE'
  AND NOT (COALESCE(workflow_codes, '[]'::jsonb) @> '"RESIDENCIA_RENOVACION"');
