-- Migration 281: Chatbot feedback table
-- Stores user feedback (thumbs up/down) on chatbot responses
-- Used for quality improvement and admin analytics

CREATE TABLE IF NOT EXISTS chatbot_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id TEXT NOT NULL,
    message_index INT,                          -- which message in the conversation (0-based)
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),  -- 1=worst, 5=best (thumbs down=1, up=5)
    feedback_text TEXT,                          -- optional text feedback
    message_content TEXT,                        -- snapshot of the assistant message rated
    user_query TEXT,                             -- snapshot of the user query that triggered it
    language VARCHAR(5) DEFAULT 'es',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_chatbot_feedback_conversation ON chatbot_feedback(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chatbot_feedback_created ON chatbot_feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chatbot_feedback_rating ON chatbot_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_chatbot_feedback_user ON chatbot_feedback(user_id) WHERE user_id IS NOT NULL;

-- View for admin dashboard analytics
CREATE OR REPLACE VIEW v_chatbot_feedback_stats AS
SELECT
    COUNT(*) as total_feedback,
    COUNT(*) FILTER (WHERE rating >= 4) as positive_count,
    COUNT(*) FILTER (WHERE rating <= 2) as negative_count,
    ROUND(AVG(rating)::numeric, 2) as avg_rating,
    COUNT(DISTINCT conversation_id) as unique_conversations,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as feedback_last_24h,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as feedback_last_7d
FROM chatbot_feedback;
