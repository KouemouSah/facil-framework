-- =============================================================================
-- Migration 325 — ai_call_metrics + view v_ai_cost_daily (Phase A.1)
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: .claude/plans/AI_OBSERVABILITY_PLAN.md §A.1
--
-- Persists every Gemini / Vertex AI call made by the backend so we can:
--   1. Bill internally (cost tracking per feature, per user role)
--   2. Detect cost spikes / latency degradation (Grafana dashboard 10_ai)
--   3. Drill-down errors via trace_id correlation with Grafana Tempo
--
-- Why a BD table on top of OTEL spans?
-- Tempo free-tier retention = 14 days only — insufficient for monthly cost
-- reports. BD = source of truth for long-term aggregation, Tempo = drill-down.
--
-- BD verified 2026-05-05 BEFORE writing this migration:
--   - users.id is uuid
--   - looker_readonly role exists (mig 316)
--   - PostgreSQL 17.6 supports GENERATED columns
--
-- Idempotent: CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- CREATE OR REPLACE VIEW, GRANT (re-grant is no-op).
--
-- Privacy (RGPD):
--   - prompt_hash is SHA-256 truncated to 16 hex chars (no reverse mapping)
--   - NO raw prompt or response content is stored
--   - user_id reference set null on user deletion
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Table ai_call_metrics
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_call_metrics (
    id              bigserial PRIMARY KEY,
    "timestamp"     timestamptz NOT NULL DEFAULT now(),

    -- Identity (OTEL correlation)
    trace_id        text,
    span_id         text,

    -- Model
    provider        text NOT NULL DEFAULT 'gemini',
    model_name      text NOT NULL,
    operation       text NOT NULL,

    -- Facil feature labels
    feature         text NOT NULL,
    user_id         uuid REFERENCES users(id) ON DELETE SET NULL,
    user_role       text,

    -- Token usage
    input_tokens    int NOT NULL DEFAULT 0,
    output_tokens   int NOT NULL DEFAULT 0,
    total_tokens    int GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    cost_xaf        numeric(14, 6) NOT NULL DEFAULT 0,

    -- Latency & status
    latency_ms      int NOT NULL,
    finish_reason   text,
    status          text NOT NULL,
    error_class     text,

    -- Privacy-safe correlation
    prompt_hash     text,

    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_aim_provider CHECK (
        provider IN ('gemini', 'vertex_embedding', 'vertex_ai')
    ),
    CONSTRAINT chk_aim_operation CHECK (
        operation IN ('chat', 'embeddings', 'completion')
    ),
    CONSTRAINT chk_aim_status CHECK (
        status IN ('success', 'error', 'rate_limited',
                   'json_parse_error', 'timeout', 'content_blocked')
    ),
    CONSTRAINT chk_aim_tokens_nonneg CHECK (
        input_tokens >= 0 AND output_tokens >= 0
    ),
    CONSTRAINT chk_aim_latency_nonneg CHECK (latency_ms >= 0),
    CONSTRAINT chk_aim_cost_nonneg CHECK (cost_xaf >= 0),
    CONSTRAINT chk_aim_prompt_hash_format CHECK (
        prompt_hash IS NULL OR prompt_hash ~ '^[a-f0-9]{16}$'
    ),
    CONSTRAINT chk_aim_trace_id_format CHECK (
        trace_id IS NULL OR trace_id ~ '^[a-f0-9]{32}$'
    ),
    CONSTRAINT chk_aim_span_id_format CHECK (
        span_id IS NULL OR span_id ~ '^[a-f0-9]{16}$'
    )
);

COMMENT ON TABLE ai_call_metrics IS
    'Per-call telemetry for Gemini/Vertex AI requests. Source of truth for AI cost reporting. Phase A AI Observability (mig 325).';
COMMENT ON COLUMN ai_call_metrics.feature IS
    'Facil feature label: chatbot_rag | ocr | classification_* | enrichment | routing | briefing | analyst_* | agent_* | verification_* | embeddings_rag.';
COMMENT ON COLUMN ai_call_metrics.prompt_hash IS
    'SHA-256 of prompt truncated to 16 hex chars. Privacy-safe (no reverse mapping). Used to dedup top-cost prompts.';
COMMENT ON COLUMN ai_call_metrics.cost_xaf IS
    'Estimated cost in FCFA (XAF) computed from token counts × pricing config. Refreshed quarterly.';

-- ---------------------------------------------------------------------------
-- 2. Indexes (designed for the dashboard panels in §A.5)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_aim_timestamp
    ON ai_call_metrics ("timestamp" DESC);

CREATE INDEX IF NOT EXISTS idx_aim_feature_time
    ON ai_call_metrics (feature, "timestamp" DESC);

CREATE INDEX IF NOT EXISTS idx_aim_model_time
    ON ai_call_metrics (model_name, "timestamp" DESC);

-- Partial: only the rows that surface in the error rate panel
CREATE INDEX IF NOT EXISTS idx_aim_status_errors
    ON ai_call_metrics (status, "timestamp" DESC)
    WHERE status != 'success';

CREATE INDEX IF NOT EXISTS idx_aim_user_time
    ON ai_call_metrics (user_id, "timestamp" DESC)
    WHERE user_id IS NOT NULL;

-- For the "Top 10 prompts by cost" panel
CREATE INDEX IF NOT EXISTS idx_aim_prompt_hash
    ON ai_call_metrics (prompt_hash, "timestamp" DESC)
    WHERE prompt_hash IS NOT NULL;

-- For trace_id drill-down (rare but should be fast)
CREATE INDEX IF NOT EXISTS idx_aim_trace_id
    ON ai_call_metrics (trace_id)
    WHERE trace_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Daily aggregation view (powers the cost time-series panel)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_ai_cost_daily AS
SELECT
    date_trunc('day', "timestamp")::date              AS day,
    feature,
    model_name,
    count(*)                                          AS call_count,
    sum(input_tokens)                                 AS input_tokens,
    sum(output_tokens)                                AS output_tokens,
    sum(total_tokens)                                 AS total_tokens,
    sum(cost_xaf)                                     AS cost_xaf,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_latency_ms,
    sum((status = 'success')::int)                    AS success_count,
    sum((status != 'success')::int)                   AS error_count,
    sum((status = 'rate_limited')::int)               AS rate_limited_count,
    sum((status = 'json_parse_error')::int)           AS json_error_count,
    sum((status = 'timeout')::int)                    AS timeout_count
FROM ai_call_metrics
WHERE "timestamp" > now() - interval '90 days'
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 8 DESC;

COMMENT ON VIEW v_ai_cost_daily IS
    'Daily AI usage rollup over the last 90 days. Powers the cost/latency/error Grafana panels. Auto-wrapped to vw_v_ai_cost_daily at boot for Looker Studio JDBC (memory rule #38).';

-- ---------------------------------------------------------------------------
-- 4. Hourly aggregation view (cost spike alert needs sub-day granularity)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_ai_cost_hourly AS
SELECT
    date_trunc('hour', "timestamp")                   AS hour,
    feature,
    count(*)                                          AS call_count,
    sum(cost_xaf)                                     AS cost_xaf,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
    sum((status != 'success')::int)                   AS error_count
FROM ai_call_metrics
WHERE "timestamp" > now() - interval '7 days'
GROUP BY 1, 2
ORDER BY 1 DESC;

COMMENT ON VIEW v_ai_cost_hourly IS
    'Hourly rollup over last 7 days. Powers spike-detection alerts.';

-- ---------------------------------------------------------------------------
-- 5. Grants — exposed to Looker / Grafana via looker_readonly role
-- ---------------------------------------------------------------------------
GRANT SELECT ON ai_call_metrics    TO looker_readonly;
GRANT SELECT ON v_ai_cost_daily    TO looker_readonly;
GRANT SELECT ON v_ai_cost_hourly   TO looker_readonly;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION (run after applying):
-- ---------------------------------------------------------------------------
-- 1. Table + columns:
--    \d ai_call_metrics
--
-- 2. Indexes (8 total: pkey + 7 above):
--    SELECT indexname FROM pg_indexes WHERE tablename = 'ai_call_metrics';
--
-- 3. Constraints (8 CHECKs + FK + PK):
--    SELECT conname FROM pg_constraint WHERE conrelid='ai_call_metrics'::regclass;
--
-- 4. Views:
--    SELECT viewname FROM pg_views WHERE viewname LIKE 'v_ai_cost%';
--
-- 5. Grants:
--    SELECT grantee, privilege_type FROM information_schema.role_table_grants
--    WHERE table_name = 'ai_call_metrics' AND grantee = 'looker_readonly';
--
-- 6. CHECK reject paths:
--    INSERT INTO ai_call_metrics (model_name, operation, feature, latency_ms, status)
--    VALUES ('test', 'invalid_op', 'test', 100, 'success');
--    -- expected: ERROR violates chk_aim_operation
--
--    INSERT INTO ai_call_metrics (model_name, operation, feature, latency_ms, status, prompt_hash)
--    VALUES ('test', 'chat', 'test', 100, 'success', 'invalid_hash');
--    -- expected: ERROR violates chk_aim_prompt_hash_format
--
-- 7. CHECK valid path:
--    INSERT INTO ai_call_metrics (model_name, operation, feature, latency_ms, status,
--      input_tokens, output_tokens, prompt_hash, trace_id)
--    VALUES ('gemini-2.5-flash', 'chat', 'chatbot_rag', 1234, 'success',
--      150, 80, 'a1b2c3d4e5f60718', 'a1b2c3d4e5f6071829aabbccddee0011');
--    -- expected: success, total_tokens computed = 230
--    DELETE FROM ai_call_metrics WHERE feature = 'chatbot_rag' AND latency_ms = 1234;
-- ---------------------------------------------------------------------------

-- ROLLBACK (manual):
-- BEGIN;
--   DROP VIEW IF EXISTS v_ai_cost_hourly;
--   DROP VIEW IF EXISTS v_ai_cost_daily;
--   DROP TABLE IF EXISTS ai_call_metrics;
-- COMMIT;
