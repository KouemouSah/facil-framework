-- Migration 312: Recurring mission templates
--
-- Supervisors can create templates to auto-generate missions on a schedule.
-- Cron job (mission-auto-create) runs daily, creates missions for matching templates.

BEGIN;

CREATE TABLE IF NOT EXISTS mission_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id),
    entity_location_id UUID NOT NULL REFERENCES entity_locations(id),
    created_by UUID NOT NULL REFERENCES users(id),

    -- Template config
    name VARCHAR(200) NOT NULL,
    recurrence VARCHAR(20) NOT NULL CHECK (recurrence IN ('daily', 'weekly', 'biweekly', 'monthly')),
    day_of_week INT CHECK (day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)),
    -- 0=Monday, 6=Sunday (ISO 8601). Required for weekly/biweekly.
    day_of_month INT CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 28)),
    -- Required for monthly. Max 28 to avoid month-end issues.

    -- Mission defaults
    zone_ids UUID[],
    default_agent_ids UUID[], -- agent user_ids to auto-assign
    target_inspections_per_agent INT NOT NULL DEFAULT 10 CHECK (target_inspections_per_agent > 0 AND target_inspections_per_agent <= 100),
    notes TEXT,

    -- State
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_created_at TIMESTAMPTZ, -- last time a mission was created from this template
    last_created_mission_id UUID REFERENCES field_missions(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mt_entity ON mission_templates(entity_id, is_active);
CREATE INDEX IF NOT EXISTS idx_mt_recurrence ON mission_templates(recurrence) WHERE is_active = true;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION trg_mission_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at_mission_templates ON mission_templates;
CREATE TRIGGER set_updated_at_mission_templates
    BEFORE UPDATE ON mission_templates
    FOR EACH ROW EXECUTE FUNCTION trg_mission_templates_updated_at();

COMMIT;
