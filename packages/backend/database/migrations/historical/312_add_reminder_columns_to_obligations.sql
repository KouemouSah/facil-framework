-- Migration 312: Add reminder tracking columns to license_obligations
--
-- oms_reminder_service.py references these columns for dedup:
-- - reminder_sent_at: J-15 reminder sent timestamp
-- - overdue_notice_sent_at: J+1 overdue notice sent
-- - escalation_sent_at: J+30 escalation sent to supervisors
--
-- Without these, the reminder cron crashes with UndefinedColumnError.

ALTER TABLE license_obligations
ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMPTZ DEFAULT NULL,
ADD COLUMN IF NOT EXISTS overdue_notice_sent_at TIMESTAMPTZ DEFAULT NULL,
ADD COLUMN IF NOT EXISTS escalation_sent_at TIMESTAMPTZ DEFAULT NULL;
