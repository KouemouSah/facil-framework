-- Migration 114: Escalation System Hardening
-- Adds CHECK constraint, missing indexes, and SLA tracking columns
-- Date: 2026-02-21

BEGIN;

-- ============================================================================
-- A1: Backfill any rows with escalated=true but null fields
-- ============================================================================

UPDATE service_requests
SET escalated_at = COALESCE(escalated_at, updated_at, created_at),
    escalated_by = COALESCE(escalated_by, assigned_to, user_id),
    escalation_reason = COALESCE(escalation_reason, 'No reason provided')
WHERE escalated = true
  AND (escalated_at IS NULL OR escalated_by IS NULL OR escalation_reason IS NULL);

-- ============================================================================
-- A2: CHECK constraint — if escalated=true, all 3 fields must be populated
-- ============================================================================

ALTER TABLE service_requests
ADD CONSTRAINT chk_escalation_fields_populated
CHECK (
    escalated = false
    OR (escalated_at IS NOT NULL AND escalated_by IS NOT NULL AND escalation_reason IS NOT NULL)
);

-- ============================================================================
-- A3: Missing indexes
-- ============================================================================

-- Agent's own escalations (for "Mis Escalaciones" page: WHERE escalated_by = $1)
CREATE INDEX IF NOT EXISTS idx_sr_escalated_by
    ON service_requests (escalated_by, escalated_at DESC)
    WHERE escalated = true;

-- Supervisor list filters by workflow_code scope
CREATE INDEX IF NOT EXISTS idx_sr_escalated_workflow
    ON service_requests (workflow_code, escalated_at DESC)
    WHERE escalated = true;

-- Note: idx_service_requests_escalated ON (entity_code, escalated_at DESC)
-- WHERE escalated = true already exists from migration 113.

-- ============================================================================
-- A4: SLA tracking columns
-- ============================================================================

ALTER TABLE service_requests
    ADD COLUMN IF NOT EXISTS escalation_sla_warning_sent BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS escalation_sla_escalated BOOLEAN NOT NULL DEFAULT FALSE;

-- Partial index for SLA cron (pending escalations not yet warned)
CREATE INDEX IF NOT EXISTS idx_sr_escalation_sla_pending
    ON service_requests (escalated_at)
    WHERE escalated = true
      AND escalation_sla_warning_sent = false;

COMMIT;
