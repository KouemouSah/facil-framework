-- Migration 143: Fix treasury legacy views and export template
-- Fixes:
--   1. v_bank_reconciliation_matching: references legacy 'payments' table → use 'service_payments'
--   2. v_reconciliation_health_metrics: references legacy 'payments' table → use 'service_payments'
--   3. export_templates SAGE_X3_STANDARD: 'completed_at' → 'validated_at' (column doesn't exist on service_payments)

BEGIN;

-- ============================================================
-- 1. Fix v_bank_reconciliation_matching
-- OLD: references payments + tax_declarations (legacy tables from declaration-based payments)
-- NEW: references service_payments + service_requests (current architecture)
-- ============================================================
DROP VIEW IF EXISTS v_bank_reconciliation_matching;

CREATE OR REPLACE VIEW v_bank_reconciliation_matching AS
SELECT
    bt.id AS bank_transaction_id,
    bt.bank_code,
    bt.bank_reference,
    bt.bank_transaction_date,
    bt.amount AS bank_amount,
    bt.currency,
    bt.account_number,
    bt.account_holder_name AS bank_account_holder,
    bt.raw_data AS bank_raw_data,
    bt.created_at AS received_at,
    EXTRACT(day FROM (NOW() - bt.created_at)) AS days_unreconciled,
    CASE
        WHEN EXTRACT(day FROM (NOW() - bt.created_at)) > 7 THEN 'HIGH'
        WHEN EXTRACT(day FROM (NOW() - bt.created_at)) > 3 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS urgency_level,
    (
        SELECT json_agg(json_build_object(
            'payment_id', matches.payment_id,
            'user_name', matches.user_name,
            'user_email', matches.user_email,
            'amount', matches.amount,
            'payment_reference', matches.payment_reference,
            'paid_at', matches.paid_at,
            'workflow_code', matches.workflow_code,
            'match_score', matches.match_score
        ))
        FROM (
            SELECT
                sp.id AS payment_id,
                u.full_name AS user_name,
                u.email AS user_email,
                sp.total_amount AS amount,
                sp.payment_reference,
                sp.paid_at,
                sr.workflow_code,
                CASE
                    WHEN sp.payment_reference = bt.bank_reference THEN 100
                    WHEN sp.total_amount = bt.amount THEN 80
                    WHEN ABS(sp.total_amount - bt.amount) < 100 THEN 60
                    ELSE 40
                END AS match_score
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            JOIN users u ON u.id = sp.user_id
            WHERE sp.workflow_status = 'completed'
              AND ABS(sp.total_amount - bt.amount) < 1000
              AND ABS(EXTRACT(EPOCH FROM (sp.paid_at - bt.bank_transaction_date))) < (86400 * 3)
            ORDER BY
                CASE
                    WHEN sp.payment_reference = bt.bank_reference THEN 1
                    WHEN sp.total_amount = bt.amount THEN 2
                    ELSE 3
                END
            LIMIT 5
        ) matches
    ) AS suggested_matches,
    (
        SELECT COUNT(*)
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND ABS(sp.total_amount - bt.amount) < 1000
          AND ABS(EXTRACT(EPOCH FROM (sp.paid_at - bt.bank_transaction_date))) < (86400 * 3)
    ) AS potential_matches_count
FROM bank_transactions bt
WHERE bt.payment_id IS NULL
ORDER BY
    CASE
        WHEN EXTRACT(day FROM (NOW() - bt.created_at)) > 7 THEN 1
        WHEN EXTRACT(day FROM (NOW() - bt.created_at)) > 3 THEN 2
        ELSE 3
    END,
    bt.created_at;


-- ============================================================
-- 2. Fix v_reconciliation_health_metrics
-- OLD: references 'payments' table with payment_status_enum
-- NEW: references 'service_payments' with payment_workflow_status
-- ============================================================
DROP VIEW IF EXISTS v_reconciliation_health_metrics;

CREATE OR REPLACE VIEW v_reconciliation_health_metrics AS
SELECT
    NOW() AS snapshot_time,
    -- Bank transaction metrics (unchanged - bank_transactions table is correct)
    (SELECT COUNT(*) FROM bank_transactions WHERE payment_id IS NULL) AS unreconciled_transactions,
    (SELECT COUNT(*) FROM bank_transactions WHERE payment_id IS NOT NULL) AS reconciled_transactions,
    (SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE payment_id IS NULL) AS unreconciled_amount,
    (SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE payment_id IS NOT NULL) AS reconciled_amount,
    -- Payment metrics (fixed: payments → service_payments)
    (SELECT COUNT(*) FROM service_payments WHERE workflow_status = 'completed') AS unmatched_payments,
    (SELECT COUNT(*) FROM service_payments WHERE workflow_status = 'completed') AS matched_payments,
    (SELECT COALESCE(SUM(total_amount), 0) FROM service_payments WHERE workflow_status = 'completed') AS unmatched_payment_amount,
    -- Aging metrics
    (SELECT COUNT(*) FROM bank_transactions WHERE payment_id IS NULL AND EXTRACT(day FROM (NOW() - created_at)) > 7) AS unreconciled_over_7_days,
    (SELECT COUNT(*) FROM bank_transactions WHERE payment_id IS NULL AND EXTRACT(day FROM (NOW() - created_at)) > 30) AS unreconciled_over_30_days,
    -- Reconciliation rate (30 days)
    (SELECT ROUND(
        COUNT(CASE WHEN payment_id IS NOT NULL THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0)::numeric * 100, 2
    ) FROM bank_transactions WHERE created_at >= NOW() - INTERVAL '30 days') AS reconciliation_rate_30d,
    -- Average reconciliation time (30 days)
    (SELECT AVG(EXTRACT(EPOCH FROM (reconciled_at - created_at)) / 3600)
     FROM bank_transactions
     WHERE reconciled_at IS NOT NULL AND created_at >= NOW() - INTERVAL '30 days') AS avg_reconciliation_hours_30d,
    -- Today metrics
    (SELECT COUNT(*) FROM bank_transactions WHERE DATE(created_at) = CURRENT_DATE) AS transactions_today,
    (SELECT COUNT(*) FROM bank_transactions WHERE DATE(reconciled_at) = CURRENT_DATE) AS reconciled_today;


-- ============================================================
-- 3. Fix export template SAGE_X3_STANDARD: completed_at → validated_at
-- ============================================================
UPDATE export_templates
SET columns_config = (
    SELECT jsonb_agg(
        CASE
            WHEN elem->>'source' = 'completed_at'
            THEN jsonb_set(elem, '{source}', '"validated_at"')
            ELSE elem
        END
    )
    FROM jsonb_array_elements(columns_config::jsonb) AS elem
)
WHERE code = 'SAGE_X3_STANDARD';

COMMIT;
