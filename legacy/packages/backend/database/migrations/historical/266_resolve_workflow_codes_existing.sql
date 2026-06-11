-- Migration 181: Resolve workflow_code for existing service_requests
--
-- Problem: Multi-subtype workflows stored BASE code instead of RESOLVED code.
--   e.g. PASAPORTE_NUEVO for all pasaporte types, CONDUCIR_NUEVO for all conducir types.
--
-- Fix: Resolve to specific code using form_data->>motivo / form_data->>sub_type.
-- Also fixes the persist logic (wizard_session_service._resolve_workflow_code).
--
-- Impact: 12 rows (11 PASAPORTE + 1 CONDUCIR). All test data from dev environment.

-- ═══════════════════════════════════════════════════════════════
-- PASAPORTE: resolve via motivo (priority) then solicitud_type
-- ═══════════════════════════════════════════════════════════════

UPDATE service_requests
SET workflow_code = 'PASAPORTE_DETERIORO'
WHERE workflow_code = 'PASAPORTE_NUEVO'
  AND form_data->>'motivo' = 'DETERIORO';

UPDATE service_requests
SET workflow_code = 'PASAPORTE_RENOVACION'
WHERE workflow_code = 'PASAPORTE_NUEVO'
  AND form_data->>'motivo' = 'VENCIMIENTO';

UPDATE service_requests
SET workflow_code = 'PASAPORTE_PERDIDA'
WHERE workflow_code = 'PASAPORTE_NUEVO'
  AND form_data->>'motivo' = 'PERDIDA';

UPDATE service_requests
SET workflow_code = 'PASAPORTE_ROBO'
WHERE workflow_code = 'PASAPORTE_NUEVO'
  AND form_data->>'motivo' = 'ROBO';

-- Renovacion without specific motivo
UPDATE service_requests
SET workflow_code = 'PASAPORTE_RENOVACION'
WHERE workflow_code = 'PASAPORTE_NUEVO'
  AND form_data->>'solicitud_type' = 'renovacion'
  AND (form_data->>'motivo' IS NULL OR form_data->>'motivo' = '');

-- ═══════════════════════════════════════════════════════════════
-- CONDUCIR: resolve via sub_type
-- ═══════════════════════════════════════════════════════════════

UPDATE service_requests
SET workflow_code = 'CONDUCIR_RENOVACION'
WHERE workflow_code = 'CONDUCIR_NUEVO'
  AND form_data->>'sub_type' = 'RENOVACION';

UPDATE service_requests
SET workflow_code = 'CONDUCIR_CANJE'
WHERE workflow_code = 'CONDUCIR_NUEVO'
  AND form_data->>'sub_type' = 'CANJE';

UPDATE service_requests
SET workflow_code = 'CONDUCIR_DUPLICADO'
WHERE workflow_code = 'CONDUCIR_NUEVO'
  AND form_data->>'sub_type' = 'DUPLICADO';

UPDATE service_requests
SET workflow_code = 'CONDUCIR_EXTENSION'
WHERE workflow_code = 'CONDUCIR_NUEVO'
  AND form_data->>'sub_type' = 'EXTENSION';

-- ═══════════════════════════════════════════════════════════════
-- CONTRATO: resolve via sub_type (no existing data, but future-proof)
-- ═══════════════════════════════════════════════════════════════

UPDATE service_requests
SET workflow_code = 'CONTRATO_' || form_data->>'sub_type'
WHERE workflow_code = 'CONTRATO_OBRA'
  AND form_data->>'sub_type' IS NOT NULL
  AND form_data->>'sub_type' != 'OBRA'
  AND form_data->>'sub_type' IN ('SERVICIO', 'SUMINISTRO', 'CONCESION', 'JOINT_VENTURE', 'ARRENDAMIENTO', 'OTRO');

-- ═══════════════════════════════════════════════════════════════
-- VISADO: resolve via sub_type (no existing data, but future-proof)
-- ═══════════════════════════════════════════════════════════════

UPDATE service_requests
SET workflow_code = CASE form_data->>'sub_type'
    WHEN 'PRORROGA' THEN 'PRORROGA_VISADO'
    WHEN 'ALTERNATIVO' THEN 'VISADO_ALTERNATIVO'
    WHEN 'PERMANENCIA' THEN 'PERMANENCIA_EXTRANJERIA'
    WHEN 'SALIDA_VENCIDO' THEN 'SALIDA_VISADO_VENCIDO'
END
WHERE workflow_code = 'PRORROGA_VISADO'
  AND form_data->>'sub_type' IS NOT NULL
  AND form_data->>'sub_type' != 'PRORROGA'
  AND form_data->>'sub_type' IN ('ALTERNATIVO', 'PERMANENCIA', 'SALIDA_VENCIDO');

-- NOTE: RESIDENCIA does not need resolution — workflow_code is set correctly
-- at session creation (RESIDENCIA_PRIMERA_VEZ or RESIDENCIA_RENOVACION).
