-- ============================================================================
-- Migration 056: Add workflow_codes to entities table
-- ============================================================================
-- Purpose:
--   Add workflow_codes JSONB column to entities table to define which workflows
--   each entity/department/ministry handles. This enables automatic menu
--   attribution for agents based on their assigned entity.
--
-- Architecture:
--   - entities.workflow_codes: Array of workflow codes handled by this entity
--   - Agents inherit workflows from their entity_id automatically
--   - agent_profiles.specializations can override for individual agents
--
-- Hierarchy:
--   1. Agent with specializations -> uses specializations (explicit)
--   2. Agent without specializations -> inherits from entity.workflow_codes
--   3. Entity without workflow_codes -> inherits from parent entity
--   4. Fallback -> all workflows matching workflows.entity_code
--
-- Date: 2026-01-16
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ADD COLUMN workflow_codes TO entities
-- ============================================================================

ALTER TABLE entities
ADD COLUMN IF NOT EXISTS workflow_codes JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN entities.workflow_codes IS
'Array of workflow codes this entity/department/ministry handles. Agents assigned via entity_id inherit these workflows automatically. Empty array means inherit from parent or match all workflows with same entity_code.';

-- ============================================================================
-- 2. CREATE GIN INDEX FOR JSONB SEARCH
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_entities_workflow_codes
ON entities USING GIN (workflow_codes jsonb_path_ops);

-- ============================================================================
-- 3. SEED WORKFLOW_CODES FOR EXISTING TOP-LEVEL ENTITIES
-- ============================================================================
-- These match the workflows seeded in migration 028_workflows_and_appointments.sql

-- CNEDOGE: Pasaportes + Residencias (shared with EXTRANJERIA)
UPDATE entities
SET workflow_codes = '[
    "PASAPORTE_NUEVO",
    "PASAPORTE_RENOVACION",
    "PASAPORTE_PERDIDA",
    "PASAPORTE_ROBO",
    "PASAPORTE_DETERIORO"
]'::jsonb
WHERE code = 'CNEDOGE' AND workflow_codes = '[]'::jsonb;

-- EXTRANJERIA: Residencias
UPDATE entities
SET workflow_codes = '[
    "RESIDENCIA_PRIMERA_VEZ",
    "RESIDENCIA_RENOVACION",
    "RESIDENCIA_DUPLICADO",
    "RESIDENCIA_CAMBIO_DATOS",
    "RESIDENCIA_REAGRUPACION"
]'::jsonb
WHERE code = 'EXTRANJERIA' AND workflow_codes = '[]'::jsonb;

-- DGT: Vehiculos + Conducir
UPDATE entities
SET workflow_codes = '[
    "VEHICULO_PRIMERA_MATRICULACION",
    "VEHICULO_TRANSFERENCIA",
    "VEHICULO_RENOVACION_CUVE",
    "VEHICULO_DUPLICADO_PERMISO",
    "VEHICULO_DUPLICADO_CUVE",
    "VEHICULO_CAMBIO_CARACTERISTICAS",
    "CONDUCIR_NUEVO",
    "CONDUCIR_CANJE",
    "CONDUCIR_RENOVACION",
    "CONDUCIR_DUPLICADO",
    "CONDUCIR_EXTENSION"
]'::jsonb
WHERE code = 'DGT' AND workflow_codes = '[]'::jsonb;

-- ITVE: ITV only
UPDATE entities
SET workflow_codes = '["VEHICULO_RENOVACION_ITV"]'::jsonb
WHERE code = 'ITVE' AND workflow_codes = '[]'::jsonb;

-- ONRC: Contratos
UPDATE entities
SET workflow_codes = '[
    "CONTRATO_OBRA",
    "CONTRATO_SERVICIO",
    "CONTRATO_SUMINISTRO",
    "CONTRATO_CONCESION",
    "CONTRATO_JOINT_VENTURE",
    "CONTRATO_ARRENDAMIENTO",
    "CONTRATO_OTRO"
]'::jsonb
WHERE code = 'ONRC' AND workflow_codes = '[]'::jsonb;

-- MINFP: Funcion Publica
UPDATE entities
SET workflow_codes = '[
    "FP_VERIFICACION_FUNCIONARIO",
    "FP_CARNET_FUNCIONARIO",
    "FP_PROMOCION_ADMINISTRATIVA",
    "FP_PERMISO_EXTRAORDINARIO",
    "FP_CERTIFICADO_ADMINISTRATIVO"
]'::jsonb
WHERE code = 'MINFP' AND workflow_codes = '[]'::jsonb;

-- ============================================================================
-- 4. CREATE SAMPLE DEPARTMENTS WITH SPECIFIC WORKFLOWS
-- ============================================================================
-- Based on test-data/agent_menu.md structure

-- CNEDOGE Departments (if they don't exist)
INSERT INTO entities (code, name, description, entity_type, parent_entity_id, workflow_codes, is_active)
SELECT
    'CNEDOGE_PASAPORTES',
    'Service des Passeports',
    'Département de gestion des demandes de passeport',
    'department'::entity_type_enum,
    (SELECT id FROM entities WHERE code = 'CNEDOGE'),
    '["PASAPORTE_NUEVO", "PASAPORTE_RENOVACION", "PASAPORTE_PERDIDA", "PASAPORTE_ROBO", "PASAPORTE_DETERIORO"]'::jsonb,
    true
WHERE NOT EXISTS (SELECT 1 FROM entities WHERE code = 'CNEDOGE_PASAPORTES');

INSERT INTO entities (code, name, description, entity_type, parent_entity_id, workflow_codes, is_active)
SELECT
    'CNEDOGE_RESIDENCIAS',
    'Service des Résidences',
    'Département de gestion des permis de résidence',
    'department'::entity_type_enum,
    (SELECT id FROM entities WHERE code = 'CNEDOGE'),
    '["RESIDENCIA_PRIMERA_VEZ", "RESIDENCIA_RENOVACION", "RESIDENCIA_DUPLICADO", "RESIDENCIA_CAMBIO_DATOS", "RESIDENCIA_REAGRUPACION"]'::jsonb,
    true
WHERE NOT EXISTS (SELECT 1 FROM entities WHERE code = 'CNEDOGE_RESIDENCIAS');

-- DGT Departments
INSERT INTO entities (code, name, description, entity_type, parent_entity_id, workflow_codes, is_active)
SELECT
    'DGT_VEHICULOS',
    'Service des Véhicules',
    'Département de gestion des immatriculations et documents véhicules',
    'department'::entity_type_enum,
    (SELECT id FROM entities WHERE code = 'DGT'),
    '["VEHICULO_PRIMERA_MATRICULACION", "VEHICULO_TRANSFERENCIA", "VEHICULO_RENOVACION_CUVE", "VEHICULO_DUPLICADO_PERMISO", "VEHICULO_DUPLICADO_CUVE", "VEHICULO_CAMBIO_CARACTERISTICAS"]'::jsonb,
    true
WHERE NOT EXISTS (SELECT 1 FROM entities WHERE code = 'DGT_VEHICULOS');

INSERT INTO entities (code, name, description, entity_type, parent_entity_id, workflow_codes, is_active)
SELECT
    'DGT_PERMISOS',
    'Service des Permis de Conduire',
    'Département de gestion des permis de conduire',
    'department'::entity_type_enum,
    (SELECT id FROM entities WHERE code = 'DGT'),
    '["CONDUCIR_NUEVO", "CONDUCIR_CANJE", "CONDUCIR_RENOVACION", "CONDUCIR_DUPLICADO", "CONDUCIR_EXTENSION"]'::jsonb,
    true
WHERE NOT EXISTS (SELECT 1 FROM entities WHERE code = 'DGT_PERMISOS');

-- ============================================================================
-- 5. HELPER FUNCTION: Get workflows for an entity (with inheritance)
-- ============================================================================

CREATE OR REPLACE FUNCTION get_entity_workflows(p_entity_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_entity RECORD;
    v_workflows JSONB;
BEGIN
    -- Get the entity
    SELECT id, code, workflow_codes, parent_entity_id, entity_type
    INTO v_entity
    FROM entities
    WHERE id = p_entity_id AND is_active = true;

    IF NOT FOUND THEN
        RETURN '[]'::jsonb;
    END IF;

    -- Check if entity has workflow_codes defined
    IF v_entity.workflow_codes IS NOT NULL AND jsonb_array_length(v_entity.workflow_codes) > 0 THEN
        RETURN v_entity.workflow_codes;
    END IF;

    -- If department, try to inherit from parent
    IF v_entity.entity_type = 'department' AND v_entity.parent_entity_id IS NOT NULL THEN
        SELECT workflow_codes INTO v_workflows
        FROM entities
        WHERE id = v_entity.parent_entity_id AND is_active = true;

        IF v_workflows IS NOT NULL AND jsonb_array_length(v_workflows) > 0 THEN
            RETURN v_workflows;
        END IF;
    END IF;

    -- Fallback: get all workflows matching entity_code
    SELECT jsonb_agg(code ORDER BY display_order)
    INTO v_workflows
    FROM workflows
    WHERE entity_code = v_entity.code AND is_active = true;

    RETURN COALESCE(v_workflows, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_entity_workflows(UUID) IS
'Returns workflow codes for an entity with inheritance: entity workflows -> parent workflows -> workflows.entity_code match';

-- ============================================================================
-- 6. HELPER FUNCTION: Get workflows for an agent (with specialization override)
-- ============================================================================

CREATE OR REPLACE FUNCTION get_agent_available_workflows(p_agent_profile_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_agent RECORD;
    v_workflows JSONB;
BEGIN
    -- Get agent profile
    SELECT id, entity_id, specializations
    INTO v_agent
    FROM agent_profiles
    WHERE id = p_agent_profile_id AND is_active = true;

    IF NOT FOUND THEN
        RETURN '[]'::jsonb;
    END IF;

    -- If agent has explicit specializations, use them
    IF v_agent.specializations IS NOT NULL AND jsonb_array_length(v_agent.specializations) > 0 THEN
        RETURN v_agent.specializations;
    END IF;

    -- Otherwise, inherit from entity
    IF v_agent.entity_id IS NOT NULL THEN
        RETURN get_entity_workflows(v_agent.entity_id);
    END IF;

    -- No entity assigned, return empty
    RETURN '[]'::jsonb;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_agent_available_workflows(UUID) IS
'Returns workflow codes for an agent: explicit specializations -> entity workflows (with inheritance)';

-- ============================================================================
-- 7. VIEW: Entities with resolved workflows
-- ============================================================================

CREATE OR REPLACE VIEW v_entities_with_workflows AS
SELECT
    e.id,
    e.code,
    e.name,
    e.description,
    e.entity_type,
    e.parent_entity_id,
    pe.code as parent_entity_code,
    pe.name as parent_entity_name,
    e.ministry_id,
    m.name_es as ministry_name,
    e.workflow_codes as direct_workflow_codes,
    get_entity_workflows(e.id) as resolved_workflow_codes,
    jsonb_array_length(get_entity_workflows(e.id)) as workflow_count,
    e.is_active,
    e.created_at,
    e.updated_at
FROM entities e
LEFT JOIN entities pe ON pe.id = e.parent_entity_id
LEFT JOIN ministries m ON m.id = e.ministry_id
WHERE e.is_active = true;

COMMENT ON VIEW v_entities_with_workflows IS
'Entities with both direct and resolved (inherited) workflow codes';

-- ============================================================================
-- 8. VALIDATION FUNCTION: Check workflow codes exist
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_entity_workflow_codes()
RETURNS TRIGGER AS $$
DECLARE
    v_code TEXT;
    v_invalid_codes TEXT[];
BEGIN
    -- Skip if workflow_codes is NULL or empty
    IF NEW.workflow_codes IS NULL OR jsonb_array_length(NEW.workflow_codes) = 0 THEN
        RETURN NEW;
    END IF;

    -- Check each workflow code exists in workflows table OR is a valid WorkflowCode enum
    -- We check against workflows table (which contains both predefined and generic workflows)
    SELECT array_agg(code)
    INTO v_invalid_codes
    FROM (
        SELECT jsonb_array_elements_text(NEW.workflow_codes) as code
    ) codes
    WHERE code NOT IN (SELECT w.code FROM workflows w WHERE w.is_active = true);

    IF array_length(v_invalid_codes, 1) > 0 THEN
        RAISE EXCEPTION 'Invalid workflow codes: %. Codes must exist in workflows table.',
            array_to_string(v_invalid_codes, ', ');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_entity_workflow_codes() IS
'Validates that workflow_codes in entities table reference existing workflows';

-- Create trigger for validation on INSERT and UPDATE
CREATE TRIGGER tr_validate_entity_workflow_codes
    BEFORE INSERT OR UPDATE OF workflow_codes ON entities
    FOR EACH ROW
    EXECUTE FUNCTION validate_entity_workflow_codes();

-- ============================================================================
-- 9. VIEW: All valid workflow codes (predefined + generic)
-- ============================================================================

CREATE OR REPLACE VIEW v_available_workflow_codes AS
SELECT
    w.code,
    w.name_es,
    w.category,
    w.entity_code,
    w.workflow_type,
    w.is_generic,
    CASE
        WHEN w.is_generic = false THEN 'predefined'
        ELSE 'generic'
    END as source_type,
    w.is_active
FROM workflows w
WHERE w.is_active = true
ORDER BY w.entity_code, w.display_order;

COMMENT ON VIEW v_available_workflow_codes IS
'All valid workflow codes that can be assigned to entities. source_type indicates if workflow has a Python class (predefined) or uses GenericWorkflow (generic)';

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (run separately if needed)
-- ============================================================================
-- BEGIN;
-- DROP TRIGGER IF EXISTS tr_validate_entity_workflow_codes ON entities;
-- DROP FUNCTION IF EXISTS validate_entity_workflow_codes();
-- DROP VIEW IF EXISTS v_available_workflow_codes;
-- DROP VIEW IF EXISTS v_entities_with_workflows;
-- DROP FUNCTION IF EXISTS get_agent_available_workflows(UUID);
-- DROP FUNCTION IF EXISTS get_entity_workflows(UUID);
-- DROP INDEX IF EXISTS idx_entities_workflow_codes;
-- ALTER TABLE entities DROP COLUMN IF EXISTS workflow_codes;
-- DELETE FROM entities WHERE code IN ('CNEDOGE_PASAPORTES', 'CNEDOGE_RESIDENCIAS', 'DGT_VEHICULOS', 'DGT_PERMISOS');
-- COMMIT;
