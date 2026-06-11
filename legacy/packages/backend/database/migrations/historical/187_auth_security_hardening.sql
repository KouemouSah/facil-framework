-- Migration 187: Auth Security Hardening - Indexes + Cleanup
-- Date: 2026-03-08
-- Phase 1.7 of AUTH_SECURITY_HARDENING_PLAN

-- ============================================================================
-- 1. Unique partial index on document_number (prevent duplicates for active users)
-- ============================================================================
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_document_type_number
ON public.users (document_type, document_number)
WHERE document_number IS NOT NULL AND status != 'deactivated';

-- ============================================================================
-- 2. Audit logs indexes (currently only has PK — very slow on any query)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON public.audit_logs(entity_type, entity_id);

-- ============================================================================
-- 3. Phone number index (for dedup/lookup)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_users_phone_number
ON public.users(phone_number)
WHERE phone_number IS NOT NULL;

-- ============================================================================
-- 4. Cleanup expired data (safe: only deletes truly expired records)
-- ============================================================================

-- 4a. Delete expired sessions older than 7 days
DELETE FROM public.sessions
WHERE expires_at < NOW() - INTERVAL '7 days';

-- 4b. Delete expired refresh tokens older than 7 days
DELETE FROM public.refresh_tokens
WHERE expires_at < NOW() - INTERVAL '7 days';

-- 4c. Delete expired pending registrations
DELETE FROM public.pending_registrations
WHERE expires_at < NOW();
