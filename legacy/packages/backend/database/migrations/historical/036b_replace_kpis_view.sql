-- ============================================================================
-- Migration 036b: REPLACE mv_treasury_daily_kpis avec JOIN service_requests
-- ============================================================================
-- A utiliser SI la vue materialisee existe deja
-- Cette migration DROP et RECREATE la vue (pas de donnees persistantes)
-- ============================================================================

-- Supprimer l'ancienne vue et ses dependances
DROP MATERIALIZED VIEW IF EXISTS mv_treasury_daily_kpis CASCADE;

-- Recreer avec la nouvelle structure incluant service_requests
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

-- Recreer les index
CREATE UNIQUE INDEX idx_mv_kpis_unique
    ON mv_treasury_daily_kpis(report_date, payment_method, COALESCE(ministry_id, 0), service_code, COALESCE(workflow_code, ''), COALESCE(solicitud_type, ''));

CREATE INDEX idx_mv_kpis_date ON mv_treasury_daily_kpis(report_date DESC);
CREATE INDEX idx_mv_kpis_method ON mv_treasury_daily_kpis(payment_method);
CREATE INDEX idx_mv_kpis_ministry ON mv_treasury_daily_kpis(ministry_id);
CREATE INDEX idx_mv_kpis_workflow ON mv_treasury_daily_kpis(workflow_code) WHERE workflow_code IS NOT NULL;

-- Mettre a jour le commentaire
COMMENT ON MATERIALIZED VIEW mv_treasury_daily_kpis IS
'KPIs journaliers agreges pour dashboard Treasury.
Inclut les donnees service_requests (workflow_code, solicitud_type).
Rafraichir via: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_treasury_daily_kpis;';

-- Recreer/Mettre a jour les vues dependantes
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

-- Vue top methodes avec workflow
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

-- Vue top workflows (nouveau!)
CREATE OR REPLACE VIEW v_top_workflows AS
SELECT
    workflow_code,
    solicitud_type,
    SUM(completed_count) as transaction_count,
    SUM(total_amount) as total_amount,
    ROUND(
        SUM(total_amount)::numeric /
        NULLIF(SUM(SUM(total_amount)) OVER (), 0)::numeric * 100, 2
    ) as percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)
  AND workflow_code IS NOT NULL
GROUP BY workflow_code, solicitud_type
ORDER BY total_amount DESC
LIMIT 10;

-- Rafraichir la vue
REFRESH MATERIALIZED VIEW mv_treasury_daily_kpis;

-- Verification
SELECT
    'Colonnes' as check_type,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'mv_treasury_daily_kpis'
ORDER BY ordinal_position;
