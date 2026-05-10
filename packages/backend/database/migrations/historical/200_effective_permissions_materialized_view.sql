-- Migration 200: Materialized View for Effective Permissions
-- Purpose: Pre-compute effective permissions for ALL users using recursive role hierarchy
-- This eliminates the need for per-request CTE resolution at scale (>200 agents)
--
-- Architecture:
--   1. effective_permissions_mv: user_id × permission_name (deduplicated)
--   2. Refreshed via pg_cron or application-level scheduler (every 60s)
--   3. Unique index for instant lookups: WHERE user_id = $1 AND permission_name = $2
--
-- Performance: O(1) permission check vs O(depth) recursive CTE per request

-- 1. Create the materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS effective_permissions_mv AS
WITH RECURSIVE role_chain AS (
    -- Start from each user's direct role
    SELECT u.id AS user_id, r.id AS role_id, r.parent_role_id
    FROM users u
    JOIN roles r ON r.id = u.role_id
    WHERE u.status != 'deactivated'
    UNION ALL
    -- Walk up the role hierarchy
    SELECT rc.user_id, parent.id AS role_id, parent.parent_role_id
    FROM roles parent
    JOIN role_chain rc ON rc.parent_role_id = parent.id
),
role_perms AS (
    -- All permissions from role hierarchy (granted = TRUE)
    SELECT DISTINCT rc.user_id, p.name AS permission_name
    FROM role_chain rc
    JOIN role_permissions rp ON rp.role_id = rc.role_id AND rp.granted = TRUE
    JOIN permissions p ON p.id = rp.permission_id
),
user_denies AS (
    -- User-level explicit denies (override role grants)
    SELECT up.user_id, p.name AS permission_name
    FROM user_permissions up
    JOIN permissions p ON p.id = up.permission_id
    WHERE up.granted = FALSE
      AND (up.expires_at IS NULL OR up.expires_at >= NOW())
),
user_grants AS (
    -- User-level explicit grants (add beyond role)
    SELECT up.user_id, p.name AS permission_name
    FROM user_permissions up
    JOIN permissions p ON p.id = up.permission_id
    WHERE up.granted = TRUE
      AND (up.expires_at IS NULL OR up.expires_at >= NOW())
)
-- Final: (role_perms - denies) UNION user_grants
SELECT user_id, permission_name FROM role_perms
WHERE (user_id, permission_name) NOT IN (SELECT user_id, permission_name FROM user_denies)
UNION
SELECT user_id, permission_name FROM user_grants;

-- 2. Create unique index for O(1) lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_effective_perms_user_perm
    ON effective_permissions_mv (user_id, permission_name);

-- 3. Index for "get all permissions for user" queries
CREATE INDEX IF NOT EXISTS idx_effective_perms_user
    ON effective_permissions_mv (user_id);

-- 4. Index for "which users have this permission" queries
CREATE INDEX IF NOT EXISTS idx_effective_perms_perm
    ON effective_permissions_mv (permission_name);

-- 5. Create a refresh function callable from scheduler
CREATE OR REPLACE FUNCTION refresh_effective_permissions()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY effective_permissions_mv;
END;
$$ LANGUAGE plpgsql;

-- 6. Grant SELECT to application role (if exists)
-- GRANT SELECT ON effective_permissions_mv TO taxasge_app;

-- 7. Initial refresh
REFRESH MATERIALIZED VIEW effective_permissions_mv;

-- Note: Schedule periodic refresh via:
--   Option A: pg_cron (if available): SELECT cron.schedule('refresh-perms', '*/1 * * * *', 'SELECT refresh_effective_permissions()');
--   Option B: Application scheduler (internal_scheduler) calling refresh_effective_permissions() every 60s
--   Option C: Triggered refresh after RBAC changes via RBACListener
