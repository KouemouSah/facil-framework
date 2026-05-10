-- =============================================================================
-- Migration 331 — Legal acceptance columns for Privacy Policy + Terms of Service
-- =============================================================================
-- Created: 2026-05-02
-- Plan reference: .claude/plans/MOBILE_PHASE_10_B_LEGAL_DETAILED.md
--
-- Purpose : track which version of Privacy Policy and Terms of Service each
-- user has explicitly accepted, with timestamp. Required by:
--   - Google Play Store : data safety + user consent declaration
--   - GDPR / Equatorial Guinea data protection regulations : audit trail
--   - V1 mobile launch : user-blocking sign-up flow with explicit checkbox
--
-- SCOPE — acceptance is enforced ONLY for roles where users self-onboard
-- via the public sign-up form (citizen, business, accountant). Admin /
-- agent / funcionario are created internally by an admin and are bound by
-- separate contractual agreements (employment / mandate) — they do NOT
-- need an in-app CGU acceptance. The 4 columns are added to ALL users for
-- schema cleanliness, but admin/agent/funcionario rows stay NULL.
--
-- BACKFILL : existing citizen/business/accountant users get a "deemed
-- accepted" stamp at version "1.0.0-legacy" with timestamp = created_at.
-- This is the legal basis used by the original web sign-up flow which
-- mentioned the terms in the form prose. The post-login mobile modal
-- (Phase B) re-prompts only when current version > 1.0.0-legacy (i.e. on
-- the next version bump, e.g. 1.1.0).
-- =============================================================================

BEGIN;

-- 1. Add columns (idempotent — safe re-run)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS terms_accepted_at   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS terms_version       VARCHAR(16),
  ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS privacy_version     VARCHAR(16);

COMMENT ON COLUMN users.terms_accepted_at   IS 'Timestamp when user explicitly accepted Terms of Service. NULL for admin/agent/funcionario (no in-app CGU obligation).';
COMMENT ON COLUMN users.terms_version       IS 'Version of Terms of Service the user accepted (e.g. "1.0.0", "1.0.0-legacy"). NULL for internal roles.';
COMMENT ON COLUMN users.privacy_accepted_at IS 'Timestamp when user explicitly accepted Privacy Policy. NULL for internal roles.';
COMMENT ON COLUMN users.privacy_version     IS 'Version of Privacy Policy the user accepted. NULL for internal roles.';

-- 2. Backfill ONLY public-onboarding roles (citizen, business, accountant).
-- admin/agent/funcionario remain NULL — they have no app-CGU obligation.
UPDATE users
SET terms_accepted_at   = COALESCE(terms_accepted_at,   created_at),
    terms_version       = COALESCE(terms_version,       '1.0.0-legacy'),
    privacy_accepted_at = COALESCE(privacy_accepted_at, created_at),
    privacy_version     = COALESCE(privacy_version,     '1.0.0-legacy')
WHERE role IN ('citizen', 'business', 'accountant')
  AND (terms_accepted_at IS NULL OR privacy_accepted_at IS NULL);

-- No indices added : we don't filter by terms_version in hot paths. The
-- post-login mobile modal does a single user lookup (by id, already PK
-- indexed) and reads these columns inline. If we later need to bulk
-- query "users with stale versions", a partial index could be added then.

COMMIT;

-- =============================================================================
-- Rollback (manual only — never auto-run) :
--   BEGIN;
--   ALTER TABLE users
--     DROP COLUMN IF EXISTS terms_accepted_at,
--     DROP COLUMN IF EXISTS terms_version,
--     DROP COLUMN IF EXISTS privacy_accepted_at,
--     DROP COLUMN IF EXISTS privacy_version;
--   COMMIT;
-- =============================================================================
