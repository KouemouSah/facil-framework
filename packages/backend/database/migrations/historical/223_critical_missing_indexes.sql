-- Migration 223: Critical Missing Indexes (Performance Audit)
-- Date: 2026-03-19
-- Description: Add 7 indexes identified as missing in performance audit.
--   Covers auth hot paths (session/token lookups), password reset,
--   email verification, license analytics, and service request history.
-- Note: Uses IF NOT EXISTS (safe for re-runs). NOT CONCURRENTLY because
--   Cloud Run migrations execute inside transactions.

BEGIN;

-- =============================================================================
-- 1. Auth hot path: session access_token lookup
--    Used on every request when Redis is down (fallback path).
--    Partial index on active sessions only — excludes expired/revoked rows.
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_sessions_access_token_active
    ON sessions (access_token)
    WHERE status = 'active';

-- =============================================================================
-- 2. Auth: refresh token lookup
--    Hit on every token refresh cycle (~every 30 min per active user).
--    Partial index on active sessions only.
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_sessions_refresh_token_active
    ON sessions (refresh_token)
    WHERE status = 'active';

-- =============================================================================
-- 3. Auth: refresh_tokens.token lookup
--    Used when validating refresh tokens for rotation/revocation.
--    Partial index excludes already-revoked tokens.
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_active
    ON refresh_tokens (token)
    WHERE is_revoked = false;

-- =============================================================================
-- 4. Password reset flow
--    Token lookup during password reset — sparse column, partial index
--    only covers rows with a non-NULL token.
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_users_password_reset_token
    ON users (password_reset_token)
    WHERE password_reset_token IS NOT NULL;

-- =============================================================================
-- 5. Email verification flow
--    Code lookup during email verification — sparse column, partial index
--    only covers rows with a non-NULL verification code.
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_users_email_verification
    ON users (email_verification_code)
    WHERE email_verification_code IS NOT NULL;

-- =============================================================================
-- 6. License analytics JOINs (company_id + fiscal_year)
--    Composite index for company dashboard queries that filter/group
--    by company and fiscal year (top debtors, fee type debt, monthly trend).
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_commercial_licenses_company_year
    ON commercial_licenses (company_id, fiscal_year);

-- =============================================================================
-- 7. Service request history/notifications timeline
--    Composite index for citizen notification panel and agent history views.
--    Covers WHERE service_request_id = $1 AND action IN (...) ORDER BY performed_at DESC.
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_sr_history_request_action
    ON service_request_history (service_request_id, action, performed_at DESC);

COMMIT;
