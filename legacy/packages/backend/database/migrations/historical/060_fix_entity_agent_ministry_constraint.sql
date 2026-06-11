-- =============================================================================
-- Migration 060: Fix entity_agent ministry constraint
-- =============================================================================
--
-- Problem: The validate_agent_assignment() trigger incorrectly prevents
-- entity_agents from being assigned to entities that have a parent ministry.
--
-- Correct architecture:
-- - entity_agent: agent working for an ENTITY (with or without ministry parent)
-- - ministry_agent: agent working directly for a MINISTRY (not via an entity)
--
-- An entity CAN have a parent ministry (hierarchical structure).
-- An entity_agent assigned to such entity should inherit the ministry_id
-- for reporting/filtering purposes, but should NOT be blocked.
--
-- Date: 2025-01-18
-- =============================================================================

-- Drop existing trigger
DROP TRIGGER IF EXISTS trg_validate_agent_assignment ON agent_profiles;

-- Recreate the function with corrected logic
CREATE OR REPLACE FUNCTION validate_agent_assignment()
RETURNS TRIGGER AS $validate_agent$
DECLARE
    v_entity_ministry_id INTEGER;
    v_entity_has_ministry BOOLEAN;
BEGIN
    v_entity_has_ministry := FALSE;

    -- If agent is assigned to an entity, get the entity's ministry (if any)
    IF NEW.entity_id IS NOT NULL THEN
        SELECT e.ministry_id INTO v_entity_ministry_id
        FROM entities e
        WHERE e.id = NEW.entity_id;

        v_entity_has_ministry := v_entity_ministry_id IS NOT NULL;

        -- Auto-populate ministry_id from entity's parent ministry
        IF v_entity_has_ministry THEN
            IF NEW.ministry_id IS NULL THEN
                -- Inherit ministry from entity
                NEW.ministry_id := v_entity_ministry_id;
            ELSIF NEW.ministry_id != v_entity_ministry_id THEN
                -- If ministry_id is explicitly set, it must match entity's ministry
                RAISE EXCEPTION 'Agent ministry_id (%) must match entity ministry_id (%)',
                    NEW.ministry_id, v_entity_ministry_id;
            END IF;
        END IF;
    END IF;

    -- Validate based on agent_type
    IF NEW.agent_type = 'entity_agent' THEN
        -- entity_agent MUST have an entity_id
        IF NEW.entity_id IS NULL THEN
            RAISE EXCEPTION 'entity_agent must have entity_id set';
        END IF;
        -- REMOVED: The constraint preventing entity_agent on entities with ministry
        -- entity_agents CAN work for entities that have a parent ministry
        -- The ministry_id is inherited automatically for filtering purposes

    ELSIF NEW.agent_type = 'ministry_agent' THEN
        -- ministry_agent works for a ministry, either:
        -- 1. Directly (ministry_id set, no entity_id), OR
        -- 2. Via an entity that belongs to a ministry (entity_id set, ministry inherited)
        IF NEW.ministry_id IS NULL THEN
            RAISE EXCEPTION 'ministry_agent must be linked to a ministry (directly or via entity)';
        END IF;
    END IF;

    RETURN NEW;
END;
$validate_agent$ LANGUAGE plpgsql;

-- Recreate the trigger
CREATE TRIGGER trg_validate_agent_assignment
    BEFORE INSERT OR UPDATE ON agent_profiles
    FOR EACH ROW
    EXECUTE FUNCTION validate_agent_assignment();

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 060: Fixed entity_agent ministry constraint - entity_agents can now be assigned to entities with parent ministries';
END $$;
