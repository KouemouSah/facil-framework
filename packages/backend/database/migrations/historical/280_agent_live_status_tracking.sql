-- ============================================================================
-- Migration 280: Agent Live Status Tracking — Phase 8 Real-Time View
-- ============================================================================
-- Adds last_activity_at to agent_profiles for real-time agent status.
-- Trigger on field_inspections INSERT/UPDATE auto-updates agent activity.
-- Partial index for supervisor live-status queries.
--
-- Agent status tiers (derived at query time, not stored):
--   ACTIVE  = last_activity_at within 2 hours
--   IDLE    = last_activity_at between 2-4 hours
--   OFFLINE = last_activity_at > 4 hours or NULL
--
-- Dependencies: 249 (field_inspections), 277 (field_missions)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Add last_activity_at to agent_profiles
-- ============================================================================

ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ DEFAULT NULL;

COMMENT ON COLUMN agent_profiles.last_activity_at IS
  'Last time agent performed any action (inspection, login, etc). Updated by trigger.';

-- ============================================================================
-- 2. Trigger function: update agent last_activity_at on inspection changes
-- ============================================================================

CREATE OR REPLACE FUNCTION trg_update_agent_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE agent_profiles
    SET last_activity_at = NOW(),
        updated_at = NOW()
    WHERE user_id = NEW.agent_id
      AND is_active = true;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- On INSERT (new inspection started)
DROP TRIGGER IF EXISTS trg_fi_agent_activity_insert ON field_inspections;
CREATE TRIGGER trg_fi_agent_activity_insert
    AFTER INSERT ON field_inspections
    FOR EACH ROW
    EXECUTE FUNCTION trg_update_agent_activity();

-- On UPDATE (inspection modified — photo, GPS, complete, etc.)
DROP TRIGGER IF EXISTS trg_fi_agent_activity_update ON field_inspections;
CREATE TRIGGER trg_fi_agent_activity_update
    AFTER UPDATE ON field_inspections
    FOR EACH ROW
    WHEN (OLD.updated_at IS DISTINCT FROM NEW.updated_at)
    EXECUTE FUNCTION trg_update_agent_activity();

-- ============================================================================
-- 3. Trigger: update on mission agent status change
-- ============================================================================

CREATE OR REPLACE FUNCTION trg_update_mission_agent_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE agent_profiles
    SET last_activity_at = NOW(),
        updated_at = NOW()
    WHERE user_id = NEW.agent_id
      AND is_active = true;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_fma_agent_activity ON field_mission_agents;
CREATE TRIGGER trg_fma_agent_activity
    AFTER INSERT OR UPDATE ON field_mission_agents
    FOR EACH ROW
    EXECUTE FUNCTION trg_update_mission_agent_activity();

-- ============================================================================
-- 4. Partial index for live-status queries
-- ============================================================================
-- Supervisor queries: WHERE entity_id = $1 AND is_active = true
-- Sorted by last_activity_at for status tier calculation

CREATE INDEX IF NOT EXISTS idx_ap_live_status
    ON agent_profiles (entity_id, last_activity_at DESC NULLS LAST)
    WHERE is_active = true;

-- ============================================================================
-- 5. Backfill last_activity_at from sessions.last_activity
-- ============================================================================
-- Use the most recent session activity per user as initial value

UPDATE agent_profiles ap
SET last_activity_at = sub.last_activity
FROM (
    SELECT s.user_id, MAX(s.last_activity) as last_activity
    FROM sessions s
    WHERE s.status = 'active'
      AND s.last_activity IS NOT NULL
    GROUP BY s.user_id
) sub
WHERE ap.user_id = sub.user_id
  AND ap.is_active = true
  AND (ap.last_activity_at IS NULL OR ap.last_activity_at < sub.last_activity);

-- ============================================================================
-- 6. System rule: configurable thresholds for agent status tiers
-- ============================================================================

INSERT INTO system_rules (rule_code, rule_category, rule_value, value_type,
                          name_es, name_fr, name_en, description, is_active, effective_from)
VALUES
    ('AGENT_STATUS_IDLE_MINUTES', 'workflow', '120'::jsonb, 'number',
     'Minutos para estado inactivo', 'Minutes pour statut inactif', 'Minutes for idle status',
     'Agent is IDLE after this many minutes without activity (default 120 = 2h)', true, CURRENT_DATE),
    ('AGENT_STATUS_OFFLINE_MINUTES', 'workflow', '240'::jsonb, 'number',
     'Minutos para estado desconectado', 'Minutes pour statut hors ligne', 'Minutes for offline status',
     'Agent is OFFLINE after this many minutes without activity (default 240 = 4h)', true, CURRENT_DATE)
ON CONFLICT (rule_code) DO NOTHING;

COMMIT;
