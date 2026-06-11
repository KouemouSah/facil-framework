-- Migration 274: Add missing FK indexes + JSONB GIN indexes
-- Source: Global audit 2026-03-22 (P2-06, P2-07)
-- PostgreSQL does NOT auto-index FK columns — these cause full table scans.
--
-- Date: 2026-03-22

BEGIN;

-- ============================================================================
-- 1. MISSING FK INDEXES (prevent sequential scans on JOINs)
-- ============================================================================

-- service_payments.user_id — used in citizen dashboard "my payments"
CREATE INDEX IF NOT EXISTS idx_service_payments_user_id
    ON service_payments(user_id);

-- service_request_documents.uploaded_by — used in audit queries
CREATE INDEX IF NOT EXISTS idx_srd_uploaded_by
    ON service_request_documents(uploaded_by)
    WHERE uploaded_by IS NOT NULL;

-- entity_locations.entity_id — used in routing lookups
CREATE INDEX IF NOT EXISTS idx_entity_locations_entity_id
    ON entity_locations(entity_id);

-- field_inspections.agent_id — used in workload/agent dashboard queries
CREATE INDEX IF NOT EXISTS idx_field_inspections_agent_id
    ON field_inspections(agent_id)
    WHERE agent_id IS NOT NULL;

-- field_inspections.license_id — used in compliance/inspection history
CREATE INDEX IF NOT EXISTS idx_field_inspections_license_id
    ON field_inspections(license_id)
    WHERE license_id IS NOT NULL;

-- ============================================================================
-- 2. PARTIAL INDEXES for hot query paths
-- ============================================================================

-- Active service requests (exclude completed/cancelled — rarely queried)
CREATE INDEX IF NOT EXISTS idx_sr_active_status
    ON service_requests(status, created_at DESC)
    WHERE status NOT IN ('COMPLETED', 'CANCELLED', 'EXPIRED');

-- Pending payment validation (treasury hot path)
CREATE INDEX IF NOT EXISTS idx_sp_pending_validation
    ON service_payments(created_at DESC)
    WHERE workflow_status = 'pending_agent_review';

-- ============================================================================
-- 3. JSONB GIN INDEXES (enable @> containment queries on JSONB)
-- ============================================================================

-- service_requests.form_data — queried during form validation
CREATE INDEX IF NOT EXISTS idx_sr_form_data_gin
    ON service_requests USING GIN (form_data jsonb_path_ops);

-- service_requests.extracted_data — queried during OCR validation
CREATE INDEX IF NOT EXISTS idx_sr_extracted_data_gin
    ON service_requests USING GIN (extracted_data jsonb_path_ops);

-- service_request_documents.extraction_data — queried during processing
CREATE INDEX IF NOT EXISTS idx_srd_extraction_data_gin
    ON service_request_documents USING GIN (extraction_data jsonb_path_ops);

COMMIT;
