-- Migration 286: Add device push token column for FCM notifications
-- Used by mobile apps (Facil citizen + Facil Inspector) to receive push notifications.
-- One token per user (last registered device wins).

ALTER TABLE users
ADD COLUMN IF NOT EXISTS device_push_token TEXT DEFAULT NULL;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS device_push_platform VARCHAR(10) DEFAULT NULL;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS device_push_app VARCHAR(20) DEFAULT NULL;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS device_push_updated_at TIMESTAMPTZ DEFAULT NULL;

-- Index for push sending service (query active tokens)
CREATE INDEX IF NOT EXISTS idx_users_device_push_token
ON users (device_push_token)
WHERE device_push_token IS NOT NULL;

COMMENT ON COLUMN users.device_push_token IS 'Expo/FCM push token for mobile notifications';
COMMENT ON COLUMN users.device_push_platform IS 'android or ios';
COMMENT ON COLUMN users.device_push_app IS 'citizen or inspector';
COMMENT ON COLUMN users.device_push_updated_at IS 'Last token registration timestamp';
