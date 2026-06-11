-- Migration 284: Fix verification_code column size for SHA256 hashing
-- Date: 2026-04-01
-- Context: pending_registration_repository.py hashes verification codes with SHA256
--          before storage (security best practice), but the column was still VARCHAR(6)
--          which is only enough for the raw 6-digit code, not the 64-char hex hash.
-- Error: asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(6)
-- Impact: ALL agent/admin invitations were broken (500 on POST /agents/invite)

ALTER TABLE pending_registrations
ALTER COLUMN verification_code TYPE VARCHAR(128);

-- 128 chars supports SHA256 hex digest (64 chars) with room for future algorithm changes
