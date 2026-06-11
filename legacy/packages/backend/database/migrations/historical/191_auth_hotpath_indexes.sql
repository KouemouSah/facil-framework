-- Migration 191: Optimize auth hotpath indexes for production scale
-- Purpose: Composite partial indexes for high-frequency auth queries
-- Impact: Token validation (~every request), session lookups, expired token cleanup
-- Date: 2026-03-09

-- 1. Composite partial index for session token validation
-- Query pattern: WHERE access_token = $1 AND status = 'active' LIMIT 1
-- Current: idx_sessions_access_token (access_token only) → post-index filter on status
-- Improvement: Include status in index with partial filter → index-only scan
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_access_token_active
ON sessions (access_token)
WHERE status = 'active';

-- 2. Composite partial index for refresh token validation
-- Query pattern: WHERE token = $1 AND is_revoked = false LIMIT 1
-- Current: refresh_tokens_token_key (UNIQUE on token) → covers it but scans revoked too
-- Improvement: Partial index excluding revoked tokens → smaller index, faster scans
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refresh_tokens_token_valid
ON refresh_tokens (token)
WHERE is_revoked = false;

-- 3. Index for expired session cleanup (cron job)
-- Query pattern: WHERE status = 'active' AND expires_at < NOW()
-- Current: idx_sessions_expires_at (expires_at only) → scans all statuses
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_expired_active
ON sessions (expires_at)
WHERE status = 'active';

-- 4. Index for expired refresh token cleanup
-- Query pattern: WHERE is_revoked = false AND expires_at < $1
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refresh_tokens_expired_valid
ON refresh_tokens (expires_at)
WHERE is_revoked = false;

-- 5. Composite index for user sessions listing
-- Query pattern: WHERE user_id = $1 AND status = 'active' ORDER BY created_at DESC LIMIT 50
-- Current: idx_sessions_active_user covers (user_id, status) WHERE active
-- But doesn't include created_at for the ORDER BY → extra sort step
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_active_recent
ON sessions (user_id, created_at DESC)
WHERE status = 'active';
