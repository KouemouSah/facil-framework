-- Migration 229: Chatbot conversation persistence
-- Stores conversation history for multi-turn chat sessions
-- Cleanup: conversations > 30 days should be purged by cron

CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    conversation_id TEXT NOT NULL UNIQUE,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    language VARCHAR(5) DEFAULT 'es',
    message_count INT DEFAULT 0,
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chatbot_conv_user ON chatbot_conversations(user_id);
CREATE INDEX idx_chatbot_conv_last_msg ON chatbot_conversations(last_message_at);
