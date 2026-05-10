-- ============================================================================
-- Migration 173: agent_query_logs — ML training data for NLP intent classifier
--
-- Purpose:
--   Captures every question sent to Treasury Analyst and Admin Assistant agents.
--   Gemini's function choices become ground truth labels (distant supervision):
--     actual_functions_called → FUNCTION_TO_INTENT map → ground_truth_intent
--   Weekly cron (Phase 3) uses this table to retrain the TF-IDF + LR classifier,
--   continuously adapting to the organization's real vocabulary.
--
-- Storage estimate:
--   ~500B per row × 100 queries/day × 365 days = ~18MB/year
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_query_logs (
    id                       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type               VARCHAR(20)  NOT NULL
                             CHECK (agent_type IN ('treasury', 'admin')),
    session_id               VARCHAR(128),                       -- client UUID for conversation context
    question                 TEXT         NOT NULL,              -- raw user question (max 2000 chars stored)
    detected_intent          VARCHAR(50),                        -- NLP ML prediction
    actual_functions_called  TEXT[]       DEFAULT '{}',          -- Gemini's actual function choices
    ground_truth_intent      VARCHAR(50),                        -- derived: FUNCTION_TO_INTENT[first_fn]
    intent_confidence        FLOAT        CHECK (intent_confidence BETWEEN 0 AND 1),
    intent_probabilities     JSONB,                              -- full 11-class distribution
    was_successful           BOOLEAN      NOT NULL DEFAULT TRUE,
    response_time_ms         INTEGER      CHECK (response_time_ms >= 0),
    entity_codes             TEXT[]       DEFAULT '{}',          -- entities from slot extraction
    time_period_days         INTEGER,
    metric                   VARCHAR(100),
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Primary access pattern: recent logs by agent type for retraining
CREATE INDEX IF NOT EXISTS idx_aql_agent_type_created
    ON agent_query_logs (agent_type, created_at DESC);

-- Retraining query: logs with confirmed ground truth
CREATE INDEX IF NOT EXISTS idx_aql_ground_truth
    ON agent_query_logs (ground_truth_intent, created_at DESC)
    WHERE ground_truth_intent IS NOT NULL;

-- Session lookup for debugging conversation quality
CREATE INDEX IF NOT EXISTS idx_aql_session
    ON agent_query_logs (session_id, created_at DESC)
    WHERE session_id IS NOT NULL;

-- Partial index for retrain window (last 90 days, has ground truth)
CREATE INDEX IF NOT EXISTS idx_aql_retrain_window
    ON agent_query_logs (created_at DESC)
    WHERE ground_truth_intent IS NOT NULL
      AND was_successful = TRUE;

COMMENT ON TABLE agent_query_logs IS
    'ML training data: every question to treasury/admin agents with NLP predictions and Gemini ground truth. Used for weekly auto-retraining of the TF-IDF + LR intent classifier.';

COMMENT ON COLUMN agent_query_logs.ground_truth_intent IS
    'Intent derived from actual_functions_called via FUNCTION_TO_INTENT mapping. '
    'Free ground truth via distant supervision — no manual labeling needed.';

COMMENT ON COLUMN agent_query_logs.intent_probabilities IS
    'Full 11-class probability distribution from sklearn predict_proba. '
    'Enables calibration analysis and threshold tuning.';
