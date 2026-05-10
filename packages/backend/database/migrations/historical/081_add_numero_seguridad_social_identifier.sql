-- Migration: 081_add_numero_seguridad_social_identifier.sql
-- Description: Add numero_seguridad_social to identifier_type_enum
-- Author: Claude Code
-- Date: 2026-01-27

-- =============================================================================
-- 1. ADD NEW VALUE TO identifier_type_enum
-- =============================================================================

ALTER TYPE identifier_type_enum ADD VALUE IF NOT EXISTS 'numero_seguridad_social';

-- =============================================================================
-- 2. ADD TRANSLATION FOR THE NEW VALUE
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('enum', 'numero_seguridad_social', 'identifier_type_enum',
     'N° Seguridad Social', 'N° Sécurité Sociale', 'Social Security Number',
     'Número de afiliación a la seguridad social', 'manual')
ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();

-- =============================================================================
-- 3. ADD seguridad_social TO verification_source_enum (if needed)
-- =============================================================================

ALTER TYPE verification_source_enum ADD VALUE IF NOT EXISTS 'seguridad_social';

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('enum', 'seguridad_social', 'verification_source_enum',
     'Seguridad Social', 'Sécurité Sociale', 'Social Security',
     'Instituto Nacional de la Seguridad Social', 'manual')
ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Log
DO $$
BEGIN
    RAISE NOTICE 'Migration 081: Added numero_seguridad_social to identifier_type_enum and seguridad_social to verification_source_enum';
END $$;
