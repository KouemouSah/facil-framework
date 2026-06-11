-- ============================================================================
-- Migration 038: Extend Anomaly Types for Enhanced Detection
-- ============================================================================
-- Description: Adds new anomaly types for comprehensive Treasury detection
-- Prerequisite: Migration 034 (payment_anomalies table)
-- ============================================================================

-- ============================================================================
-- 1. ADD NEW ANOMALY TYPES TO ENUM
-- ============================================================================

-- Add new types to anomaly_type_enum
-- PostgreSQL requires ALTER TYPE ... ADD VALUE

ALTER TYPE anomaly_type_enum ADD VALUE IF NOT EXISTS 'duplicate_payment';
ALTER TYPE anomaly_type_enum ADD VALUE IF NOT EXISTS 'late_validation';
ALTER TYPE anomaly_type_enum ADD VALUE IF NOT EXISTS 'orphan_transaction';
ALTER TYPE anomaly_type_enum ADD VALUE IF NOT EXISTS 'reference_missing';

-- ============================================================================
-- 2. UPDATE ENTITY TYPE CONSTRAINT
-- ============================================================================

-- Drop existing constraint
ALTER TABLE payment_anomalies DROP CONSTRAINT IF EXISTS valid_entity_type;

-- Add updated constraint including 'user' for suspicious pattern detection
ALTER TABLE payment_anomalies ADD CONSTRAINT valid_entity_type CHECK (
    entity_type IN ('service_payment', 'bank_transaction', 'payment', 'user')
);

-- ============================================================================
-- 3. ADD MISSING COLUMNS FOR ENHANCED DETECTION
-- ============================================================================

-- Add affected_amount column if not exists (for tracking financial impact)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'payment_anomalies' AND column_name = 'affected_amount'
    ) THEN
        ALTER TABLE payment_anomalies ADD COLUMN affected_amount NUMERIC(15, 2);
        COMMENT ON COLUMN payment_anomalies.affected_amount IS
            'Monto afectado por la anomalia (ej: monto duplicado, diferencia de reconciliacion)';
    END IF;
END $$;

-- Add related_entities column if not exists (for storing context)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'payment_anomalies' AND column_name = 'related_entities'
    ) THEN
        ALTER TABLE payment_anomalies ADD COLUMN related_entities JSONB;
        COMMENT ON COLUMN payment_anomalies.related_entities IS
            'Entites liees (ex: {bank_transaction_id, duplicate_count, etc.})';
    END IF;
END $$;

-- Add metadata column if not exists (for detection config/context)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'payment_anomalies' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE payment_anomalies ADD COLUMN metadata JSONB;
        COMMENT ON COLUMN payment_anomalies.metadata IS
            'Metadonnees supplementaires (user_id pour suspicious_pattern, etc.)';
    END IF;
END $$;

-- ============================================================================
-- 4. ADD INDEX FOR METADATA QUERIES
-- ============================================================================

-- Index for querying anomalies by user_id in metadata (for suspicious pattern)
CREATE INDEX IF NOT EXISTS idx_anomalies_metadata_user
    ON payment_anomalies USING gin ((metadata->'user_id'));

-- ============================================================================
-- 5. UPDATE VIEW FOR NEW TYPES
-- ============================================================================

-- Drop and recreate view to include affected_amount
DROP VIEW IF EXISTS v_anomaly_summary;

CREATE VIEW v_anomaly_summary AS
SELECT
    anomaly_type,
    severity,
    status,
    COUNT(*) as count,
    SUM(COALESCE(affected_amount, difference_amount, 0)) as total_affected,
    MIN(detected_at) as oldest_detected,
    MAX(detected_at) as newest_detected
FROM payment_anomalies
GROUP BY anomaly_type, severity, status;

COMMENT ON VIEW v_anomaly_summary IS
'Vue agregee des anomalies incluant affected_amount pour les nouveaux types';

-- ============================================================================
-- 6. MAPPING DOCUMENTATION
-- ============================================================================

-- Anomaly Type Mapping:
-- Backend Service Type      | Database Enum Value      | Description
-- --------------------------|--------------------------|---------------------------
-- duplicate_payment         | duplicate_payment        | Pagos duplicados detectados
-- amount_mismatch           | amount_mismatch          | Diferencia monto sistema vs banco
-- orphan_transaction        | orphan_transaction       | Transaccion banco sin pago
-- late_validation           | late_validation          | SLA validation excedido
-- suspicious_pattern        | suspicious_pattern       | Patron de pagos sospechoso
-- high_amount               | high_amount              | Monto inusualmente alto
-- reference_missing         | reference_missing        | Referencia de pago faltante
--
-- Legacy types (from migration 034):
-- duplicate_suspected       | duplicate_suspected      | (use duplicate_payment instead)
-- sla_breached              | sla_breached             | (use late_validation instead)
-- reconciliation_failed     | reconciliation_failed    | Fallo reconciliacion
-- validated_not_received    | validated_not_received   | Validado pero no recibido
-- manual_flag               | manual_flag              | Señalamiento manual

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify new enum values
SELECT
    t.typname as enum_name,
    array_agg(e.enumlabel ORDER BY e.enumsortorder) as values
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE t.typname = 'anomaly_type_enum'
GROUP BY t.typname;

-- Verify columns exist
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'payment_anomalies'
  AND column_name IN ('affected_amount', 'related_entities', 'metadata')
ORDER BY column_name;
