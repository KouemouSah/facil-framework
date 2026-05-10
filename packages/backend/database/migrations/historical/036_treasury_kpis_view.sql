-- Migration 036: Treasury KPIs Materialized View
-- Description: Vue materialisee pour KPIs et dashboard executif
-- Phase: 4 (KPIs & Dashboard Executif)
-- Date: 2026-01-XX (a executer)
-- Prerequis: Migrations 034-035 completees

-- ============================================================================
-- VUE MATERIALISEE: KPIs journaliers
-- ============================================================================

CREATE MATERIALIZED VIEW mv_treasury_daily_kpis AS
SELECT
    -- Dimensions temporelles
    DATE(sp.created_at) as report_date,

    -- Dimensions paiement
    sp.payment_method::text as payment_method,
    sp.ministry_id,
    m.name_es as ministry_name,

    -- Dimensions service (via fiscal_services OU service_requests)
    COALESCE(sp.fiscal_service_code, sr.workflow_code) as service_code,
    COALESCE(fs.name_es, sr.workflow_code) as service_name,

    -- Dimensions service_requests (si lie)
    sr.workflow_code as workflow_code,
    sr.solicitud_type as solicitud_type,

    -- Metriques de volume
    COUNT(*) as payment_count,
    COUNT(*) FILTER (WHERE sp.workflow_status = 'completed') as completed_count,
    COUNT(*) FILTER (WHERE sp.workflow_status IN ('rejected_by_agent', 'cancelled_by_agent')) as rejected_count,
    COUNT(*) FILTER (WHERE sp.workflow_status = 'cancelled_by_user') as cancelled_by_user_count,

    -- Metriques financieres
    SUM(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as total_amount,
    AVG(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as avg_amount,
    MIN(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as min_amount,
    MAX(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as max_amount,

    -- Metriques de temps (en minutes)
    AVG(
        EXTRACT(EPOCH FROM (
            COALESCE(sp.validated_at, sp.paid_at, NOW()) - sp.created_at
        )) / 60
    ) FILTER (
        WHERE sp.workflow_status IN ('completed', 'approved_by_agent')
          AND sp.validated_at IS NOT NULL
    ) as avg_processing_minutes,

    -- Metriques SLA
    COUNT(*) FILTER (WHERE sp.sla_escalated = true) as sla_breached_count,
    COUNT(*) FILTER (WHERE sp.sla_warning_sent = true) as sla_warning_count

FROM service_payments sp
LEFT JOIN ministries m ON m.id = sp.ministry_id
LEFT JOIN fiscal_services fs ON fs.service_code = sp.fiscal_service_code
LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
WHERE sp.created_at >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY
    DATE(sp.created_at),
    sp.payment_method,
    sp.ministry_id,
    m.name_es,
    COALESCE(sp.fiscal_service_code, sr.workflow_code),
    COALESCE(fs.name_es, sr.workflow_code),
    sr.workflow_code,
    sr.solicitud_type;

-- Index unique pour refresh concurrent
-- Note: service_code peut etre fiscal_service_code ou workflow_code
CREATE UNIQUE INDEX idx_mv_kpis_unique
    ON mv_treasury_daily_kpis(report_date, payment_method, COALESCE(ministry_id, 0), service_code, COALESCE(workflow_code, ''), COALESCE(solicitud_type, ''));

-- Index pour requetes par date
CREATE INDEX idx_mv_kpis_date ON mv_treasury_daily_kpis(report_date DESC);

-- Index pour requetes par methode
CREATE INDEX idx_mv_kpis_method ON mv_treasury_daily_kpis(payment_method);

-- Index pour requetes par ministere
CREATE INDEX idx_mv_kpis_ministry ON mv_treasury_daily_kpis(ministry_id);

COMMENT ON MATERIALIZED VIEW mv_treasury_daily_kpis IS
'KPIs journaliers agreges pour dashboard Treasury.
Rafraichir via: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_treasury_daily_kpis;
Recommandation: rafraichir toutes les heures via cron job.';

-- ============================================================================
-- VUE MATERIALISEE: Performance agents
-- ============================================================================

CREATE MATERIALIZED VIEW mv_agent_performance AS
SELECT
    -- Agent
    ma.id as agent_id,
    u.full_name as agent_name,
    u.email as agent_email,
    ma.is_active as agent_is_active,

    -- Periode (mois)
    DATE_TRUNC('month', pva.created_at) as month,

    -- Metriques d'activite
    COUNT(*) as total_actions,
    COUNT(*) FILTER (WHERE pva.action = 'approve') as validations_count,
    COUNT(*) FILTER (WHERE pva.action = 'reject') as rejections_count,
    COUNT(*) FILTER (WHERE pva.action = 'lock_for_review') as locks_count,
    COUNT(*) FILTER (WHERE pva.action = 'escalate') as escalations_count,

    -- Temps moyen de traitement (secondes)
    AVG(pva.action_duration_seconds) FILTER (
        WHERE pva.action IN ('approve', 'reject') AND pva.action_duration_seconds IS NOT NULL
    ) as avg_action_duration_seconds,

    -- Taux de rejet
    CASE
        WHEN COUNT(*) FILTER (WHERE pva.action IN ('approve', 'reject')) > 0
        THEN ROUND(
            COUNT(*) FILTER (WHERE pva.action = 'reject')::numeric /
            COUNT(*) FILTER (WHERE pva.action IN ('approve', 'reject'))::numeric * 100, 2
        )
        ELSE 0
    END as rejection_rate,

    -- Jours actifs
    COUNT(DISTINCT DATE(pva.created_at)) as active_days

FROM payment_validation_audit pva
JOIN ministry_agents ma ON ma.id = pva.agent_id
JOIN users u ON u.id = pva.agent_user_id
WHERE pva.created_at >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY
    ma.id,
    u.full_name,
    u.email,
    ma.is_active,
    DATE_TRUNC('month', pva.created_at);

-- Index unique pour refresh concurrent
CREATE UNIQUE INDEX idx_mv_agent_perf_unique
    ON mv_agent_performance(agent_id, month);

-- Index par agent
CREATE INDEX idx_mv_agent_perf_agent ON mv_agent_performance(agent_id);

-- Index par mois
CREATE INDEX idx_mv_agent_perf_month ON mv_agent_performance(month DESC);

COMMENT ON MATERIALIZED VIEW mv_agent_performance IS
'Performance mensuelle des agents Treasury.
Rafraichir quotidiennement via cron job.';

-- ============================================================================
-- VUE MATERIALISEE: Reconciliation stats
-- ============================================================================

CREATE MATERIALIZED VIEW mv_reconciliation_stats AS
SELECT
    DATE(bt.created_at) as report_date,
    bt.bank_code,

    -- Volume
    COUNT(*) as total_transactions,
    COUNT(*) FILTER (WHERE bt.status = 'reconciled') as reconciled_count,
    COUNT(*) FILTER (WHERE bt.status = 'unreconciled') as unreconciled_count,
    COUNT(*) FILTER (WHERE bt.status = 'failed') as failed_count,

    -- Montants
    SUM(bt.amount) as total_amount,
    SUM(bt.amount) FILTER (WHERE bt.status = 'reconciled') as reconciled_amount,
    SUM(bt.amount) FILTER (WHERE bt.status = 'unreconciled') as unreconciled_amount,

    -- Taux de reconciliation
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(COUNT(*) FILTER (WHERE bt.status = 'reconciled')::numeric / COUNT(*)::numeric * 100, 2)
        ELSE 0
    END as reconciliation_rate,

    -- Temps moyen de reconciliation (heures)
    AVG(
        EXTRACT(EPOCH FROM (bt.reconciled_at - bt.created_at)) / 3600
    ) FILTER (WHERE bt.reconciled_at IS NOT NULL) as avg_reconciliation_hours

FROM bank_transactions bt
WHERE bt.created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY DATE(bt.created_at), bt.bank_code;

-- Index
CREATE UNIQUE INDEX idx_mv_recon_unique ON mv_reconciliation_stats(report_date, bank_code);
CREATE INDEX idx_mv_recon_date ON mv_reconciliation_stats(report_date DESC);
CREATE INDEX idx_mv_recon_bank ON mv_reconciliation_stats(bank_code);

COMMENT ON MATERIALIZED VIEW mv_reconciliation_stats IS
'Statistiques de reconciliation par jour et par banque.';

-- ============================================================================
-- FONCTIONS DE RAFRAICHISSEMENT
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_treasury_kpis()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_treasury_daily_kpis;
    RAISE NOTICE 'mv_treasury_daily_kpis refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION refresh_agent_performance()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_agent_performance;
    RAISE NOTICE 'mv_agent_performance refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION refresh_reconciliation_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_stats;
    RAISE NOTICE 'mv_reconciliation_stats refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql;

-- Fonction combinee pour cron
CREATE OR REPLACE FUNCTION refresh_all_treasury_views()
RETURNS void AS $$
BEGIN
    PERFORM refresh_treasury_kpis();
    PERFORM refresh_agent_performance();
    PERFORM refresh_reconciliation_stats();
    RAISE NOTICE 'All Treasury views refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_all_treasury_views IS
'Rafraichit toutes les vues materialisees Treasury.
A executer via cron: SELECT refresh_all_treasury_views();
Recommandation: toutes les heures pour KPIs, quotidien pour agent perf.';

-- ============================================================================
-- VUES HELPERS pour API
-- ============================================================================

-- Vue pour KPIs agreges par periode
CREATE OR REPLACE VIEW v_kpi_summary AS
SELECT
    'today' as period,
    SUM(total_amount) as total_collected,
    SUM(completed_count) as total_transactions,
    AVG(avg_amount) as avg_transaction,
    SUM(sla_breached_count) as sla_breaches
FROM mv_treasury_daily_kpis
WHERE report_date = CURRENT_DATE

UNION ALL

SELECT
    'week' as period,
    SUM(total_amount),
    SUM(completed_count),
    AVG(avg_amount),
    SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('week', CURRENT_DATE)

UNION ALL

SELECT
    'month' as period,
    SUM(total_amount),
    SUM(completed_count),
    AVG(avg_amount),
    SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)

UNION ALL

SELECT
    'year' as period,
    SUM(total_amount),
    SUM(completed_count),
    AVG(avg_amount),
    SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('year', CURRENT_DATE);

-- Vue pour top methodes de paiement
CREATE OR REPLACE VIEW v_top_payment_methods AS
SELECT
    payment_method,
    SUM(completed_count) as transaction_count,
    SUM(total_amount) as total_amount,
    ROUND(
        SUM(total_amount)::numeric /
        NULLIF(SUM(SUM(total_amount)) OVER (), 0)::numeric * 100, 2
    ) as percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY payment_method
ORDER BY total_amount DESC;

-- Vue pour top ministeres
CREATE OR REPLACE VIEW v_top_ministries AS
SELECT
    ministry_id,
    ministry_name,
    SUM(completed_count) as transaction_count,
    SUM(total_amount) as total_amount
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)
  AND ministry_id IS NOT NULL
GROUP BY ministry_id, ministry_name
ORDER BY total_amount DESC
LIMIT 10;

-- ============================================================================
-- PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name) VALUES
('treasury.stats.view', 'treasury_stats', 'view', 'Ver KPIs y estadisticas Treasury', false, 'treasury'),
('treasury.audit.view', 'treasury_audit', 'view', 'Ver historial de auditoria Treasury', false, 'treasury')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PREMIER RAFRAICHISSEMENT
-- ============================================================================

-- Rafraichir les vues apres creation (sans CONCURRENTLY car premiere fois)
REFRESH MATERIALIZED VIEW mv_treasury_daily_kpis;
REFRESH MATERIALIZED VIEW mv_agent_performance;
REFRESH MATERIALIZED VIEW mv_reconciliation_stats;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT
    schemaname,
    matviewname,
    ispopulated
FROM pg_matviews
WHERE matviewname LIKE 'mv_%'
ORDER BY matviewname;
