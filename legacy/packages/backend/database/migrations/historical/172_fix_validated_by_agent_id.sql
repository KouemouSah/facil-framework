-- Migration 172: Fix validated_by_agent_id on service_payments
--
-- BUG: validated_by_agent_id was storing agent_profiles.id instead of
-- agent_profiles.user_id (the actual users.id of the TESORO agent).
-- This caused JOINs on users.id to fail (wrong UUID type) and broke
-- entity scoping for the Treasury Analyst.
--
-- Source of truth: payment_validation_audit.agent_user_id (correctly stores users.id)
-- Fix: backfill from PVA for all affected records.

-- 1. Fix completed payments (approve action)
UPDATE service_payments sp
SET validated_by_agent_id = pva.agent_user_id
FROM (
    SELECT DISTINCT ON (payment_id) payment_id, agent_user_id
    FROM payment_validation_audit
    WHERE action = 'approve' AND agent_user_id IS NOT NULL
    ORDER BY payment_id, created_at DESC
) pva
WHERE sp.id = pva.payment_id
  AND sp.validated_by_agent_id IS NOT NULL
  AND sp.validated_by_agent_id != pva.agent_user_id;

-- 2. Fix rejected payments (reject action)
UPDATE service_payments sp
SET validated_by_agent_id = pva.agent_user_id
FROM (
    SELECT DISTINCT ON (payment_id) payment_id, agent_user_id
    FROM payment_validation_audit
    WHERE action = 'reject' AND agent_user_id IS NOT NULL
    ORDER BY payment_id, created_at DESC
) pva
WHERE sp.id = pva.payment_id
  AND sp.validated_by_agent_id IS NOT NULL
  AND sp.validated_by_agent_id != pva.agent_user_id;

-- 3. Fill NULL validated_by_agent_id where PVA exists (edge case: old records)
UPDATE service_payments sp
SET validated_by_agent_id = pva.agent_user_id
FROM (
    SELECT DISTINCT ON (payment_id) payment_id, agent_user_id
    FROM payment_validation_audit
    WHERE agent_user_id IS NOT NULL
    ORDER BY payment_id, created_at DESC
) pva
WHERE sp.id = pva.payment_id
  AND sp.validated_by_agent_id IS NULL
  AND sp.workflow_status IN ('completed', 'rejected_by_agent');

-- 4. Add index for analyst site-scoping queries on validated_by_agent_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sp_validated_by_agent
ON service_payments(validated_by_agent_id)
WHERE validated_by_agent_id IS NOT NULL;
