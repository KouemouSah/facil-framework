-- ============================================================================
-- Migration 057: Normalize workflow_codes to UPPERCASE
-- ============================================================================
-- Purpose:
--   Fix inconsistency where workflow_document_requirements, workflow_tariffs,
--   and workflow_supplement_config use lowercase codes while workflows table
--   uses UPPERCASE codes.
--
-- Tables affected:
--   - workflow_document_requirements.workflow_code
--   - workflow_tariffs.workflow_code
--   - workflow_supplement_config.workflow_code
--
-- After normalization, add FK constraints for referential integrity.
--
-- Date: 2026-01-16
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE MAPPING TABLE FOR CODE CONVERSION
-- ============================================================================

CREATE TEMP TABLE workflow_code_mapping (
    old_code VARCHAR(100),
    new_code VARCHAR(100)
);

INSERT INTO workflow_code_mapping (old_code, new_code) VALUES
    -- PASAPORTE
    ('pasaporte_nuevo', 'PASAPORTE_NUEVO'),
    ('pasaporte_renovacion', 'PASAPORTE_RENOVACION'),
    ('pasaporte_perdida', 'PASAPORTE_PERDIDA'),
    ('pasaporte_robo', 'PASAPORTE_ROBO'),
    ('pasaporte_deterioro', 'PASAPORTE_DETERIORO'),

    -- RESIDENCIA
    ('residencia', 'RESIDENCIA_PRIMERA_VEZ'),
    ('residencia_renovacion', 'RESIDENCIA_RENOVACION'),
    ('residencia_duplicado', 'RESIDENCIA_DUPLICADO'),
    ('residencia_cambio_datos', 'RESIDENCIA_CAMBIO_DATOS'),
    ('residencia_reagrupacion', 'RESIDENCIA_REAGRUPACION'),

    -- FUNCION PUBLICA
    ('carnet_funcionario', 'FP_CARNET_FUNCIONARIO'),
    ('certificado_administrativo', 'FP_CERTIFICADO_ADMINISTRATIVO'),
    ('permiso_extraordinario', 'FP_PERMISO_EXTRAORDINARIO'),
    ('promocion_administrativa', 'FP_PROMOCION_ADMINISTRATIVA'),
    ('verificacion_funcionario', 'FP_VERIFICACION_FUNCIONARIO'),

    -- CONDUCIR
    ('certificado_conducir_nuevo', 'CONDUCIR_NUEVO'),
    ('certificado_conducir_renovacion', 'CONDUCIR_RENOVACION'),
    ('conducir_canje', 'CONDUCIR_CANJE'),
    ('conducir_duplicado', 'CONDUCIR_DUPLICADO'),
    ('conducir_extension', 'CONDUCIR_EXTENSION'),

    -- VEHICULO
    ('transferencia_vehiculo', 'VEHICULO_TRANSFERENCIA'),
    ('renovacion_vehiculo', 'VEHICULO_RENOVACION_CUVE'),
    ('vehiculo_matriculacion', 'VEHICULO_PRIMERA_MATRICULACION'),
    ('vehiculo_itv', 'VEHICULO_RENOVACION_ITV'),
    ('vehiculo_duplicado_permiso', 'VEHICULO_DUPLICADO_PERMISO'),
    ('vehiculo_duplicado_cuve', 'VEHICULO_DUPLICADO_CUVE'),
    ('vehiculo_cambio_caracteristicas', 'VEHICULO_CAMBIO_CARACTERISTICAS'),
    ('cuve', 'VEHICULO_RENOVACION_CUVE'),

    -- CONTRATO
    ('contrato_onrc', 'CONTRATO_OBRA'),
    ('contrato_obra', 'CONTRATO_OBRA'),
    ('contrato_servicio', 'CONTRATO_SERVICIO'),
    ('contrato_suministro', 'CONTRATO_SUMINISTRO'),
    ('contrato_concesion', 'CONTRATO_CONCESION'),
    ('contrato_joint_venture', 'CONTRATO_JOINT_VENTURE'),
    ('contrato_arrendamiento', 'CONTRATO_ARRENDAMIENTO'),
    ('contrato_otro', 'CONTRATO_OTRO');

-- ============================================================================
-- 2. UPDATE workflow_document_requirements
-- ============================================================================

UPDATE workflow_document_requirements wdr
SET workflow_code = m.new_code
FROM workflow_code_mapping m
WHERE wdr.workflow_code = m.old_code;

-- Also handle any already uppercase codes that don't need mapping
-- (in case some were already correct)

-- ============================================================================
-- 3. UPDATE workflow_tariffs
-- ============================================================================

UPDATE workflow_tariffs wt
SET workflow_code = m.new_code
FROM workflow_code_mapping m
WHERE wt.workflow_code = m.old_code;

-- ============================================================================
-- 4. UPDATE workflow_supplement_config
-- ============================================================================

UPDATE workflow_supplement_config wsc
SET workflow_code = m.new_code
FROM workflow_code_mapping m
WHERE wsc.workflow_code = m.old_code;

-- ============================================================================
-- 5. VERIFY NO ORPHAN CODES REMAIN
-- ============================================================================
-- Log any codes that couldn't be mapped (for manual review)

DO $$
DECLARE
    orphan_count INTEGER;
    orphan_codes TEXT;
BEGIN
    -- Check workflow_document_requirements
    SELECT COUNT(*), string_agg(DISTINCT workflow_code, ', ')
    INTO orphan_count, orphan_codes
    FROM workflow_document_requirements
    WHERE workflow_code NOT IN (SELECT code FROM workflows);

    IF orphan_count > 0 THEN
        RAISE WARNING 'workflow_document_requirements has % orphan codes: %', orphan_count, orphan_codes;
    END IF;

    -- Check workflow_tariffs
    SELECT COUNT(*), string_agg(DISTINCT workflow_code, ', ')
    INTO orphan_count, orphan_codes
    FROM workflow_tariffs
    WHERE workflow_code NOT IN (SELECT code FROM workflows);

    IF orphan_count > 0 THEN
        RAISE WARNING 'workflow_tariffs has % orphan codes: %', orphan_count, orphan_codes;
    END IF;

    -- Check workflow_supplement_config
    SELECT COUNT(*), string_agg(DISTINCT workflow_code, ', ')
    INTO orphan_count, orphan_codes
    FROM workflow_supplement_config
    WHERE workflow_code NOT IN (SELECT code FROM workflows);

    IF orphan_count > 0 THEN
        RAISE WARNING 'workflow_supplement_config has % orphan codes: %', orphan_count, orphan_codes;
    END IF;
END $$;

-- ============================================================================
-- 6. ADD FK CONSTRAINTS (only if no orphans)
-- ============================================================================
-- Note: These will fail if orphan codes exist. That's intentional.
-- If they fail, fix the orphan codes first.

-- FK for workflow_document_requirements
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_wdr_workflow_code'
    ) THEN
        -- Only add FK if all codes exist in workflows
        IF NOT EXISTS (
            SELECT 1 FROM workflow_document_requirements
            WHERE workflow_code NOT IN (SELECT code FROM workflows)
        ) THEN
            ALTER TABLE workflow_document_requirements
            ADD CONSTRAINT fk_wdr_workflow_code
            FOREIGN KEY (workflow_code) REFERENCES workflows(code)
            ON UPDATE CASCADE ON DELETE CASCADE;

            RAISE NOTICE 'Added FK constraint to workflow_document_requirements';
        ELSE
            RAISE WARNING 'Cannot add FK to workflow_document_requirements - orphan codes exist';
        END IF;
    END IF;
END $$;

-- FK for workflow_tariffs
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_wt_workflow_code'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM workflow_tariffs
            WHERE workflow_code NOT IN (SELECT code FROM workflows)
        ) THEN
            ALTER TABLE workflow_tariffs
            ADD CONSTRAINT fk_wt_workflow_code
            FOREIGN KEY (workflow_code) REFERENCES workflows(code)
            ON UPDATE CASCADE ON DELETE CASCADE;

            RAISE NOTICE 'Added FK constraint to workflow_tariffs';
        ELSE
            RAISE WARNING 'Cannot add FK to workflow_tariffs - orphan codes exist';
        END IF;
    END IF;
END $$;

-- FK for workflow_supplement_config
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_wsc_workflow_code'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM workflow_supplement_config
            WHERE workflow_code NOT IN (SELECT code FROM workflows)
        ) THEN
            ALTER TABLE workflow_supplement_config
            ADD CONSTRAINT fk_wsc_workflow_code
            FOREIGN KEY (workflow_code) REFERENCES workflows(code)
            ON UPDATE CASCADE ON DELETE CASCADE;

            RAISE NOTICE 'Added FK constraint to workflow_supplement_config';
        ELSE
            RAISE WARNING 'Cannot add FK to workflow_supplement_config - orphan codes exist';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- 7. UPDATE COMMENTS
-- ============================================================================

COMMENT ON COLUMN workflow_document_requirements.workflow_code IS
'Code du workflow (UPPERCASE). Must match workflows.code. Ex: PASAPORTE_NUEVO';

COMMENT ON COLUMN workflow_tariffs.workflow_code IS
'Code du workflow (UPPERCASE). Must match workflows.code. Ex: PASAPORTE_NUEVO';

COMMENT ON COLUMN workflow_supplement_config.workflow_code IS
'Code du workflow (UPPERCASE). Must match workflows.code. Ex: PASAPORTE_NUEVO';

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (run separately if needed)
-- ============================================================================
-- Note: Rolling back FK constraints is easy, but rolling back the code changes
-- requires the reverse mapping. Consider backing up data before running.
--
-- BEGIN;
-- ALTER TABLE workflow_document_requirements DROP CONSTRAINT IF EXISTS fk_wdr_workflow_code;
-- ALTER TABLE workflow_tariffs DROP CONSTRAINT IF EXISTS fk_wt_workflow_code;
-- ALTER TABLE workflow_supplement_config DROP CONSTRAINT IF EXISTS fk_wsc_workflow_code;
-- COMMIT;
