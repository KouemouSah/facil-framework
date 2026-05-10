-- ============================================================================
-- Migration 079: Add Appointment Status Columns to Service Requests
-- ============================================================================
-- Purpose:
--   Add columns to track citizen appointment attendance:
--   - appointment_status: 'arrived', 'no_show', NULL (pending)
--   - arrived_at: Timestamp when citizen arrived
--   - no_show_at: Timestamp when marked as no-show
--
-- These columns are used by agent endpoints to track appointment outcomes
-- separate from the reservation system (appointment_reservations table).
--
-- Author: Claude Code
-- Date: 2026-01-26
-- ============================================================================

BEGIN;

-- Add appointment_status column
ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS appointment_status VARCHAR(50) DEFAULT NULL;

-- Add arrived_at timestamp
ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS arrived_at TIMESTAMPTZ DEFAULT NULL;

-- Add no_show_at timestamp
ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS no_show_at TIMESTAMPTZ DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN service_requests.appointment_status IS 'Citizen attendance status: arrived, no_show, or NULL (pending)';
COMMENT ON COLUMN service_requests.arrived_at IS 'Timestamp when citizen arrived for appointment';
COMMENT ON COLUMN service_requests.no_show_at IS 'Timestamp when marked as no-show';

-- Create index for filtering by appointment_status
CREATE INDEX IF NOT EXISTS idx_service_requests_appointment_status
ON service_requests(appointment_status)
WHERE appointment_status IS NOT NULL;

COMMIT;
