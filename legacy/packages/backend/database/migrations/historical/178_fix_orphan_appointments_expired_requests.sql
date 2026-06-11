-- Migration 178: Fix orphan appointments for expired/cancelled requests
-- Problem: When payment SLA expires a request, linked appointments were not cancelled.
-- This migration retroactively cancels orphan reservations and adds a safety net.
--
-- Affected: 1 row (SRV-2026-00012, CONDUCIR_NUEVO, appointment 2026-02-17)

BEGIN;

-- 1. Cancel orphan appointment_reservations
UPDATE appointment_reservations ar
SET status = 'cancelled',
    cancelled_at = NOW(),
    cancellation_reason = 'Retroactive fix: linked request expired/cancelled (migration 178)'
FROM service_requests sr
WHERE sr.id = ar.service_request_id
  AND sr.status IN ('EXPIRED', 'CANCELLED', 'REJECTED')
  AND ar.status NOT IN ('cancelled', 'completed');

-- 2. Release orphan appointment_holds
UPDATE appointment_holds ah
SET status = 'expired'::appointment_hold_status,
    released_at = NOW()
FROM service_requests sr
WHERE sr.id = ah.service_request_id
  AND sr.status IN ('EXPIRED', 'CANCELLED', 'REJECTED')
  AND ah.status NOT IN ('expired', 'released');

-- 3. Insert missing history entry for the already-expired request
INSERT INTO service_request_history
    (id, service_request_id, action, previous_status, new_status, details, comment, performed_at)
SELECT
    gen_random_uuid(),
    sr.id,
    'status_change',
    'PAYMENT_PENDING',
    'EXPIRED',
    jsonb_build_object(
        'reason', 'payment_sla_expired',
        'payment_reference', sp.payment_reference,
        'payment_amount', sp.total_amount::text,
        'sla_days', 15,
        'retroactive_fix', true
    ),
    'Pago ' || sp.payment_reference || ' expirado tras 15 dias sin validacion. Solicitud cerrada automaticamente. (retroactive fix migration 178)',
    NOW()
FROM service_requests sr
JOIN service_payments sp ON sp.service_request_id = sr.id
WHERE sr.status = 'EXPIRED'
  AND sp.workflow_status = 'expired'
  AND NOT EXISTS (
    SELECT 1 FROM service_request_history h
    WHERE h.service_request_id = sr.id
      AND h.new_status = 'EXPIRED'
  );

COMMIT;
