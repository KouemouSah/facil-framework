-- Migration 292: Agent Executive Audit Log
--
-- Append-only audit trail for Level 3 executive tools (submit_prepared_request,
-- book_appointment). These tools use a confirmation_code single-use mechanism
-- (Redis TTL 5min) orthogonal to user_agent_permissions because migration 287's
-- CHECK constraint rejects level=3 and the corresponding permission_types.
--
-- Every confirmation code issuance AND redemption is logged here. Never UPDATE
-- except to mark an existing 'issued' row as 'redeemed' (via the dedicated
-- executive_consent service). Never DELETE except via the standard retention
-- policy (not defined yet — infinite for now).
--
-- Security considerations (OWASP A04 Insecure Design + A09 Logging):
-- - We NEVER store the clear confirmation_code, only SHA-256(code).
-- - args_hash is SHA-256 of the canonical JSON of the tool arguments at
--   issuance time; it's re-computed at redemption to detect tampering.
-- - outcome captures the full lifecycle: issued → (redeemed | expired |
--   invalid_args | rate_limited | execution_failed).

BEGIN;

CREATE TABLE IF NOT EXISTS agent_executive_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    tool_name VARCHAR(64) NOT NULL
        CHECK (tool_name IN ('submit_prepared_request', 'book_appointment')),

    -- SHA-256 hex digest of the confirmation_code — the clear code is never stored
    confirmation_code_hash VARCHAR(128) NOT NULL,

    -- SHA-256 hex digest of canonical_json(tool_args without user_id/confirmation_code)
    args_hash VARCHAR(128) NOT NULL,

    -- Short human-readable summary displayed in the confirmation modal
    summary TEXT NOT NULL,

    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    redeemed_at TIMESTAMPTZ,

    outcome VARCHAR(32) NOT NULL DEFAULT 'issued'
        CHECK (outcome IN (
            'issued',
            'redeemed',
            'expired',
            'invalid_args',
            'rate_limited',
            'execution_failed'
        )),

    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_aeal_user_issued
    ON agent_executive_audit_log(user_id, issued_at DESC);

CREATE INDEX IF NOT EXISTS idx_aeal_outcome
    ON agent_executive_audit_log(outcome);

COMMENT ON TABLE agent_executive_audit_log IS
    'Append-only audit trail for Level 3 executive agent tools (Phase 5). '
    'Every confirmation_code issuance and redemption is logged. '
    'See packages/backend/app/modules/chatbot/services/executive_consent.py.';

COMMENT ON COLUMN agent_executive_audit_log.confirmation_code_hash IS
    'SHA-256(confirmation_code). The clear code is NEVER stored anywhere '
    'except the short-lived Redis cache (TTL 5min, single-use).';

COMMENT ON COLUMN agent_executive_audit_log.args_hash IS
    'SHA-256 of canonical JSON of tool arguments (excluding user_id and '
    'confirmation_code). Re-computed at redemption to detect tampering.';

-- Cross-reference comments on user_agent_permissions (migration 287) so any
-- DBA inspecting that table understands why Level 3 is NOT stored there.
-- Moved inline here (instead of a separate migration 293) to avoid collision
-- with migrations created in parallel sessions. COMMENT ON is idempotent —
-- safe to re-run.
COMMENT ON TABLE user_agent_permissions IS
    'Persistent agent autonomy consents (Level 1 informational and '
    'Level 2 preparatory). Level 3 executive tools are handled by the '
    'separate confirmation_code mechanism — see agent_executive_audit_log '
    '(this migration 292) and '
    'app/modules/chatbot/services/executive_consent.py.';

COMMENT ON COLUMN user_agent_permissions.level IS
    'Autonomy level: 1 = informational consent, 2 = preparatory (agent can '
    'modify state within user scope). Level 3 (executive) is NOT stored '
    'here — it uses per-action consent via Redis codes + audit log '
    '(see agent_executive_audit_log).';

COMMENT ON COLUMN user_agent_permissions.permission_type IS
    'Permission scope for Level 1-2 tools. The five allowed values match '
    'the frontend catalog exposed by GET /user-documents/agent/'
    'permission-catalog. Tools submit_prepared_request and book_appointment '
    'are Level 3 and are NOT listed here — they require confirmation_code '
    'redemption (see agent_executive_audit_log).';

COMMIT;
