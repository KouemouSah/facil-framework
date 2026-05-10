-- =============================================================================
-- Migration 327 — ai_pricing_config table (Phase B.2)
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: AI_OBSERVABILITY_PLAN.md Phase B.2
--
-- Replaces the hardcoded PRICING_XAF dict in app/core/ai_telemetry.py with a
-- BD-backed config table. Allows quarterly pricing updates without redeploy
-- (admin updates row → cost_xaf calculation immediately uses new rates).
--
-- The wrapper still falls back to the hardcoded PRICING_XAF when the BD is
-- unreachable (defense in depth — never break the user's call).
--
-- BD verified 2026-05-05:
--   - ai_call_metrics table exists (mig 325)
--   - looker_readonly role exists (mig 316)
--
-- Idempotent: CREATE TABLE IF NOT EXISTS, ON CONFLICT DO UPDATE on seed.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ai_pricing_config (
    model_name              text PRIMARY KEY,
    provider                text NOT NULL DEFAULT 'gemini',
    input_xaf_per_1m_tokens  numeric(14, 6) NOT NULL,
    output_xaf_per_1m_tokens numeric(14, 6) NOT NULL DEFAULT 0,
    is_active               boolean NOT NULL DEFAULT true,
    notes                   text,
    -- Audit
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    updated_by              uuid REFERENCES users(id) ON DELETE SET NULL,
    -- Versioning: when pricing changes, we keep the old row inactive for
    -- historical cost recomputation. New active row uses the new rates.
    effective_from          timestamptz NOT NULL DEFAULT now(),
    effective_until         timestamptz,
    CONSTRAINT chk_aipc_provider CHECK (
        provider IN ('gemini', 'vertex_embedding', 'vertex_ai', 'openai', 'anthropic')
    ),
    CONSTRAINT chk_aipc_nonneg CHECK (
        input_xaf_per_1m_tokens >= 0 AND output_xaf_per_1m_tokens >= 0
    ),
    CONSTRAINT chk_aipc_validity CHECK (
        effective_until IS NULL OR effective_until > effective_from
    )
);

COMMENT ON TABLE ai_pricing_config IS
    'Pricing rates for Gemini/Vertex AI models (XAF per 1M tokens). Source of truth for cost_xaf computation in ai_call_metrics. Editable via admin UI / cron — no redeploy needed. Phase B.2 (mig 327).';
COMMENT ON COLUMN ai_pricing_config.effective_from IS
    'Date from which this pricing is active. When pricing changes, mark the old row effective_until=NOW() and INSERT a new active row.';

CREATE INDEX IF NOT EXISTS idx_aipc_active
    ON ai_pricing_config(is_active, model_name)
    WHERE is_active = true;

-- Seed with the current PRICING_XAF values from app/core/ai_telemetry.py
INSERT INTO ai_pricing_config (
    model_name, provider, input_xaf_per_1m_tokens, output_xaf_per_1m_tokens, notes
) VALUES
    ('gemini-2.5-flash',     'gemini',           45.0,    180.0,  'Primary chatbot + classification'),
    ('gemini-2.5-flash-001', 'gemini',           45.0,    180.0,  'Versioned alias of gemini-2.5-flash'),
    ('gemini-1.5-pro',       'gemini',           750.0,   3000.0, 'Complex enrichment + agent decisions'),
    ('gemini-1.5-pro-001',   'gemini',           750.0,   3000.0, NULL),
    ('gemini-1.5-pro-002',   'gemini',           750.0,   3000.0, NULL),
    ('gemini-1.5-flash',     'gemini',           45.0,    180.0,  'Fallback flash model'),
    ('gemini-1.5-flash-002', 'gemini',           45.0,    180.0,  NULL),
    ('text-embedding-005',   'vertex_embedding', 7.5,     0.0,    'Default embedding model — pgvector RAG'),
    ('text-embedding-004',   'vertex_embedding', 7.5,     0.0,    NULL)
ON CONFLICT (model_name) DO UPDATE SET
    provider                 = EXCLUDED.provider,
    input_xaf_per_1m_tokens  = EXCLUDED.input_xaf_per_1m_tokens,
    output_xaf_per_1m_tokens = EXCLUDED.output_xaf_per_1m_tokens,
    notes                    = COALESCE(EXCLUDED.notes, ai_pricing_config.notes),
    updated_at               = NOW();

GRANT SELECT ON ai_pricing_config TO looker_readonly;

COMMIT;

-- VERIFICATION:
--   SELECT model_name, provider, input_xaf_per_1m_tokens, output_xaf_per_1m_tokens, is_active
--   FROM ai_pricing_config ORDER BY model_name;
--   -- expected: 9 rows
