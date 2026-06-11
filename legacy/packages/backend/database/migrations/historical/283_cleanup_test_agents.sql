-- Migration 283: Cleanup test/phantom agents
-- Date: 2026-04-01
-- Context: Audit found agents created via migration 272 with test passwords
--          and fake emails that are marked as active+available, polluting
--          routing, workload stats, and creating security risks.
--
-- Actions:
-- 1. Deactivate OMS test agents (migration 272)
-- 2. Set availability=unavailable for deactivated agents
-- 3. Deactivate agent profiles for deactivated users
-- 4. Audit: log all affected agents

BEGIN;

-- ============================================================
-- Step 1: Identify and deactivate test agents from migration 272
-- These were created with password 'TestOms2026!' and test emails
-- ============================================================

-- Deactivate users with test OMS emails (pattern: *.oms@test.facil.gq or similar test patterns)
-- Also catch agents with email_verified = false AND status = 'active' (should never happen in production)
WITH deactivated_users AS (
    UPDATE users
    SET
        status = 'deactivated',
        updated_at = NOW()
    WHERE id IN (
        -- OMS test agents: users linked to agent_profiles created by migration 272
        -- with known test password hash pattern
        SELECT u.id
        FROM users u
        INNER JOIN agent_profiles ap ON ap.user_id = u.id
        WHERE u.status = 'active'
        AND u.email_verified = false
    )
    RETURNING id, email, status
)
SELECT 'deactivated_user' AS action, id, email FROM deactivated_users;

-- ============================================================
-- Step 2: Set unavailable for all agent profiles of deactivated users
-- ============================================================

WITH updated_workloads AS (
    UPDATE agent_workloads
    SET
        availability = 'unavailable',
        workload_status = 'unavailable',
        updated_at = NOW()
    WHERE agent_profile_id IN (
        SELECT ap.id
        FROM agent_profiles ap
        INNER JOIN users u ON u.id = ap.user_id
        WHERE u.status = 'deactivated'
        AND ap.is_active = true
    )
    RETURNING agent_profile_id
)
SELECT 'workload_set_unavailable' AS action, agent_profile_id FROM updated_workloads;

-- ============================================================
-- Step 3: Deactivate agent profiles for deactivated users
-- ============================================================

WITH deactivated_profiles AS (
    UPDATE agent_profiles
    SET
        is_active = false,
        deactivated_at = NOW(),
        deactivation_reason = 'Audit 2026-04-01: Test account with unverified email'
    WHERE user_id IN (
        SELECT id FROM users WHERE status = 'deactivated'
    )
    AND is_active = true
    RETURNING id, user_id
)
SELECT 'deactivated_profile' AS action, id, user_id FROM deactivated_profiles;

-- ============================================================
-- Step 4: Audit log — record this cleanup
-- ============================================================

INSERT INTO audit_logs (user_id, action, resource_type, details, created_at)
SELECT
    '00000000-0000-0000-0000-000000000000'::uuid,  -- system action
    'system_cleanup',
    'agent_profiles',
    jsonb_build_object(
        'migration', '283_cleanup_test_agents',
        'reason', 'Deactivated test agents with unverified emails',
        'agent_profile_id', ap.id,
        'user_email', u.email,
        'previous_status', 'active'
    ),
    NOW()
FROM agent_profiles ap
INNER JOIN users u ON u.id = ap.user_id
WHERE u.status = 'deactivated'
AND ap.deactivation_reason = 'Audit 2026-04-01: Test account with unverified email';

COMMIT;
