-- Migration 098: Add citizen_last_viewed_at for notification tracking
-- Purpose: Track when citizen last viewed their request detail page
-- Used to determine which notifications are "new" (unread)

ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS citizen_last_viewed_at TIMESTAMPTZ;

COMMENT ON COLUMN service_requests.citizen_last_viewed_at IS
    'Timestamp of last time the citizen viewed the request detail page. Used to determine unread notifications.';
