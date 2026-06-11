-- Migration 135: Agent Workflow Proficiency
-- Per-agent, per-workflow performance tracking for multi-criteria scoring.
-- Updated by feedback loop on each completion/escalation.
-- Feeds: scoring engine, auto-specializations, escalation prédictive.

BEGIN;

CREATE TABLE IF NOT EXISTS agent_workflow_proficiency (
    agent_profile_id UUID NOT NULL REFERENCES agent_profiles(id) ON DELETE CASCADE,
    workflow_code TEXT NOT NULL,

    -- Lifetime counters
    completions_total INTEGER NOT NULL DEFAULT 0,
    escalations_total INTEGER NOT NULL DEFAULT 0,

    -- 30-day rolling window (recalculated by daily cron)
    completions_30d INTEGER NOT NULL DEFAULT 0,
    escalations_30d INTEGER NOT NULL DEFAULT 0,

    -- Computed metrics (updated on each completion/escalation)
    success_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
    avg_processing_hours NUMERIC(8,2) NOT NULL DEFAULT 0,

    -- Timestamps
    last_completed_at TIMESTAMPTZ,
    last_escalated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (agent_profile_id, workflow_code)
);

-- Index for batch-fetching all agents for a given workflow (used by scoring engine)
CREATE INDEX IF NOT EXISTS idx_awp_workflow
    ON agent_workflow_proficiency(workflow_code);

-- Index for daily rollup cron (scans all rows)
CREATE INDEX IF NOT EXISTS idx_awp_updated
    ON agent_workflow_proficiency(updated_at);

COMMENT ON TABLE agent_workflow_proficiency IS
    'Per-agent, per-workflow performance metrics. Feeds multi-criteria scoring and auto-specializations.';

COMMIT;
