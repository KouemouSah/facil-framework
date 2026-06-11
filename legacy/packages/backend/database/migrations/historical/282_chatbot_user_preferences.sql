-- Migration 282: Chatbot user preferences for personalization
-- Stores user preferences learned from conversations (language, zone, profile type)
-- Injected into LLM context for personalized responses

CREATE TABLE IF NOT EXISTS chatbot_user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferred_language VARCHAR(5) DEFAULT 'es',
    preferred_zone_code VARCHAR(5),          -- A1, B1, C1, D1
    preferred_city TEXT,                      -- Malabo, Bata, etc.
    user_type VARCHAR(30),                   -- citizen, business_owner, accountant, agent
    frequent_topics TEXT[] DEFAULT '{}'::text[],                   -- ['pasaporte', 'licencia', 'residencia']
    total_conversations INT DEFAULT 0,
    last_interaction_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chatbot_user_prefs_updated ON chatbot_user_preferences(updated_at DESC);
