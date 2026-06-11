-- Migration 183: Production hardening for workflow_code resolution
--
-- 3 measures:
--   1. app_migrations tracking table (know which migrations ran)
--   2. CHECK constraint on service_requests.workflow_code (reject typos/invalid codes)
--   3. Validation trigger: auto-resolve base codes on INSERT (safety net)
--
-- Idempotent: all statements use IF NOT EXISTS / OR REPLACE.

-- ═══════════════════════════════════════════════════════════════
-- 1. APP MIGRATIONS TRACKING TABLE
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS app_migrations (
    id SERIAL PRIMARY KEY,
    version VARCHAR(10) NOT NULL UNIQUE,       -- e.g. '183'
    name VARCHAR(255) NOT NULL,                 -- e.g. 'workflow_code_production_hardening'
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by VARCHAR(100),                    -- user or 'system'
    checksum VARCHAR(64),                       -- SHA-256 of SQL file (optional)
    execution_time_ms INTEGER,                  -- Duration (optional)
    notes TEXT                                  -- Free-form notes
);

COMMENT ON TABLE app_migrations IS
    'Tracks application-level SQL migrations. '
    'Check before executing: SELECT 1 FROM app_migrations WHERE version = $1';

-- Backfill: record this migration as the first tracked one
INSERT INTO app_migrations (version, name, applied_by, notes)
VALUES ('183', 'workflow_code_production_hardening', 'system',
        'First tracked migration. Adds app_migrations table, workflow_code CHECK, and resolution trigger.')
ON CONFLICT (version) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════
-- 2. VALID WORKFLOW CODES — Reference table (admin-managed)
-- ═══════════════════════════════════════════════════════════════
-- Instead of a static CHECK constraint (requires ALTER TABLE for new codes),
-- use a reference table that admins can manage via UI.

CREATE TABLE IF NOT EXISTS valid_workflow_codes (
    code VARCHAR(100) PRIMARY KEY,
    base_code VARCHAR(100),                     -- NULL if this IS the base code
    resolution_key VARCHAR(100),                -- The key that maps to this code (e.g. 'DETERIORO')
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE valid_workflow_codes IS
    'Authoritative list of valid workflow codes. '
    'Used by FK constraint on service_requests.workflow_code. '
    'Managed via admin UI — no SQL needed for new workflows.';

-- Seed from current entities.workflow_codes + WorkflowCode enum
INSERT INTO valid_workflow_codes (code, base_code, resolution_key) VALUES
    -- Pasaporte (base: PASAPORTE_NUEVO)
    ('PASAPORTE_NUEVO', NULL, 'NUEVO'),
    ('PASAPORTE_RENOVACION', 'PASAPORTE_NUEVO', 'RENOVACION'),
    ('PASAPORTE_PERDIDA', 'PASAPORTE_NUEVO', 'PERDIDA'),
    ('PASAPORTE_ROBO', 'PASAPORTE_NUEVO', 'ROBO'),
    ('PASAPORTE_DETERIORO', 'PASAPORTE_NUEVO', 'DETERIORO'),
    -- Conducir (base: CONDUCIR_NUEVO)
    ('CONDUCIR_NUEVO', NULL, 'NUEVO'),
    ('CONDUCIR_CANJE', 'CONDUCIR_NUEVO', 'CANJE'),
    ('CONDUCIR_RENOVACION', 'CONDUCIR_NUEVO', 'RENOVACION'),
    ('CONDUCIR_DUPLICADO', 'CONDUCIR_NUEVO', 'DUPLICADO'),
    ('CONDUCIR_EXTENSION', 'CONDUCIR_NUEVO', 'EXTENSION'),
    -- Contrato (base: CONTRATO_OBRA)
    ('CONTRATO_OBRA', NULL, 'OBRA'),
    ('CONTRATO_SERVICIO', 'CONTRATO_OBRA', 'SERVICIO'),
    ('CONTRATO_SUMINISTRO', 'CONTRATO_OBRA', 'SUMINISTRO'),
    ('CONTRATO_CONCESION', 'CONTRATO_OBRA', 'CONCESION'),
    ('CONTRATO_JOINT_VENTURE', 'CONTRATO_OBRA', 'JOINT_VENTURE'),
    ('CONTRATO_ARRENDAMIENTO', 'CONTRATO_OBRA', 'ARRENDAMIENTO'),
    ('CONTRATO_OTRO', 'CONTRATO_OBRA', 'OTRO'),
    -- Visado (base: PRORROGA_VISADO)
    ('PRORROGA_VISADO', NULL, 'PRORROGA'),
    ('VISADO_ALTERNATIVO', 'PRORROGA_VISADO', 'ALTERNATIVO'),
    ('PERMANENCIA_EXTRANJERIA', 'PRORROGA_VISADO', 'PERMANENCIA'),
    ('SALIDA_VISADO_VENCIDO', 'PRORROGA_VISADO', 'SALIDA_VENCIDO'),
    -- Residencia (base: RESIDENCIA_PRIMERA_VEZ)
    ('RESIDENCIA_PRIMERA_VEZ', NULL, 'PRIMERA_VEZ'),
    ('RESIDENCIA_RENOVACION', 'RESIDENCIA_PRIMERA_VEZ', 'RENOVACION'),
    -- Vehiculos
    ('VEHICULO_PRIMERA_MATRICULACION', NULL, NULL),
    ('VEHICULO_TRANSFERENCIA', NULL, NULL),
    ('VEHICULO_RENOVACION_ITV', NULL, NULL),
    ('VEHICULO_RENOVACION_CUVE', NULL, NULL),
    ('VEHICULO_DUPLICADO_PERMISO', NULL, NULL),
    ('VEHICULO_DUPLICADO_CUVE', NULL, NULL),
    ('VEHICULO_CAMBIO_CARACTERISTICAS', NULL, NULL),
    -- Funcion Publica
    ('FP_VERIFICACION_FUNCIONARIO', NULL, NULL),
    ('FP_CARNET_FUNCIONARIO', NULL, NULL),
    ('FP_PROMOCION_ADMINISTRATIVA', NULL, NULL),
    ('FP_PERMISO_EXTRAORDINARIO', NULL, NULL),
    ('FP_CERTIFICADO_ADMINISTRATIVO', NULL, NULL)
ON CONFLICT (code) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════
-- 3. FK CONSTRAINT — Reject invalid workflow codes at DB level
-- ═══════════════════════════════════════════════════════════════

-- Add FK only if not already exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_sr_valid_workflow_code'
    ) THEN
        ALTER TABLE service_requests
            ADD CONSTRAINT fk_sr_valid_workflow_code
            FOREIGN KEY (workflow_code)
            REFERENCES valid_workflow_codes(code);
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- 4. RESOLUTION TRIGGER — Auto-resolve base codes on INSERT
--    Safety net: if Python resolve_workflow_code() was bypassed,
--    the trigger resolves it using valid_workflow_codes.base_code + form_data keys.
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION fn_resolve_workflow_code()
RETURNS TRIGGER AS $$
DECLARE
    v_base_code VARCHAR(100);
    v_resolution_key VARCHAR(100);
    v_resolved_code VARCHAR(100);
BEGIN
    -- Only act if workflow_code is a base code (has children in valid_workflow_codes)
    SELECT code INTO v_base_code
    FROM valid_workflow_codes
    WHERE code = NEW.workflow_code
      AND base_code IS NULL
      AND EXISTS (
          SELECT 1 FROM valid_workflow_codes vc2
          WHERE vc2.base_code = NEW.workflow_code
      );

    -- Not a base code with children → nothing to do
    IF v_base_code IS NULL THEN
        RETURN NEW;
    END IF;

    -- Extract resolution key from form_data (priority: sub_type > motivo > solicitud_type)
    v_resolution_key := UPPER(COALESCE(
        NULLIF(TRIM(NEW.form_data->>'sub_type'), ''),
        NULLIF(TRIM(NEW.form_data->>'motivo'), ''),
        NULLIF(TRIM(NEW.form_data->>'solicitud_type'), '')
    ));

    IF v_resolution_key IS NULL THEN
        -- No key available, keep base code (legitimate for primera expedicion)
        RETURN NEW;
    END IF;

    -- Look up resolved code
    SELECT code INTO v_resolved_code
    FROM valid_workflow_codes
    WHERE base_code = v_base_code
      AND resolution_key = v_resolution_key
      AND is_active = TRUE;

    IF v_resolved_code IS NOT NULL THEN
        -- Auto-resolve
        NEW.workflow_code := v_resolved_code;
        RAISE LOG 'fn_resolve_workflow_code: % → % (key=%)',
                   v_base_code, v_resolved_code, v_resolution_key;
    END IF;

    -- If no match found, keep original (may be a valid base code like PASAPORTE_NUEVO for EXPEDICION)
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger only if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_resolve_workflow_code'
    ) THEN
        CREATE TRIGGER trg_resolve_workflow_code
            BEFORE INSERT ON service_requests
            FOR EACH ROW
            EXECUTE FUNCTION fn_resolve_workflow_code();
    END IF;
END $$;

COMMENT ON FUNCTION fn_resolve_workflow_code() IS
    'Safety net: auto-resolves base workflow codes (e.g. PASAPORTE_NUEVO → PASAPORTE_DETERIORO) '
    'using form_data keys. Runs BEFORE INSERT as a fallback in case Python resolve_workflow_code() was bypassed.';
