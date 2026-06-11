-- =============================================================================
-- Migration 328 — extend ai_call_metrics with prompt injection assessment columns
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: .claude/plans/SECURITY_OBSERVABILITY_PLAN.md §C.1
--
-- Phase B.5 added prompt injection detection (regex-based, 6-status risk
-- levels) but only persisted the assessment to OTEL spans (Tempo, 14d
-- retention) and Cloud Run logs. No SQL queryability → no dashboard panels,
-- no aggregation, no alerts on trends.
--
-- This migration adds 3 columns to ai_call_metrics so each row carries its
-- injection assessment. Powers C.5 dashboard + C.1 alert (severity critical
-- when ≥5 high-risk attempts/hour).
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT IF EXISTS, CREATE
-- INDEX IF NOT EXISTS.
-- =============================================================================

BEGIN;

ALTER TABLE ai_call_metrics
    ADD COLUMN IF NOT EXISTS injection_risk text,
    ADD COLUMN IF NOT EXISTS injection_score int DEFAULT 0,
    ADD COLUMN IF NOT EXISTS injection_rules text[];

ALTER TABLE ai_call_metrics
    DROP CONSTRAINT IF EXISTS chk_aim_injection_risk;
ALTER TABLE ai_call_metrics
    ADD CONSTRAINT chk_aim_injection_risk
    CHECK (
        injection_risk IS NULL
        OR injection_risk IN ('none', 'low', 'medium', 'high')
    );

ALTER TABLE ai_call_metrics
    DROP CONSTRAINT IF EXISTS chk_aim_injection_score_nonneg;
ALTER TABLE ai_call_metrics
    ADD CONSTRAINT chk_aim_injection_score_nonneg
    CHECK (injection_score IS NULL OR injection_score >= 0);

-- Partial index for the dashboard "high-risk attempts" panel + alerts
CREATE INDEX IF NOT EXISTS idx_aim_high_risk
    ON ai_call_metrics ("timestamp" DESC, feature)
    WHERE injection_risk IN ('medium', 'high');

COMMENT ON COLUMN ai_call_metrics.injection_risk IS
    'Prompt injection risk level from Phase B.5 ai_security.py: none/low/medium/high.';
COMMENT ON COLUMN ai_call_metrics.injection_score IS
    'Cumulative score from matched patterns. 0=clean, 60+=high.';
COMMENT ON COLUMN ai_call_metrics.injection_rules IS
    'Top 5 matched rule labels (e.g. ignore_previous, dan_jailbreak).';

COMMIT;

-- VERIFICATION:
--   \d ai_call_metrics | grep injection
--   SELECT count(*) FROM ai_call_metrics WHERE injection_risk = 'high';
