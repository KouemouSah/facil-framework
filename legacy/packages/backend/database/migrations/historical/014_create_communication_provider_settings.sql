-- Migration: Create Communication Provider Settings Table
-- Date: 2025-12-19
-- Description: Table to store configuration for SMS, Email, Push, WhatsApp providers

-- =============================================================================
-- ENUM TYPE: Communication Provider Types
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'communication_provider_type') THEN
        CREATE TYPE communication_provider_type AS ENUM (
            'sms',
            'email',
            'push',
            'whatsapp'
        );
    END IF;
END $$;

-- =============================================================================
-- TABLE: Communication Provider Settings
-- =============================================================================

CREATE TABLE IF NOT EXISTS communication_provider_settings (
    id SERIAL PRIMARY KEY,
    provider_type communication_provider_type NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    provider_code VARCHAR(50) NOT NULL UNIQUE,

    -- Connection settings
    api_base_url VARCHAR(500),
    api_key_encrypted VARCHAR(500),
    api_secret_encrypted VARCHAR(500),

    -- Provider-specific configuration (JSONB for flexibility)
    config JSONB DEFAULT '{}'::jsonb,

    -- Settings
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    rate_limit_per_minute INTEGER DEFAULT 100,
    retry_attempts INTEGER DEFAULT 3,
    timeout_seconds INTEGER DEFAULT 30,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),

    -- No constraint here, we use a partial unique index instead
    CONSTRAINT check_timeout CHECK (timeout_seconds > 0 AND timeout_seconds <= 300)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_comm_provider_type ON communication_provider_settings(provider_type);
CREATE INDEX IF NOT EXISTS idx_comm_provider_active ON communication_provider_settings(is_active);
CREATE INDEX IF NOT EXISTS idx_comm_provider_default ON communication_provider_settings(is_default) WHERE is_default = true;

-- Ensure only one default provider per type (partial unique index)
CREATE UNIQUE INDEX IF NOT EXISTS idx_comm_provider_unique_default_per_type
    ON communication_provider_settings(provider_type) WHERE is_default = true;

-- =============================================================================
-- SEED: Infobip SMS Provider Configuration
-- =============================================================================

INSERT INTO communication_provider_settings (
    provider_type,
    provider_name,
    provider_code,
    api_base_url,
    api_key_encrypted,
    config,
    is_active,
    is_default,
    rate_limit_per_minute,
    retry_attempts,
    timeout_seconds
) VALUES (
    'sms',
    'Infobip',
    'INFOBIP_SMS',
    'https://y45e8g.api.infobip.com',
    -- API Key will be stored encrypted, this is a placeholder
    'ENCRYPTED_API_KEY_PLACEHOLDER',
    '{
        "sender_id": "TaxasGE",
        "sms_endpoint": "/sms/2/text/advanced",
        "delivery_report_endpoint": "/sms/1/reports",
        "balance_endpoint": "/account/1/balance",
        "supports_unicode": true,
        "max_segments": 10,
        "country_code": "+240"
    }'::jsonb,
    true,
    true,
    100,
    3,
    30
) ON CONFLICT (provider_code) DO UPDATE SET
    api_base_url = EXCLUDED.api_base_url,
    config = EXCLUDED.config,
    updated_at = NOW();

-- =============================================================================
-- SEED: SendGrid Email Provider Configuration
-- =============================================================================

INSERT INTO communication_provider_settings (
    provider_type,
    provider_name,
    provider_code,
    api_base_url,
    config,
    is_active,
    is_default,
    rate_limit_per_minute,
    retry_attempts,
    timeout_seconds
) VALUES (
    'email',
    'SendGrid',
    'SENDGRID_EMAIL',
    'https://api.sendgrid.com/v3',
    '{
        "from_email": "noreply@taxasge.gq",
        "from_name": "TaxasGE",
        "send_endpoint": "/mail/send",
        "templates_enabled": true,
        "tracking_enabled": true
    }'::jsonb,
    true,
    true,
    500,
    3,
    30
) ON CONFLICT (provider_code) DO UPDATE SET
    config = EXCLUDED.config,
    updated_at = NOW();

-- =============================================================================
-- SEED: Firebase Push Provider Configuration
-- =============================================================================

INSERT INTO communication_provider_settings (
    provider_type,
    provider_name,
    provider_code,
    api_base_url,
    config,
    is_active,
    is_default,
    rate_limit_per_minute,
    retry_attempts,
    timeout_seconds
) VALUES (
    'push',
    'Firebase Cloud Messaging',
    'FCM_PUSH',
    'https://fcm.googleapis.com/v1',
    '{
        "project_id": "taxasge-dev",
        "send_endpoint": "/projects/taxasge-dev/messages:send",
        "platforms": ["android", "ios", "web"],
        "priority": "high"
    }'::jsonb,
    true,
    true,
    1000,
    3,
    30
) ON CONFLICT (provider_code) DO UPDATE SET
    config = EXCLUDED.config,
    updated_at = NOW();

-- =============================================================================
-- SEED: WhatsApp Business API Configuration
-- =============================================================================

INSERT INTO communication_provider_settings (
    provider_type,
    provider_name,
    provider_code,
    api_base_url,
    config,
    is_active,
    is_default,
    rate_limit_per_minute,
    retry_attempts,
    timeout_seconds
) VALUES (
    'whatsapp',
    'Meta WhatsApp Business',
    'META_WHATSAPP',
    'https://graph.facebook.com/v17.0',
    '{
        "phone_number_id": "PHONE_NUMBER_ID_PLACEHOLDER",
        "business_account_id": "BUSINESS_ACCOUNT_ID_PLACEHOLDER",
        "send_endpoint": "/messages",
        "templates_endpoint": "/message_templates",
        "webhook_verify_token": "taxasge_whatsapp_verify"
    }'::jsonb,
    false,
    true,
    100,
    3,
    30
) ON CONFLICT (provider_code) DO UPDATE SET
    config = EXCLUDED.config,
    updated_at = NOW();

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE communication_provider_settings IS 'Configuration settings for communication providers (SMS, Email, Push, WhatsApp)';
COMMENT ON COLUMN communication_provider_settings.api_key_encrypted IS 'Encrypted API key - decrypt at runtime using app secret';
COMMENT ON COLUMN communication_provider_settings.config IS 'Provider-specific configuration in JSONB format';
