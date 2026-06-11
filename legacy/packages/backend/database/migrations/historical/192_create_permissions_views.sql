-- ============================================================================
-- Migration 192: Create missing permissions views
-- ============================================================================
-- Fixes CRITICAL bug: 2 views referenced by permission_repository.py don't exist
-- - v_user_effective_permissions (used by get_user_effective_permissions, list_users_effective_permissions)
-- - v_overprivileged_users_detection (used by detect_overprivileged_users)
-- Also assigns the 15 admin.* permissions to the 'admin' role (currently NONE assigned)
-- ============================================================================

-- ============================================================================
-- VIEW 1: v_user_effective_permissions
-- Combines role-based + user-specific permissions into a single row per user
-- Used by: permission_repository.get_user_effective_permissions(user_id)
--          permission_repository.list_users_effective_permissions(role, is_admin)
-- ============================================================================

CREATE OR REPLACE VIEW v_user_effective_permissions AS
WITH role_perm_counts AS (
    -- Count permissions per role
    SELECT r.id AS role_id, r.code AS role_code, r.name AS role_name,
           COUNT(rp.permission_id) AS role_perm_count,
           ARRAY_AGG(DISTINCT p.module_name ORDER BY p.module_name) AS accessible_modules,
           COUNT(CASE WHEN p.is_critical THEN 1 END) AS critical_perm_count
    FROM roles r
    LEFT JOIN role_permissions rp ON rp.role_id = r.id
    LEFT JOIN permissions p ON p.id = rp.permission_id
    GROUP BY r.id, r.code, r.name
),
user_override_counts AS (
    -- Count user-specific permission overrides
    SELECT up.user_id,
           COUNT(*) FILTER (WHERE up.granted = true AND (up.expires_at IS NULL OR up.expires_at >= NOW())) AS explicit_grants,
           COUNT(*) FILTER (WHERE up.granted = false AND (up.expires_at IS NULL OR up.expires_at >= NOW())) AS explicit_denies,
           COUNT(*) FILTER (WHERE up.expires_at IS NOT NULL AND up.expires_at < NOW()) AS expired_count
    FROM user_permissions up
    GROUP BY up.user_id
)
SELECT
    u.id AS user_id,
    u.email,
    COALESCE(u.first_name || ' ' || u.last_name, u.email) AS full_name,
    u.role::text AS role,
    u.status::text AS status,
    rpc.role_code,
    rpc.role_name,
    COALESCE(rpc.role_perm_count, 0) AS role_permissions_count,
    COALESCE(rpc.accessible_modules, ARRAY[]::varchar[]) AS accessible_modules,
    COALESCE(rpc.critical_perm_count, 0) AS critical_permissions_count,
    COALESCE(uoc.explicit_grants, 0) AS explicit_grants,
    COALESCE(uoc.explicit_denies, 0) AS explicit_denies,
    COALESCE(uoc.expired_count, 0) AS expired_overrides,
    COALESCE(rpc.role_perm_count, 0) + COALESCE(uoc.explicit_grants, 0) - COALESCE(uoc.explicit_denies, 0) AS total_effective_permissions,
    -- Capability level based on permission count
    CASE
        WHEN COALESCE(rpc.role_perm_count, 0) + COALESCE(uoc.explicit_grants, 0) > 100 THEN 'FULL_ACCESS'
        WHEN COALESCE(rpc.role_perm_count, 0) + COALESCE(uoc.explicit_grants, 0) > 50 THEN 'ELEVATED'
        WHEN COALESCE(rpc.role_perm_count, 0) + COALESCE(uoc.explicit_grants, 0) > 20 THEN 'STANDARD'
        WHEN COALESCE(rpc.role_perm_count, 0) + COALESCE(uoc.explicit_grants, 0) > 0 THEN 'LIMITED'
        ELSE 'NONE'
    END AS capability_level,
    -- Admin flag
    u.role::text = 'admin' AS is_admin
FROM users u
LEFT JOIN roles r_link ON r_link.id = u.role_id
LEFT JOIN role_perm_counts rpc ON rpc.role_id = u.role_id
LEFT JOIN user_override_counts uoc ON uoc.user_id = u.id
WHERE u.status::text != 'deactivated';


-- ============================================================================
-- VIEW 2: v_overprivileged_users_detection
-- Identifies users with more permissions than typical for their role
-- Used by: permission_repository.detect_overprivileged_users(min_risk_score, risk_level)
-- ============================================================================

CREATE OR REPLACE VIEW v_overprivileged_users_detection AS
WITH role_averages AS (
    -- Average permissions per role (baseline)
    SELECT r.code AS role_code,
           COUNT(DISTINCT rp.permission_id) AS role_perm_count,
           COUNT(DISTINCT CASE WHEN p.is_critical THEN p.id END) AS role_critical_count
    FROM roles r
    LEFT JOIN role_permissions rp ON rp.role_id = r.id
    LEFT JOIN permissions p ON p.id = rp.permission_id
    GROUP BY r.code
),
user_totals AS (
    -- Total permissions per user (role + overrides)
    SELECT u.id AS user_id,
           u.email,
           COALESCE(u.first_name || ' ' || u.last_name, u.email) AS full_name,
           u.role::text AS role,
           r.code AS role_code,
           -- Role-based permissions
           COUNT(DISTINCT rp.permission_id) AS from_role,
           -- User-specific grants (active only)
           (SELECT COUNT(*) FROM user_permissions up
            WHERE up.user_id = u.id AND up.granted = true
            AND (up.expires_at IS NULL OR up.expires_at >= NOW())) AS from_user_grants,
           -- User-specific denies
           (SELECT COUNT(*) FROM user_permissions up
            WHERE up.user_id = u.id AND up.granted = false
            AND (up.expires_at IS NULL OR up.expires_at >= NOW())) AS from_user_denies,
           -- Critical permissions from role
           COUNT(DISTINCT CASE WHEN p.is_critical THEN p.id END) AS critical_from_role,
           -- Critical permissions from user grants
           (SELECT COUNT(*) FROM user_permissions up
            JOIN permissions p2 ON p2.id = up.permission_id
            WHERE up.user_id = u.id AND up.granted = true AND p2.is_critical
            AND (up.expires_at IS NULL OR up.expires_at >= NOW())) AS critical_from_user
    FROM users u
    LEFT JOIN roles r ON r.id = u.role_id
    LEFT JOIN role_permissions rp ON rp.role_id = r.id
    LEFT JOIN permissions p ON p.id = rp.permission_id
    WHERE u.status::text != 'deactivated'
    GROUP BY u.id, u.email, u.first_name, u.last_name, u.role, r.code
)
SELECT
    ut.user_id,
    ut.email,
    ut.full_name,
    ut.role,
    ut.role_code,
    ut.from_role AS role_permissions,
    ut.from_user_grants AS user_grants,
    ut.from_user_denies AS user_denies,
    ut.from_role + ut.from_user_grants - ut.from_user_denies AS total_permissions,
    ut.critical_from_role + ut.critical_from_user AS total_critical,
    -- Risk score: weighted formula
    -- +1 per extra user grant, +5 per critical user grant, +10 if >50% more than role average
    ut.from_user_grants
    + (ut.critical_from_user * 5)
    + CASE WHEN ra.role_perm_count > 0
           AND (ut.from_role + ut.from_user_grants) > (ra.role_perm_count * 1.5)
           THEN 10 ELSE 0 END
    + CASE WHEN ut.critical_from_role + ut.critical_from_user > 10 THEN 15 ELSE 0 END
    AS risk_score,
    -- Risk level
    CASE
        WHEN ut.from_user_grants + (ut.critical_from_user * 5)
             + CASE WHEN ra.role_perm_count > 0
                    AND (ut.from_role + ut.from_user_grants) > (ra.role_perm_count * 1.5)
                    THEN 10 ELSE 0 END
             + CASE WHEN ut.critical_from_role + ut.critical_from_user > 10 THEN 15 ELSE 0 END
             >= 50 THEN 'CRITICAL'
        WHEN ut.from_user_grants + (ut.critical_from_user * 5)
             + CASE WHEN ra.role_perm_count > 0
                    AND (ut.from_role + ut.from_user_grants) > (ra.role_perm_count * 1.5)
                    THEN 10 ELSE 0 END
             + CASE WHEN ut.critical_from_role + ut.critical_from_user > 10 THEN 15 ELSE 0 END
             >= 30 THEN 'HIGH'
        WHEN ut.from_user_grants + (ut.critical_from_user * 5)
             + CASE WHEN ra.role_perm_count > 0
                    AND (ut.from_role + ut.from_user_grants) > (ra.role_perm_count * 1.5)
                    THEN 10 ELSE 0 END
             + CASE WHEN ut.critical_from_role + ut.critical_from_user > 10 THEN 15 ELSE 0 END
             >= 20 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level,
    -- Recommendation
    CASE
        WHEN ut.from_user_grants > 10 THEN 'Review user-specific grants — consider creating a dedicated role'
        WHEN ut.critical_from_user > 3 THEN 'Excessive critical permissions via user grants — audit immediately'
        WHEN ra.role_perm_count > 0
             AND (ut.from_role + ut.from_user_grants) > (ra.role_perm_count * 1.5)
             THEN 'User has 50%+ more permissions than role baseline — review grants'
        ELSE 'Within acceptable range'
    END AS recommendation
FROM user_totals ut
LEFT JOIN role_averages ra ON ra.role_code = ut.role_code;


-- ============================================================================
-- VIEW 3: Drop and recreate v_permission_usage_analytics with columns the code expects
-- Must DROP first because CREATE OR REPLACE cannot change column names/order
-- The existing view is too simple (missing: module alias, usage_category,
-- users_with_permission). permission_repository.py L452-478 expects these.
-- ============================================================================

DROP VIEW IF EXISTS v_permission_usage_analytics;
CREATE VIEW v_permission_usage_analytics AS
WITH perm_stats AS (
    SELECT
        p.id AS permission_id,
        p.name AS permission_name,
        p.resource,
        p.action,
        p.module_name,
        p.module_name AS module,  -- alias expected by repository code
        p.is_critical,
        p.created_at AS permission_created_at,
        -- Direct user grants (active)
        COUNT(DISTINCT up.user_id) FILTER (
            WHERE up.granted = true AND (up.expires_at IS NULL OR up.expires_at >= NOW())
        ) AS direct_grant_count,
        -- Roles that have this permission
        COUNT(DISTINCT rp.role_id) AS role_grant_count,
        -- Users who have it via role
        COUNT(DISTINCT u.id) AS users_with_permission
    FROM permissions p
    LEFT JOIN user_permissions up ON up.permission_id = p.id
    LEFT JOIN role_permissions rp ON rp.permission_id = p.id
    LEFT JOIN users u ON u.role_id = rp.role_id AND u.status::text = 'active'
    GROUP BY p.id, p.name, p.resource, p.action, p.module_name, p.is_critical, p.created_at
)
SELECT
    permission_id,
    permission_name,
    resource,
    action,
    module_name,
    module,
    is_critical,
    permission_created_at,
    direct_grant_count,
    role_grant_count,
    users_with_permission,
    -- Usage category based on how many users have this permission
    CASE
        WHEN users_with_permission + direct_grant_count = 0 THEN 'UNUSED'
        WHEN users_with_permission + direct_grant_count <= 2 THEN 'RARELY_USED'
        WHEN users_with_permission + direct_grant_count <= 10 THEN 'MODERATELY_USED'
        ELSE 'WIDELY_USED'
    END AS usage_category
FROM perm_stats;


-- ============================================================================
-- FIX: Assign 15 admin.* permissions to 'admin' role (currently NONE assigned)
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
SELECT r.id, p.id, true, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
  AND p.module_name = 'admin'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Also add dashboard.*, reports.*, rules.* from ADMIN role to admin role (they're useful)
INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
SELECT r.id, p.id, true, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
  AND p.module_name IN ('dashboard', 'reports', 'rules')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
