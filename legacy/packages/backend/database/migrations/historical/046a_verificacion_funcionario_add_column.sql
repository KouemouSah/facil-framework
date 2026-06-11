-- Migration: 046a_verificacion_funcionario_add_column.sql
-- Date: 2025-01-12
-- Description: PART 1 - Add verification_data JSONB column to verificacion_funcionario
-- Author: TaxasGE Development Team
-- NOTE: Execute this BEFORE 046b

-- ============================================================================
-- 1. DROP DEPENDENT VIEWS FIRST
-- ============================================================================

DROP VIEW IF EXISTS v_verificaciones_pendientes CASCADE;
DROP VIEW IF EXISTS v_verificacion_stats CASCADE;

-- ============================================================================
-- 2. DROP OLD FUNCTION (will be recreated in 046b)
-- ============================================================================

DROP FUNCTION IF EXISTS process_verificacion_funcionario CASCADE;
DROP FUNCTION IF EXISTS batch_approve_verificaciones CASCADE;

-- ============================================================================
-- 3. ADD verification_data JSONB COLUMN
-- ============================================================================

-- Drop if exists (any type)
ALTER TABLE verificacion_funcionario DROP COLUMN IF EXISTS verification_data;
ALTER TABLE verificacion_funcionario DROP COLUMN IF EXISTS form_data;

-- Create with correct JSONB type
ALTER TABLE verificacion_funcionario
ADD COLUMN verification_data JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN verificacion_funcionario.verification_data IS
'Données complètes: documents (dip, nombramiento/carnet/contrato), extractions OCR, validation croisée';

-- ============================================================================
-- 4. MIGRATE EXISTING DATA (if old columns exist)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'verificacion_funcionario'
        AND column_name = 'documento_id'
    ) THEN
        UPDATE verificacion_funcionario
        SET verification_data = jsonb_build_object(
            'matricula', matricula,
            'dip', CASE
                WHEN documento_id IS NOT NULL THEN jsonb_build_object(
                    'file_id', documento_id::text,
                    'extraction', COALESCE(datos_extraidos_dip, '{}'::jsonb),
                    'migrated_from_legacy', true
                )
                ELSE NULL
            END
        )
        WHERE verification_data = '{}'::jsonb
          AND (documento_id IS NOT NULL OR datos_extraidos_dip IS NOT NULL);

        RAISE NOTICE 'Migrated existing data to verification_data';
    END IF;
END $$;

-- ============================================================================
-- 5. DROP DEPRECATED COLUMNS
-- ============================================================================

ALTER TABLE verificacion_funcionario
DROP CONSTRAINT IF EXISTS verificacion_funcionario_documento_id_fkey;

ALTER TABLE verificacion_funcionario
DROP COLUMN IF EXISTS documento_id;

ALTER TABLE verificacion_funcionario
DROP COLUMN IF EXISTS datos_extraidos_dip;

-- ============================================================================
-- 6. ADD GIN INDEX
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_verificacion_data_gin
ON verificacion_funcionario USING GIN (verification_data);

CREATE INDEX IF NOT EXISTS idx_verificacion_data_matricula
ON verificacion_funcionario ((verification_data->>'matricula'));

-- ============================================================================
-- END OF PART 1 - Now execute 046b
-- ============================================================================
