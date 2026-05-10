-- Migration: 080_seed_identifier_type_translations.sql
-- Description: Add translations for identifier_type_enum and verification_source_enum values
-- Author: Claude Code
-- Date: 2026-01-27

-- =============================================================================
-- IDENTIFIER TYPE ENUM TRANSLATIONS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    -- DNI - Document National d'Identité
    ('enum', 'dni', 'identifier_type_enum',
     'DNI', 'DNI', 'DNI',
     'Documento Nacional de Identidad - Document d''identité national', 'manual'),

    -- Pasaporte
    ('enum', 'pasaporte', 'identifier_type_enum',
     'Pasaporte', 'Passeport', 'Passport',
     'Número de pasaporte', 'manual'),

    -- Permiso de Residencia
    ('enum', 'permiso_residencia', 'identifier_type_enum',
     'Permiso de Residencia', 'Permis de Résidence', 'Residence Permit',
     'Permiso de residencia para extranjeros', 'manual'),

    -- Certificado de Conducir
    ('enum', 'certificado_conducir', 'identifier_type_enum',
     'Certificado de Conducir', 'Permis de Conduire', 'Driver''s License',
     'Licencia de conducción', 'manual'),

    -- NIF
    ('enum', 'nif', 'identifier_type_enum',
     'NIF', 'NIF', 'Tax ID (NIF)',
     'Número de Identificación Fiscal', 'manual'),

    -- Matrícula de Vehículo
    ('enum', 'matricula_vehiculo', 'identifier_type_enum',
     'Matrícula de Vehículo', 'Immatriculation Véhicule', 'Vehicle Registration',
     'Número de matrícula del vehículo', 'manual'),

    -- Matrícula de Funcionario
    ('enum', 'matricula_funcionario', 'identifier_type_enum',
     'Matrícula de Funcionario', 'Matricule Fonctionnaire', 'Civil Servant ID',
     'Número de matrícula del funcionario público', 'manual'),

    -- Número de Nombramiento
    ('enum', 'numero_nombramiento', 'identifier_type_enum',
     'Número de Nombramiento', 'Numéro de Nomination', 'Appointment Number',
     'Número del acto de nombramiento oficial', 'manual'),

    -- Carnet de Funcionario
    ('enum', 'carnet_funcionario', 'identifier_type_enum',
     'Carnet de Funcionario', 'Carte Fonctionnaire', 'Civil Servant Card',
     'Carnet de identificación de funcionario', 'manual'),

    -- CUVE
    ('enum', 'cuve', 'identifier_type_enum',
     'CUVE', 'CUVE', 'CUVE',
     'Código Único de Verificación Electrónica', 'manual'),

    -- Permiso de Circulación
    ('enum', 'permiso_circulacion', 'identifier_type_enum',
     'Permiso de Circulación', 'Permis de Circulation', 'Circulation Permit',
     'Permiso de circulación de vehículos', 'manual'),

    -- Registro Civil
    ('enum', 'registro_civil', 'identifier_type_enum',
     'Registro Civil', 'Registre Civil', 'Civil Registry',
     'Número de inscripción en el registro civil', 'manual'),

    -- Contrato ORNC
    ('enum', 'contrato_ornc', 'identifier_type_enum',
     'Contrato ORNC', 'Contrat ORNC', 'ORNC Contract',
     'Número de contrato con ORNC', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();

-- =============================================================================
-- VERIFICATION SOURCE ENUM TRANSLATIONS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    -- CNEDOGE
    ('enum', 'cnedoge', 'verification_source_enum',
     'CNEDOGE', 'CNEDOGE', 'CNEDOGE',
     'Centro Nacional de Expedición de Documentos de Guinea Ecuatorial', 'manual'),

    -- Tráfico
    ('enum', 'trafico', 'verification_source_enum',
     'Tráfico', 'Trafic', 'Traffic',
     'Dirección General de Tráfico', 'manual'),

    -- Hacienda
    ('enum', 'hacienda', 'verification_source_enum',
     'Hacienda', 'Trésor', 'Treasury',
     'Ministerio de Hacienda y Presupuestos', 'manual'),

    -- Agent Manual
    ('enum', 'agent_manual', 'verification_source_enum',
     'Agente (Manual)', 'Agent (Manuel)', 'Agent (Manual)',
     'Verificación manual por agente', 'manual'),

    -- API Integration
    ('enum', 'api_integration', 'verification_source_enum',
     'API', 'API', 'API',
     'Verificación automática vía integración API', 'manual'),

    -- ORNC
    ('enum', 'ornc', 'verification_source_enum',
     'ORNC', 'ORNC', 'ORNC',
     'Oficina de Registro Notarial y Civil', 'manual'),

    -- Registro Civil
    ('enum', 'registro_civil', 'verification_source_enum',
     'Registro Civil', 'Registre Civil', 'Civil Registry',
     'Registro Civil Nacional', 'manual'),

    -- Registro de Vehículos
    ('enum', 'registro_vehiculos', 'verification_source_enum',
     'Registro de Vehículos', 'Registre des Véhicules', 'Vehicle Registry',
     'Registro Nacional de Vehículos', 'manual'),

    -- Ministerio de Función Pública
    ('enum', 'ministerio_funcion_publica', 'verification_source_enum',
     'Min. Función Pública', 'Min. Fonction Publique', 'Ministry of Public Function',
     'Ministerio de la Función Pública', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();

-- =============================================================================
-- VERIFICATION STATUS ENUM TRANSLATIONS (bonus)
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('enum', 'pending', 'verification_status_enum',
     'Pendiente', 'En attente', 'Pending',
     'Verificación pendiente', 'manual'),

    ('enum', 'in_progress', 'verification_status_enum',
     'En progreso', 'En cours', 'In Progress',
     'Verificación en curso', 'manual'),

    ('enum', 'verified', 'verification_status_enum',
     'Verificado', 'Vérifié', 'Verified',
     'Verificación completada automáticamente', 'manual'),

    ('enum', 'verified_manually', 'verification_status_enum',
     'Verificado manualmente', 'Vérifié manuellement', 'Manually Verified',
     'Verificación completada por agente', 'manual'),

    ('enum', 'verification_failed', 'verification_status_enum',
     'Verificación fallida', 'Échec de vérification', 'Verification Failed',
     'La verificación ha fallado', 'manual'),

    ('enum', 'partial_verification', 'verification_status_enum',
     'Verificación parcial', 'Vérification partielle', 'Partial Verification',
     'Algunos identificadores verificados, otros pendientes', 'manual'),

    ('enum', 'not_found', 'verification_status_enum',
     'No encontrado', 'Non trouvé', 'Not Found',
     'Identificador no encontrado en el sistema', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 080: Inserted/updated translations for identifier_type_enum, verification_source_enum, and verification_status_enum';
END $$;
