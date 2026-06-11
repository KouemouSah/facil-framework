-- ============================================================================
-- Migration 034b: ALTER payment_anomalies - Ajouter colonnes service_request
-- ============================================================================
-- A utiliser SI la table payment_anomalies existe deja et contient des donnees
-- ============================================================================

-- Ajouter les colonnes service_request si elles n'existent pas
DO $$
BEGIN
    -- Ajouter service_request_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'payment_anomalies' AND column_name = 'service_request_id'
    ) THEN
        ALTER TABLE payment_anomalies
        ADD COLUMN service_request_id UUID REFERENCES service_requests(id) ON DELETE SET NULL;

        RAISE NOTICE 'Colonne service_request_id ajoutee';
    ELSE
        RAISE NOTICE 'Colonne service_request_id existe deja';
    END IF;

    -- Ajouter service_request_reference
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'payment_anomalies' AND column_name = 'service_request_reference'
    ) THEN
        ALTER TABLE payment_anomalies
        ADD COLUMN service_request_reference VARCHAR(50);

        RAISE NOTICE 'Colonne service_request_reference ajoutee';
    ELSE
        RAISE NOTICE 'Colonne service_request_reference existe deja';
    END IF;
END $$;

-- Creer l'index si il n'existe pas
CREATE INDEX IF NOT EXISTS idx_anomalies_service_request
ON payment_anomalies(service_request_id)
WHERE service_request_id IS NOT NULL;

-- Mettre a jour la fonction detect_duplicate_payments
CREATE OR REPLACE FUNCTION detect_duplicate_payments()
RETURNS TABLE (
    payment_id_1 UUID,
    payment_id_2 UUID,
    service_request_id_1 UUID,
    service_request_id_2 UUID,
    service_request_ref_1 VARCHAR,
    service_request_ref_2 VARCHAR,
    user_id UUID,
    amount NUMERIC,
    time_diff INTERVAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp1.id as payment_id_1,
        sp2.id as payment_id_2,
        sp1.service_request_id as service_request_id_1,
        sp2.service_request_id as service_request_id_2,
        sr1.reference as service_request_ref_1,
        sr2.reference as service_request_ref_2,
        sp1.user_id,
        sp1.total_amount as amount,
        sp2.created_at - sp1.created_at as time_diff
    FROM service_payments sp1
    JOIN service_payments sp2
        ON sp1.user_id = sp2.user_id
        AND sp1.total_amount = sp2.total_amount
        AND sp1.id < sp2.id
        AND sp2.created_at - sp1.created_at < INTERVAL '24 hours'
    LEFT JOIN service_requests sr1 ON sr1.id = sp1.service_request_id
    LEFT JOIN service_requests sr2 ON sr2.id = sp2.service_request_id
    WHERE sp1.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent')
      AND sp2.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent')
      AND NOT EXISTS (
          SELECT 1 FROM payment_anomalies pa
          WHERE pa.entity_id IN (sp1.id, sp2.id)
            AND pa.anomaly_type = 'duplicate_suspected'
            AND pa.status NOT IN ('resolved', 'false_positive')
      );
END;
$$ LANGUAGE plpgsql;

-- Mettre a jour les anomalies existantes avec service_request_id
UPDATE payment_anomalies pa
SET
    service_request_id = sp.service_request_id,
    service_request_reference = sr.reference
FROM service_payments sp
LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
WHERE pa.entity_type = 'service_payment'
  AND pa.entity_id = sp.id
  AND pa.service_request_id IS NULL;

-- Verification
SELECT
    COUNT(*) as total_anomalies,
    COUNT(service_request_id) as with_service_request,
    COUNT(*) - COUNT(service_request_id) as without_service_request
FROM payment_anomalies;
