-- ================================================================
-- Migration 165: Drop legacy payment views, recreate health metrics
--
-- PROBLEM: 6 views still reference the old `payments` table.
-- Zero Python code uses them, but they block future payments cleanup.
--
-- FIX: Drop all 6 legacy views. Recreate only
-- v_reconciliation_health_metrics using service_payments + bank_transactions.
-- ================================================================

-- Drop all legacy views
DROP VIEW IF EXISTS v_payments_lifecycle_dashboard CASCADE;
DROP VIEW IF EXISTS v_bank_reconciliation_matching CASCADE;
DROP VIEW IF EXISTS v_reconciliation_health_metrics CASCADE;
DROP VIEW IF EXISTS v_revenue_analytics CASCADE;
DROP VIEW IF EXISTS v_failed_payments_recovery CASCADE;
DROP VIEW IF EXISTS v_payment_plans_tracking CASCADE;

-- Recreate health metrics view using service_payments
CREATE OR REPLACE VIEW v_reconciliation_health_metrics AS
SELECT
    NOW() AS snapshot_time,
    (SELECT COUNT(*)
     FROM bank_transactions
     WHERE service_payment_id IS NULL AND status = 'unreconciled'
    ) AS unreconciled_transactions,
    (SELECT COUNT(*)
     FROM bank_transactions
     WHERE service_payment_id IS NOT NULL AND status = 'reconciled'
    ) AS reconciled_transactions,
    (SELECT COALESCE(SUM(amount), 0)
     FROM bank_transactions
     WHERE service_payment_id IS NULL AND status = 'unreconciled'
    ) AS unreconciled_amount,
    (SELECT COALESCE(SUM(amount), 0)
     FROM bank_transactions
     WHERE service_payment_id IS NOT NULL AND status = 'reconciled'
    ) AS reconciled_amount,
    (SELECT COUNT(*)
     FROM service_payments
     WHERE workflow_status = 'completed' AND bank_transaction_id IS NULL
    ) AS unmatched_payments,
    (SELECT COUNT(*)
     FROM service_payments
     WHERE workflow_status = 'completed' AND bank_transaction_id IS NOT NULL
    ) AS matched_payments,
    (SELECT COUNT(*)
     FROM bank_transactions
     WHERE service_payment_id IS NULL
       AND status = 'unreconciled'
       AND EXTRACT(DAY FROM NOW() - created_at) > 7
    ) AS unreconciled_over_7_days,
    (SELECT ROUND(
        (COUNT(CASE WHEN status = 'reconciled' THEN 1 END)::numeric
         / NULLIF(COUNT(*), 0)) * 100, 2
    )
     FROM bank_transactions
     WHERE created_at >= NOW() - INTERVAL '30 days'
    ) AS reconciliation_rate_30d,
    (SELECT COUNT(*)
     FROM bank_transactions
     WHERE DATE(created_at) = CURRENT_DATE
    ) AS transactions_today,
    (SELECT COUNT(*)
     FROM bank_transactions
     WHERE DATE(reconciled_at) = CURRENT_DATE
    ) AS reconciled_today;
