-- ============================================================================
-- MIGRATION 145: Remove deprecated 'locked_by_agent' from payment_workflow_status enum
-- Date: 2026-03-01
-- Context: With auto-assignment architecture (migrations 067-068), agents only
--          see their assigned payments. The explicit locking mechanism is obsolete.
--          Status was replaced by 'agent_reviewing' (agent picks up the payment).
--          Migration 067 already converted all existing locked_by_agent → pending_agent_review.
--          0 payments currently have this status (verified 2026-03-01).
-- ============================================================================

BEGIN;

-- Step 1: Verify no payments use the deprecated status
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM service_payments
    WHERE workflow_status = 'locked_by_agent';

    IF v_count > 0 THEN
        RAISE EXCEPTION 'Cannot remove locked_by_agent: % payments still use this status', v_count;
    END IF;

    RAISE NOTICE 'Migration 145: 0 payments with locked_by_agent - safe to proceed';
END $$;

-- Step 2: Fix workflow_transitions referencing locked_by_agent
-- Row analysis (unique constraint on from_status, to_status):
--   Row 5: pending_agent_review → locked_by_agent → UPDATE to pending_agent_review → agent_reviewing (direct pickup)
--   Row 6: locked_by_agent → agent_reviewing → DELETE (redundant, now covered by Row 5)
--   Row 7: locked_by_agent → pending_agent_review → DELETE ("release lock" concept is gone)
--   Row 21: locked_by_agent → cancelled_by_agent → DELETE (Row 22 already has agent_reviewing → cancelled_by_agent)

DELETE FROM workflow_transitions WHERE from_status = 'locked_by_agent' AND to_status = 'agent_reviewing';
DELETE FROM workflow_transitions WHERE from_status = 'locked_by_agent' AND to_status = 'pending_agent_review';
DELETE FROM workflow_transitions WHERE from_status = 'locked_by_agent' AND to_status = 'cancelled_by_agent';
UPDATE workflow_transitions SET to_status = 'agent_reviewing'
WHERE from_status = 'pending_agent_review' AND to_status = 'locked_by_agent';

-- Step 3: Convert any stale locked_by_agent in payment_validation_audit
UPDATE payment_validation_audit SET from_status = 'pending_agent_review'
WHERE from_status = 'locked_by_agent';
UPDATE payment_validation_audit SET to_status = 'pending_agent_review'
WHERE to_status = 'locked_by_agent';

-- Step 4: Drop ALL dependent views (5 regular + 1 materialized + 4 dependent on matview)
DROP VIEW IF EXISTS v_kpi_summary;
DROP VIEW IF EXISTS v_top_payment_methods;
DROP VIEW IF EXISTS v_top_ministries;
DROP VIEW IF EXISTS v_top_workflows;
DROP MATERIALIZED VIEW IF EXISTS mv_treasury_daily_kpis;
DROP VIEW IF EXISTS v_bank_reconciliation_matching;
DROP VIEW IF EXISTS v_reconciliation_health_metrics;
DROP VIEW IF EXISTS v_pending_escalations;
DROP VIEW IF EXISTS v_pending_payment_validations;
DROP VIEW IF EXISTS v_service_request_payments;

-- Step 5: Drop defaults and partial indexes that cast to the enum
ALTER TABLE service_payments ALTER COLUMN workflow_status DROP DEFAULT;
DROP INDEX IF EXISTS idx_service_payments_pending_validation;

-- Step 6: Convert ALL enum columns to TEXT (avoids cross-type comparison errors)
ALTER TABLE service_payments ALTER COLUMN workflow_status TYPE TEXT;
ALTER TABLE payment_validation_audit ALTER COLUMN from_status TYPE TEXT;
ALTER TABLE payment_validation_audit ALTER COLUMN to_status TYPE TEXT;
ALTER TABLE workflow_transitions ALTER COLUMN from_status TYPE TEXT;
ALTER TABLE workflow_transitions ALTER COLUMN to_status TYPE TEXT;

-- Step 7: Drop old enum and create new one (without locked_by_agent)
DROP TYPE payment_workflow_status;
CREATE TYPE payment_workflow_status AS ENUM (
    'submitted',
    'auto_processing',
    'auto_approved',
    'pending_agent_review',
    'agent_reviewing',
    'requires_documents',
    'docs_resubmitted',
    'approved_by_agent',
    'rejected_by_agent',
    'escalated_supervisor',
    'supervisor_reviewing',
    'completed',
    'cancelled_by_user',
    'cancelled_by_agent',
    'expired'
);

-- Step 8: Convert TEXT columns back to the new enum
ALTER TABLE service_payments ALTER COLUMN workflow_status TYPE payment_workflow_status
    USING workflow_status::payment_workflow_status;
ALTER TABLE payment_validation_audit ALTER COLUMN from_status TYPE payment_workflow_status
    USING from_status::payment_workflow_status;
ALTER TABLE payment_validation_audit ALTER COLUMN to_status TYPE payment_workflow_status
    USING to_status::payment_workflow_status;
ALTER TABLE workflow_transitions ALTER COLUMN from_status TYPE payment_workflow_status
    USING from_status::payment_workflow_status;
ALTER TABLE workflow_transitions ALTER COLUMN to_status TYPE payment_workflow_status
    USING to_status::payment_workflow_status;

-- Step 9: Restore defaults
ALTER TABLE service_payments
    ALTER COLUMN workflow_status SET DEFAULT 'submitted'::payment_workflow_status;

-- Recreate partial index
CREATE INDEX idx_service_payments_pending_validation
    ON service_payments USING btree (workflow_status, payment_method, created_at)
    WHERE workflow_status = 'pending_agent_review'::payment_workflow_status;

-- Step 10: Recreate all views

CREATE OR REPLACE VIEW v_bank_reconciliation_matching AS
SELECT bt.id AS bank_transaction_id,
    bt.bank_code,
    bt.bank_reference,
    bt.bank_transaction_date,
    bt.amount AS bank_amount,
    bt.currency,
    bt.account_number,
    bt.account_holder_name AS bank_account_holder,
    bt.raw_data AS bank_raw_data,
    bt.created_at AS received_at,
    EXTRACT(day FROM now() - bt.created_at) AS days_unreconciled,
    CASE
        WHEN EXTRACT(day FROM now() - bt.created_at) > 7::numeric THEN 'HIGH'::text
        WHEN EXTRACT(day FROM now() - bt.created_at) > 3::numeric THEN 'MEDIUM'::text
        ELSE 'LOW'::text
    END AS urgency_level,
    ( SELECT json_agg(json_build_object('payment_id', matches.payment_id, 'user_name', matches.user_name, 'user_email', matches.user_email, 'amount', matches.amount, 'payment_reference', matches.payment_reference, 'paid_at', matches.paid_at, 'workflow_code', matches.workflow_code, 'match_score', matches.match_score))
       FROM ( SELECT sp.id AS payment_id,
                u.full_name AS user_name,
                u.email AS user_email,
                sp.total_amount AS amount,
                sp.payment_reference,
                sp.paid_at,
                sr.workflow_code,
                CASE
                    WHEN sp.payment_reference::text = bt.bank_reference::text THEN 100
                    WHEN sp.total_amount = bt.amount THEN 80
                    WHEN abs(sp.total_amount - bt.amount) < 100::numeric THEN 60
                    ELSE 40
                END AS match_score
               FROM service_payments sp
                 JOIN service_requests sr ON sr.id = sp.service_request_id
                 JOIN users u ON u.id = sp.user_id
              WHERE sp.workflow_status = 'completed'::payment_workflow_status
                AND abs(sp.total_amount - bt.amount) < 1000::numeric
                AND abs(EXTRACT(epoch FROM sp.paid_at - bt.bank_transaction_date)) < (86400 * 3)::numeric
              ORDER BY (CASE
                    WHEN sp.payment_reference::text = bt.bank_reference::text THEN 1
                    WHEN sp.total_amount = bt.amount THEN 2
                    ELSE 3
                END)
             LIMIT 5) matches) AS suggested_matches,
    ( SELECT count(*)
       FROM service_payments sp
      WHERE sp.workflow_status = 'completed'::payment_workflow_status
        AND abs(sp.total_amount - bt.amount) < 1000::numeric
        AND abs(EXTRACT(epoch FROM sp.paid_at - bt.bank_transaction_date)) < (86400 * 3)::numeric) AS potential_matches_count
FROM bank_transactions bt
WHERE bt.payment_id IS NULL
ORDER BY (CASE
    WHEN EXTRACT(day FROM now() - bt.created_at) > 7::numeric THEN 1
    WHEN EXTRACT(day FROM now() - bt.created_at) > 3::numeric THEN 2
    ELSE 3
END), bt.created_at;

CREATE OR REPLACE VIEW v_reconciliation_health_metrics AS
SELECT now() AS snapshot_time,
    (SELECT count(*) FROM bank_transactions WHERE payment_id IS NULL) AS unreconciled_transactions,
    (SELECT count(*) FROM bank_transactions WHERE payment_id IS NOT NULL) AS reconciled_transactions,
    (SELECT COALESCE(sum(amount), 0::numeric) FROM bank_transactions WHERE payment_id IS NULL) AS unreconciled_amount,
    (SELECT COALESCE(sum(amount), 0::numeric) FROM bank_transactions WHERE payment_id IS NOT NULL) AS reconciled_amount,
    (SELECT count(*) FROM service_payments WHERE workflow_status = 'completed'::payment_workflow_status) AS unmatched_payments,
    (SELECT count(*) FROM service_payments WHERE workflow_status = 'completed'::payment_workflow_status) AS matched_payments,
    (SELECT COALESCE(sum(total_amount), 0::numeric) FROM service_payments WHERE workflow_status = 'completed'::payment_workflow_status) AS unmatched_payment_amount,
    (SELECT count(*) FROM bank_transactions WHERE payment_id IS NULL AND EXTRACT(day FROM now() - created_at) > 7::numeric) AS unreconciled_over_7_days,
    (SELECT count(*) FROM bank_transactions WHERE payment_id IS NULL AND EXTRACT(day FROM now() - created_at) > 30::numeric) AS unreconciled_over_30_days,
    (SELECT round(count(CASE WHEN payment_id IS NOT NULL THEN 1 ELSE NULL::integer END)::numeric / NULLIF(count(*), 0)::numeric * 100::numeric, 2) FROM bank_transactions WHERE created_at >= (now() - '30 days'::interval)) AS reconciliation_rate_30d,
    (SELECT avg(EXTRACT(epoch FROM reconciled_at - created_at) / 3600::numeric) FROM bank_transactions WHERE reconciled_at IS NOT NULL AND created_at >= (now() - '30 days'::interval)) AS avg_reconciliation_hours_30d,
    (SELECT count(*) FROM bank_transactions WHERE date(created_at) = CURRENT_DATE) AS transactions_today,
    (SELECT count(*) FROM bank_transactions WHERE date(reconciled_at) = CURRENT_DATE) AS reconciled_today;

CREATE OR REPLACE VIEW v_pending_escalations AS
SELECT sp.id AS payment_id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS service_request_reference,
    sp.total_amount,
    sp.workflow_status,
    sp.escalation_level,
    sp.escalation_reason,
    sp.escalated_at,
    sp.escalated_to_agent_id AS escalated_to_agent_profile_id,
    supervisor.full_name AS escalated_to_name,
    supervisor.email AS escalated_to_email,
    sp.assigned_agent_id AS original_agent_profile_id,
    original_agent.full_name AS original_agent_name,
    ap_escalated.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    round(EXTRACT(epoch FROM now() - sp.escalated_at) / 3600::numeric, 2) AS hours_since_escalation,
    CASE
        WHEN sp.escalation_level::text = 'critical' THEN 1
        WHEN sp.escalation_level::text = 'high' THEN 2
        WHEN sp.escalation_level::text = 'medium' THEN 3
        ELSE 4
    END AS priority_order
FROM service_payments sp
    LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
    LEFT JOIN agent_profiles ap_escalated ON ap_escalated.id = sp.escalated_to_agent_id
    LEFT JOIN users supervisor ON ap_escalated.user_id = supervisor.id
    LEFT JOIN agent_profiles ap_original ON ap_original.id = sp.assigned_agent_id
    LEFT JOIN users original_agent ON ap_original.user_id = original_agent.id
    LEFT JOIN ministries m ON ap_escalated.ministry_id = m.id
WHERE sp.workflow_status IN ('escalated_supervisor', 'supervisor_reviewing')
    AND sp.escalated_at IS NOT NULL
ORDER BY
    CASE
        WHEN sp.escalation_level::text = 'critical' THEN 1
        WHEN sp.escalation_level::text = 'high' THEN 2
        WHEN sp.escalation_level::text = 'medium' THEN 3
        ELSE 4
    END, sp.escalated_at;

CREATE OR REPLACE VIEW v_pending_payment_validations AS
SELECT sp.id AS payment_id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS request_reference,
    sr.workflow_code,
    sp.user_id,
    u.full_name AS user_name,
    u.email AS user_email,
    sp.payment_method,
    sp.total_amount,
    sp.currency,
    sp.workflow_status,
    sp.assigned_agent_id AS assigned_agent_profile_id,
    assigned_ap.user_id AS assigned_to_user_id,
    assigned_user.full_name AS assigned_to_name,
    sp.batch_id,
    br.reference AS batch_reference,
    br.total_items AS batch_total_items,
    sp.escalated_to_agent_id,
    sp.escalation_level,
    sp.escalation_reason,
    sp.escalated_at,
    sp.sla_escalated,
    sp.created_at,
    EXTRACT(epoch FROM now() - sp.created_at) / 3600::numeric AS hours_waiting
FROM service_payments sp
    LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
    LEFT JOIN users u ON sp.user_id = u.id
    LEFT JOIN agent_profiles assigned_ap ON sp.assigned_agent_id = assigned_ap.id
    LEFT JOIN users assigned_user ON assigned_ap.user_id = assigned_user.id
    LEFT JOIN batch_requests br ON sp.batch_id = br.id
WHERE sp.requires_agent_validation = true
ORDER BY sp.created_at;

CREATE OR REPLACE VIEW v_service_request_payments AS
SELECT sp.id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS request_reference,
    sr.workflow_code,
    sr.solicitud_type,
    sp.user_id,
    u.email AS user_email,
    u.full_name AS user_name,
    sp.payment_method,
    sp.base_amount,
    sp.total_amount,
    sp.currency,
    sp.status,
    sp.workflow_status,
    sp.requires_agent_validation,
    sp.assigned_agent_id AS assigned_agent_profile_id,
    sp.validated_by_agent_id AS validated_by_agent_profile_id,
    sp.validated_at,
    sp.validation_comment,
    sp.receipt_number,
    sp.receipt_url,
    sp.paid_at,
    sp.created_at,
    sp.updated_at
FROM service_payments sp
    LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
    LEFT JOIN users u ON sp.user_id = u.id
WHERE sp.service_request_id IS NOT NULL;

-- Recreate materialized view mv_treasury_daily_kpis + indexes
CREATE MATERIALIZED VIEW mv_treasury_daily_kpis AS
SELECT date(sp.created_at) AS report_date,
    (sp.payment_method)::text AS payment_method,
    sp.ministry_id,
    m.name_es AS ministry_name,
    sr.workflow_code AS service_code,
    COALESCE(fs.name_es, sr.workflow_code) AS service_name,
    sr.workflow_code,
    sr.solicitud_type,
    count(*) AS payment_count,
    count(*) FILTER (WHERE sp.workflow_status = 'completed'::payment_workflow_status) AS completed_count,
    count(*) FILTER (WHERE sp.workflow_status = ANY (ARRAY['rejected_by_agent'::payment_workflow_status, 'cancelled_by_agent'::payment_workflow_status])) AS rejected_count,
    count(*) FILTER (WHERE sp.workflow_status = 'cancelled_by_user'::payment_workflow_status) AS cancelled_by_user_count,
    sum(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed'::payment_workflow_status) AS total_amount,
    avg(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed'::payment_workflow_status) AS avg_amount,
    min(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed'::payment_workflow_status) AS min_amount,
    max(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed'::payment_workflow_status) AS max_amount,
    avg((EXTRACT(epoch FROM (COALESCE(sp.validated_at, sp.paid_at, now()) - sp.created_at)) / 60::numeric))
        FILTER (WHERE sp.workflow_status = ANY (ARRAY['completed'::payment_workflow_status, 'approved_by_agent'::payment_workflow_status])
                  AND sp.validated_at IS NOT NULL) AS avg_processing_minutes,
    count(*) FILTER (WHERE sp.sla_escalated = true) AS sla_breached_count,
    count(*) FILTER (WHERE sp.sla_warning_sent = true) AS sla_warning_count
FROM service_payments sp
    LEFT JOIN ministries m ON m.id = sp.ministry_id
    LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
    LEFT JOIN fiscal_services fs ON fs.id = sr.fiscal_service_id
WHERE sp.created_at >= (CURRENT_DATE - '365 days'::interval)
GROUP BY date(sp.created_at), sp.payment_method, sp.ministry_id, m.name_es,
         sr.workflow_code, sr.solicitud_type, fs.name_es;

CREATE UNIQUE INDEX idx_mv_kpis_unique ON mv_treasury_daily_kpis
    USING btree (report_date, payment_method, COALESCE(ministry_id, 0),
                 COALESCE(service_code, ''::character varying),
                 COALESCE(workflow_code, ''::character varying),
                 COALESCE(solicitud_type, ''::character varying));
CREATE INDEX idx_mv_kpis_date ON mv_treasury_daily_kpis USING btree (report_date DESC);
CREATE INDEX idx_mv_kpis_method ON mv_treasury_daily_kpis USING btree (payment_method);
CREATE INDEX idx_mv_kpis_ministry ON mv_treasury_daily_kpis USING btree (ministry_id);
CREATE INDEX idx_mv_kpis_workflow ON mv_treasury_daily_kpis
    USING btree (workflow_code) WHERE workflow_code IS NOT NULL;

-- Recreate 4 views that depend on mv_treasury_daily_kpis
CREATE OR REPLACE VIEW v_kpi_summary AS
SELECT 'today'::text AS period,
    sum(total_amount) AS total_collected,
    sum(completed_count) AS total_transactions,
    avg(avg_amount) AS avg_transaction,
    sum(sla_breached_count) AS sla_breaches
FROM mv_treasury_daily_kpis WHERE report_date = CURRENT_DATE
UNION ALL
SELECT 'week'::text AS period,
    sum(total_amount), sum(completed_count), avg(avg_amount), sum(sla_breached_count)
FROM mv_treasury_daily_kpis WHERE report_date >= date_trunc('week', CURRENT_DATE::timestamp with time zone)
UNION ALL
SELECT 'month'::text AS period,
    sum(total_amount), sum(completed_count), avg(avg_amount), sum(sla_breached_count)
FROM mv_treasury_daily_kpis WHERE report_date >= date_trunc('month', CURRENT_DATE::timestamp with time zone)
UNION ALL
SELECT 'year'::text AS period,
    sum(total_amount), sum(completed_count), avg(avg_amount), sum(sla_breached_count)
FROM mv_treasury_daily_kpis WHERE report_date >= date_trunc('year', CURRENT_DATE::timestamp with time zone);

CREATE OR REPLACE VIEW v_top_payment_methods AS
SELECT payment_method,
    sum(completed_count) AS transaction_count,
    sum(total_amount) AS total_amount,
    round(sum(total_amount) / NULLIF(sum(sum(total_amount)) OVER (), 0::numeric) * 100::numeric, 2) AS percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('month', CURRENT_DATE::timestamp with time zone)
GROUP BY payment_method
ORDER BY sum(total_amount) DESC;

CREATE OR REPLACE VIEW v_top_ministries AS
SELECT ministry_id, ministry_name,
    sum(completed_count) AS transaction_count,
    sum(total_amount) AS total_amount
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('month', CURRENT_DATE::timestamp with time zone) AND ministry_id IS NOT NULL
GROUP BY ministry_id, ministry_name
ORDER BY sum(total_amount) DESC
LIMIT 10;

CREATE OR REPLACE VIEW v_top_workflows AS
SELECT workflow_code, solicitud_type,
    sum(completed_count) AS transaction_count,
    sum(total_amount) AS total_amount,
    round(sum(total_amount) / NULLIF(sum(sum(total_amount)) OVER (), 0::numeric) * 100::numeric, 2) AS percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('month', CURRENT_DATE::timestamp with time zone) AND workflow_code IS NOT NULL
GROUP BY workflow_code, solicitud_type
ORDER BY sum(total_amount) DESC
LIMIT 10;

-- Step 11: Verify
DO $$
DECLARE
    v_values TEXT;
BEGIN
    SELECT string_agg(e::text, ', ' ORDER BY e::text)
    INTO v_values
    FROM unnest(enum_range(NULL::payment_workflow_status)) e;

    RAISE NOTICE 'Migration 145: payment_workflow_status values = %', v_values;

    IF v_values LIKE '%locked_by_agent%' THEN
        RAISE EXCEPTION 'locked_by_agent still present in enum!';
    END IF;

    RAISE NOTICE 'Migration 145: locked_by_agent successfully removed';
    RAISE NOTICE 'Migration 145: 10 views + 1 materialized view recreated successfully';
END $$;

COMMIT;
