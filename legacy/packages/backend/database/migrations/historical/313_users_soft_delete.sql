-- =============================================================================
-- Migration 313 — Users soft-delete (RGPD art. 17 — droit à l'effacement)
-- =============================================================================
-- Adds a `deleted_at` timestamp on `users` so account deletion can be performed
-- as a soft-delete: the user record stays for audit + foreign-key integrity for
-- 30 days, then a periodic cron purges the row + re-shuffles the email so the
-- address can be reused.
--
-- Why soft-delete and not hard-delete:
--   * preserves FK integrity (service_requests, payments, audit_logs, etc.)
--     without complex cascade rules — none of those tables expect their owning
--     user to vanish at random
--   * gives the user a 30-day grace period to undo (regulatory best practice)
--   * keeps the audit trail intact for tax compliance
--
-- Deletion behavior at API time:
--   1. UPDATE users SET deleted_at = NOW(), email = email || '.deleted-' || id
--      (suffixing the email frees up the address for re-registration)
--   2. UPDATE refresh_tokens SET is_revoked = TRUE, revoked_at = NOW()
--      WHERE user_id = $1 AND is_revoked = FALSE
--   3. UPDATE sessions SET status = 'revoked' WHERE user_id = $1
--   4. INSERT INTO audit_logs (entity_type='user', action='soft_delete')
--
-- A separate cron (out of scope for this migration) is expected to:
--   DELETE FROM users WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '30 days';
-- =============================================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;

-- Partial index — most queries filter "active users only", and the column is
-- NULL for the vast majority of rows, so a partial index on the non-null subset
-- is small and lets the purge cron finish quickly.
CREATE INDEX IF NOT EXISTS idx_users_deleted_at
  ON users (deleted_at)
  WHERE deleted_at IS NOT NULL;

-- Comment for self-documentation.
COMMENT ON COLUMN users.deleted_at IS
  'RGPD soft-delete timestamp. NULL = active. Non-null = pending purge by cron after 30 days.';
