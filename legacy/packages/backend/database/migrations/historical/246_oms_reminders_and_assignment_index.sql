-- Migration 246: OMS Reminders + Assignment Index
-- Date: 2026-03-20
-- Purpose:
--   1. Add reminder_sent_at to license_obligations for idempotent reminders
--   2. Add partial index on assignments for OMS obligation filtering
--   3. Insert email templates for OMS reminder tiers

-- ============================================================
-- 1. reminder_sent_at on license_obligations
-- ============================================================

ALTER TABLE license_obligations
    ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMPTZ DEFAULT NULL;

ALTER TABLE license_obligations
    ADD COLUMN IF NOT EXISTS overdue_notice_sent_at TIMESTAMPTZ DEFAULT NULL;

ALTER TABLE license_obligations
    ADD COLUMN IF NOT EXISTS escalation_sent_at TIMESTAMPTZ DEFAULT NULL;

COMMENT ON COLUMN license_obligations.reminder_sent_at
    IS 'Timestamp of J-15 reminder sent. Used for idempotency.';
COMMENT ON COLUMN license_obligations.overdue_notice_sent_at
    IS 'Timestamp of J+1 overdue notice sent. Used for idempotency.';
COMMENT ON COLUMN license_obligations.escalation_sent_at
    IS 'Timestamp of J+30 escalation sent. Used for idempotency.';

-- ============================================================
-- 2. Partial index for OMS assignment-based queue filtering
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_assignments_oms_obligation
    ON assignments (agent_profile_id, status)
    WHERE item_type = 'obligation_processing';

COMMENT ON INDEX idx_assignments_oms_obligation
    IS 'Optimizes OMS queue: JOIN assignments WHERE item_type=obligation_processing AND agent_profile_id=$1';

-- ============================================================
-- 3. Email templates for OMS reminders (multilingual)
-- ============================================================

INSERT INTO email_templates (
    template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    category, variables, is_active, created_at, updated_at
) VALUES
(
    'oms_obligation_reminder',
    'Recordatorio de obligación fiscal próxima',
    'Rappel d''obligation fiscale à venir',
    'Upcoming fiscal obligation reminder',
    'Recordatorio: Obligaciones fiscales próximas a vencer — {{company_name}}',
    'Rappel : Obligations fiscales à échéance prochaine — {{company_name}}',
    'Reminder: Upcoming fiscal obligations — {{company_name}}',
    'oms_reminder',
    '[
        {"name": "company_name", "required": true},
        {"name": "obligations_count", "required": true},
        {"name": "total_amount", "required": true},
        {"name": "due_date", "required": true}
    ]'::jsonb,
    true, NOW(), NOW()
),
(
    'oms_obligation_overdue',
    'Obligación fiscal vencida',
    'Obligation fiscale en retard',
    'Overdue fiscal obligation',
    '[URGENTE] {{obligations_count}} obligaciones vencidas — {{company_name}}',
    '[URGENT] {{obligations_count}} obligations en retard — {{company_name}}',
    '[URGENT] {{obligations_count}} overdue obligations — {{company_name}}',
    'oms_reminder',
    '[
        {"name": "company_name", "required": true},
        {"name": "obligations_count", "required": true},
        {"name": "total_amount", "required": true},
        {"name": "days_overdue", "required": true}
    ]'::jsonb,
    true, NOW(), NOW()
),
(
    'oms_obligation_escalation',
    'Escalación: Obligaciones >30 días vencidas',
    'Escalade : Obligations >30 jours de retard',
    'Escalation: Obligations >30 days overdue',
    '[ESCALATION] {{obligations_count}} obligaciones >30 días — {{ministry_name}}',
    '[ESCALADE] {{obligations_count}} obligations >30 jours — {{ministry_name}}',
    '[ESCALATION] {{obligations_count}} obligations >30 days — {{ministry_name}}',
    'oms_reminder',
    '[
        {"name": "ministry_name", "required": true},
        {"name": "obligations_count", "required": true},
        {"name": "total_amount", "required": true}
    ]'::jsonb,
    true, NOW(), NOW()
)
ON CONFLICT (template_code) DO NOTHING;

-- ============================================================
-- Verification
-- ============================================================

DO $$
DECLARE
    v_col_exists boolean;
    v_idx_exists boolean;
    v_tpl_count int;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'license_obligations' AND column_name = 'reminder_sent_at'
    ) INTO v_col_exists;

    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_assignments_oms_obligation'
    ) INTO v_idx_exists;

    SELECT COUNT(*) FROM email_templates
    WHERE template_code LIKE 'oms_obligation_%' INTO v_tpl_count;

    RAISE NOTICE '=== Migration 246 Verification ===';
    RAISE NOTICE 'reminder_sent_at column: %', v_col_exists;
    RAISE NOTICE 'OMS assignment index: %', v_idx_exists;
    RAISE NOTICE 'OMS email templates: %/3', v_tpl_count;

    IF NOT v_col_exists THEN
        RAISE EXCEPTION 'FAILED: reminder_sent_at column not created';
    END IF;
END $$;
