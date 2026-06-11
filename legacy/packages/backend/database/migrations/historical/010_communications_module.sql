-- Migration: Communications Module Tables
-- Date: 2025-12-12
-- Description: Create tables for communications management (Email, SMS, Webhooks, USSD, Notifications, Push)

-- 1. Email Templates (metadata - HTML files stored separately)
CREATE TABLE IF NOT EXISTS email_templates (
    id SERIAL PRIMARY KEY,
    template_code VARCHAR(100) UNIQUE NOT NULL,
    name_es VARCHAR(255) NOT NULL,
    name_fr VARCHAR(255),
    name_en VARCHAR(255),
    subject_es VARCHAR(500) NOT NULL,
    subject_fr VARCHAR(500),
    subject_en VARCHAR(500),
    description_es TEXT,
    description_fr TEXT,
    description_en TEXT,
    html_file_path VARCHAR(500) NOT NULL,
    variables JSONB DEFAULT '[]',
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

-- 2. SMS Templates
CREATE TABLE IF NOT EXISTS sms_templates (
    id SERIAL PRIMARY KEY,
    template_code VARCHAR(100) UNIQUE NOT NULL,
    name_es VARCHAR(255) NOT NULL,
    name_fr VARCHAR(255),
    name_en VARCHAR(255),
    content_es TEXT NOT NULL,
    content_fr TEXT,
    content_en TEXT,
    variables JSONB DEFAULT '[]',
    category VARCHAR(100),
    max_segments INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

-- 3. Webhook Configurations
CREATE TABLE IF NOT EXISTS webhook_configurations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    webhook_type VARCHAR(50) NOT NULL,
    endpoint_url VARCHAR(1000) NOT NULL,
    http_method VARCHAR(10) DEFAULT 'POST',
    headers JSONB DEFAULT '{}',
    auth_type VARCHAR(50),
    auth_config JSONB DEFAULT '{}',
    payload_template JSONB,
    retry_config JSONB DEFAULT '{"max_retries": 3, "retry_delay_seconds": 60}',
    timeout_seconds INTEGER DEFAULT 30,
    events TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    last_status VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- 4. USSD Configurations (Multi-operator: Getesa, Muni, Other API SMS)
CREATE TABLE IF NOT EXISTS ussd_configurations (
    id SERIAL PRIMARY KEY,
    operator_name VARCHAR(100) NOT NULL,
    operator_code VARCHAR(50) NOT NULL,
    short_code VARCHAR(20) NOT NULL,
    api_endpoint VARCHAR(500),
    auth_config JSONB DEFAULT '{}',
    menu_structure JSONB NOT NULL,
    session_timeout_seconds INTEGER DEFAULT 180,
    max_input_length INTEGER DEFAULT 160,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- 5. Notification Templates (In-app)
CREATE TABLE IF NOT EXISTS notification_templates (
    id SERIAL PRIMARY KEY,
    template_code VARCHAR(100) UNIQUE NOT NULL,
    name_es VARCHAR(255) NOT NULL,
    name_fr VARCHAR(255),
    name_en VARCHAR(255),
    title_es VARCHAR(255) NOT NULL,
    title_fr VARCHAR(255),
    title_en VARCHAR(255),
    body_es TEXT NOT NULL,
    body_fr TEXT,
    body_en TEXT,
    icon VARCHAR(100),
    action_url VARCHAR(500),
    variables JSONB DEFAULT '[]',
    notification_type VARCHAR(50),
    priority VARCHAR(20) DEFAULT 'normal',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- 6. Push Templates (Mobile/Web Push)
CREATE TABLE IF NOT EXISTS push_templates (
    id SERIAL PRIMARY KEY,
    template_code VARCHAR(100) UNIQUE NOT NULL,
    name_es VARCHAR(255) NOT NULL,
    name_fr VARCHAR(255),
    name_en VARCHAR(255),
    title_es VARCHAR(100) NOT NULL,
    title_fr VARCHAR(100),
    title_en VARCHAR(100),
    body_es VARCHAR(240) NOT NULL,
    body_fr VARCHAR(240),
    body_en VARCHAR(240),
    image_url VARCHAR(500),
    icon_url VARCHAR(500),
    click_action VARCHAR(500),
    data_payload JSONB DEFAULT '{}',
    variables JSONB DEFAULT '[]',
    platform VARCHAR(20) DEFAULT 'all',
    ttl_seconds INTEGER DEFAULT 86400,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- 7. Webhook Logs (audit)
CREATE TABLE IF NOT EXISTS webhook_logs (
    id SERIAL PRIMARY KEY,
    webhook_id INTEGER REFERENCES webhook_configurations(id) ON DELETE CASCADE,
    event_type VARCHAR(100),
    request_payload JSONB,
    response_status INTEGER,
    response_body TEXT,
    duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_email_templates_code ON email_templates(template_code);
CREATE INDEX IF NOT EXISTS idx_email_templates_category ON email_templates(category);
CREATE INDEX IF NOT EXISTS idx_email_templates_active ON email_templates(is_active);

CREATE INDEX IF NOT EXISTS idx_sms_templates_code ON sms_templates(template_code);
CREATE INDEX IF NOT EXISTS idx_sms_templates_category ON sms_templates(category);
CREATE INDEX IF NOT EXISTS idx_sms_templates_active ON sms_templates(is_active);

CREATE INDEX IF NOT EXISTS idx_webhook_configs_type ON webhook_configurations(webhook_type);
CREATE INDEX IF NOT EXISTS idx_webhook_configs_active ON webhook_configurations(is_active);

CREATE INDEX IF NOT EXISTS idx_ussd_configs_operator ON ussd_configurations(operator_code);
CREATE INDEX IF NOT EXISTS idx_ussd_configs_active ON ussd_configurations(is_active);

CREATE INDEX IF NOT EXISTS idx_notification_templates_code ON notification_templates(template_code);
CREATE INDEX IF NOT EXISTS idx_notification_templates_type ON notification_templates(notification_type);
CREATE INDEX IF NOT EXISTS idx_notification_templates_active ON notification_templates(is_active);

CREATE INDEX IF NOT EXISTS idx_push_templates_code ON push_templates(template_code);
CREATE INDEX IF NOT EXISTS idx_push_templates_platform ON push_templates(platform);
CREATE INDEX IF NOT EXISTS idx_push_templates_active ON push_templates(is_active);

CREATE INDEX IF NOT EXISTS idx_webhook_logs_webhook_id ON webhook_logs(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_created_at ON webhook_logs(created_at);

-- Add constraints for webhook_type
ALTER TABLE webhook_configurations DROP CONSTRAINT IF EXISTS chk_webhook_type;
ALTER TABLE webhook_configurations ADD CONSTRAINT chk_webhook_type
    CHECK (webhook_type IN ('whatsapp', 'custom'));

-- Add constraints for auth_type
ALTER TABLE webhook_configurations DROP CONSTRAINT IF EXISTS chk_auth_type;
ALTER TABLE webhook_configurations ADD CONSTRAINT chk_auth_type
    CHECK (auth_type IS NULL OR auth_type IN ('none', 'api_key', 'bearer', 'basic'));

-- Add constraints for notification_type
ALTER TABLE notification_templates DROP CONSTRAINT IF EXISTS chk_notification_type;
ALTER TABLE notification_templates ADD CONSTRAINT chk_notification_type
    CHECK (notification_type IS NULL OR notification_type IN ('info', 'success', 'warning', 'error'));

-- Add constraints for priority
ALTER TABLE notification_templates DROP CONSTRAINT IF EXISTS chk_priority;
ALTER TABLE notification_templates ADD CONSTRAINT chk_priority
    CHECK (priority IN ('low', 'normal', 'high', 'urgent'));

-- Add constraints for platform
ALTER TABLE push_templates DROP CONSTRAINT IF EXISTS chk_platform;
ALTER TABLE push_templates ADD CONSTRAINT chk_platform
    CHECK (platform IN ('all', 'ios', 'android', 'web'));

-- Add constraints for http_method
ALTER TABLE webhook_configurations DROP CONSTRAINT IF EXISTS chk_http_method;
ALTER TABLE webhook_configurations ADD CONSTRAINT chk_http_method
    CHECK (http_method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'));

-- Comments for documentation
COMMENT ON TABLE email_templates IS 'Email templates with multilingual support. HTML content stored in separate files.';
COMMENT ON TABLE sms_templates IS 'SMS templates with multilingual support. Content limited to 160 chars per segment.';
COMMENT ON TABLE webhook_configurations IS 'Webhook configurations for WhatsApp Business API and custom integrations.';
COMMENT ON TABLE ussd_configurations IS 'USSD menu configurations for operators: Getesa, Muni, Other API SMS.';
COMMENT ON TABLE notification_templates IS 'In-app notification templates with multilingual support.';
COMMENT ON TABLE push_templates IS 'Push notification templates for mobile and web platforms.';
COMMENT ON TABLE webhook_logs IS 'Audit log for webhook executions.';
