-- Migration 053: Unify assignments table for entire application
-- Part of Phase 3: Agent Unification
--
-- Changes:
-- 1. Rename declaration_id → item_id (generic for any module)
-- 2. Rename declaration_type → item_type (generic for any module)
-- 3. Drop deprecated columns: agent_id, assigned_by, reassigned_to
-- 4. Make agent_profile_id NOT NULL
-- 5. Create generic views + module-specific views
--
-- Supported item_types:
-- - Tax declarations: 'iva_declaration', 'income_tax', 'corporate_tax', etc.
-- - Service requests: 'pasaporte_nuevo', 'residencia', 'carnet_conducir', etc. (workflow_code)
-- - Future modules: payments, documents, etc.

BEGIN;

-- ============================================================================
-- STEP 1: Verify no data exists (safety check)
-- ============================================================================

DO $$
DECLARE
    row_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count FROM assignments;
    IF row_count > 0 THEN
        RAISE EXCEPTION 'assignments table has % rows. Migration requires empty table or manual data review.', row_count;
    END IF;
    RAISE NOTICE 'Safety check passed: assignments table is empty';
END $$;

-- ============================================================================
-- STEP 2: Drop dependent views
-- ============================================================================

DROP VIEW IF EXISTS v_active_assignments CASCADE;
DROP VIEW IF EXISTS v_agent_assignment_history CASCADE;
DROP VIEW IF EXISTS v_assignments_with_profiles CASCADE;

-- ============================================================================
-- STEP 3: Drop Foreign Key constraints on deprecated columns
-- ============================================================================

ALTER TABLE assignments DROP CONSTRAINT IF EXISTS fk_assignments_agent_id;
ALTER TABLE assignments DROP CONSTRAINT IF EXISTS assignments_agent_id_fkey;
ALTER TABLE assignments DROP CONSTRAINT IF EXISTS fk_assignments_assigned_by;
ALTER TABLE assignments DROP CONSTRAINT IF EXISTS assignments_assigned_by_fkey;
ALTER TABLE assignments DROP CONSTRAINT IF EXISTS fk_assignments_reassigned_to;
ALTER TABLE assignments DROP CONSTRAINT IF EXISTS assignments_reassigned_to_fkey;

-- ============================================================================
-- STEP 4: Drop Indexes on deprecated columns
-- ============================================================================

DROP INDEX IF EXISTS idx_assignments_agent_id;
DROP INDEX IF EXISTS idx_assignments_assigned_by;
DROP INDEX IF EXISTS idx_assignments_agent_status;
DROP INDEX IF EXISTS idx_assignments_declaration;

-- ============================================================================
-- STEP 5: Drop deprecated columns
-- ============================================================================

ALTER TABLE assignments DROP COLUMN IF EXISTS agent_id;
ALTER TABLE assignments DROP COLUMN IF EXISTS assigned_by;
ALTER TABLE assignments DROP COLUMN IF EXISTS reassigned_to;

-- ============================================================================
-- STEP 6: Rename columns for generic usage
-- ============================================================================

-- Rename declaration_id → item_id
ALTER TABLE assignments RENAME COLUMN declaration_id TO item_id;

-- Rename declaration_type → item_type
ALTER TABLE assignments RENAME COLUMN declaration_type TO item_type;

-- Add comments
COMMENT ON COLUMN assignments.item_id IS
    'UUID of the assigned item (tax_declarations.id, service_requests.id, etc.)';

COMMENT ON COLUMN assignments.item_type IS
    'Type of the assigned item: declaration types (iva_declaration, income_tax) or workflow codes (pasaporte_nuevo, residencia)';

-- ============================================================================
-- STEP 7: Make agent_profile_id NOT NULL
-- ============================================================================

ALTER TABLE assignments DROP CONSTRAINT IF EXISTS fk_assignments_agent_profile;
ALTER TABLE assignments
ADD CONSTRAINT fk_assignments_agent_profile
FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles(id)
ON DELETE RESTRICT ON UPDATE NO ACTION;

ALTER TABLE assignments ALTER COLUMN agent_profile_id SET NOT NULL;

-- ============================================================================
-- STEP 8: Create new indexes with renamed columns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_assignments_item
ON assignments(item_id, item_type);

CREATE INDEX IF NOT EXISTS idx_assignments_agent_profile_status
ON assignments(agent_profile_id, status);

-- ============================================================================
-- STEP 9: Create GENERIC views (for all modules)
-- ============================================================================

-- ==========================================================================
-- VIEW: v_assignments_with_profiles (comprehensive - all modules)
-- ==========================================================================
CREATE OR REPLACE VIEW v_assignments_with_profiles AS
SELECT
    a.id,
    a.item_id,
    a.item_type,
    a.agent_profile_id,
    a.assigned_by_profile_id,
    a.assignment_method,
    a.status,
    a.notes,
    a.auto_assignment_score,
    a.score_breakdown,
    a.rule_applied_id,
    a.assigned_at,
    a.started_at,
    a.completed_at,
    a.processing_duration_hours,
    a.deadline,
    a.deadline_met,
    a.priority_level,
    a.reassigned_to_profile_id,
    a.reassigned_at,
    a.reassignment_reason,
    a.reassignment_notes,
    a.validation_status,
    a.quality_score,
    a.created_at,
    a.updated_at,
    -- Agent profile details
    ap.agent_type,
    ap.is_supervisor AS agent_is_supervisor,
    ap.ministry_id AS agent_ministry_id,
    ap.entity_id AS agent_entity_id,
    ap.user_id AS agent_user_id,
    u.full_name AS agent_full_name,
    u.email AS agent_email,
    -- Assigned by profile details
    abp.agent_type AS assigned_by_agent_type,
    abp.is_supervisor AS assigned_by_is_supervisor,
    abp.user_id AS assigned_by_user_id,
    abu.full_name AS assigned_by_full_name,
    abu.email AS assigned_by_email,
    -- Reassigned to profile details
    rtp.agent_type AS reassigned_to_agent_type,
    rtp.is_supervisor AS reassigned_to_is_supervisor,
    rtp.user_id AS reassigned_to_user_id,
    rtu.full_name AS reassigned_to_full_name,
    -- Ministry/Entity names
    m.name_es AS agent_ministry_name,
    e.name AS agent_entity_name
FROM assignments a
JOIN agent_profiles ap ON a.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
LEFT JOIN agent_profiles abp ON a.assigned_by_profile_id = abp.id
LEFT JOIN users abu ON abp.user_id = abu.id
LEFT JOIN agent_profiles rtp ON a.reassigned_to_profile_id = rtp.id
LEFT JOIN users rtu ON rtp.user_id = rtu.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id;

COMMENT ON VIEW v_assignments_with_profiles IS
    'Unified assignments with agent profiles - works for all modules (declarations, service_requests, etc.)';

-- ==========================================================================
-- VIEW: v_active_assignments (active - all modules)
-- ==========================================================================
CREATE OR REPLACE VIEW v_active_assignments AS
SELECT
    a.id AS assignment_id,
    a.item_id,
    a.item_type,
    a.agent_profile_id,
    ap.user_id AS agent_user_id,
    u.full_name AS agent_name,
    u.email AS agent_email,
    ap.ministry_id,
    m.ministry_code,
    ap.entity_id,
    e.code AS entity_code,
    a.status AS assignment_status,
    a.priority_level,
    a.assigned_at,
    a.deadline,
    ROUND(EXTRACT(EPOCH FROM (NOW() - a.assigned_at)) / 3600, 2) AS hours_since_assigned,
    CASE
        WHEN a.deadline IS NOT NULL AND NOW() > a.deadline THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN a.deadline IS NOT NULL THEN ROUND(EXTRACT(EPOCH FROM (a.deadline - NOW())) / 3600, 2)
        ELSE NULL
    END AS hours_until_deadline
FROM assignments a
JOIN agent_profiles ap ON a.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id
WHERE a.status IN ('assigned', 'in_progress', 'pending_review');

COMMENT ON VIEW v_active_assignments IS
    'Active assignments (all modules) - status: assigned, in_progress, pending_review';

-- ==========================================================================
-- VIEW: v_agent_assignment_history (history - all modules)
-- ==========================================================================
CREATE OR REPLACE VIEW v_agent_assignment_history AS
SELECT
    a.id AS assignment_id,
    a.item_id,
    a.item_type,
    a.agent_profile_id,
    ap.user_id AS agent_user_id,
    u.full_name AS agent_name,
    ap.ministry_id,
    m.ministry_code,
    ap.entity_id,
    e.code AS entity_code,
    a.status AS assignment_status,
    a.priority_level,
    a.assignment_method,
    a.assigned_at,
    a.completed_at,
    a.deadline,
    a.notes,
    CASE
        WHEN a.completed_at IS NOT NULL THEN ROUND(EXTRACT(EPOCH FROM (a.completed_at - a.assigned_at)) / 3600, 2)
        ELSE NULL
    END AS total_hours
FROM assignments a
JOIN agent_profiles ap ON a.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id;

COMMENT ON VIEW v_agent_assignment_history IS
    'Full assignment history (all modules) for agent performance tracking';

-- ============================================================================
-- STEP 10: Create SERVICE_REQUESTS specific views
-- ============================================================================

-- ==========================================================================
-- VIEW: v_service_request_assignments (full details)
-- ==========================================================================
CREATE OR REPLACE VIEW v_service_request_assignments AS
SELECT
    a.id AS assignment_id,
    a.item_id AS service_request_id,
    a.item_type AS workflow_code,
    a.agent_profile_id,
    a.assigned_by_profile_id,
    a.assignment_method,
    a.status AS assignment_status,
    a.notes AS assignment_notes,
    a.priority_level AS assignment_priority,
    a.assigned_at,
    a.started_at,
    a.completed_at AS assignment_completed_at,
    a.deadline AS assignment_deadline,
    a.deadline_met,
    a.reassigned_to_profile_id,
    a.reassigned_at,
    a.reassignment_reason,
    a.quality_score,
    -- Agent profile details
    ap.agent_type,
    ap.is_supervisor AS agent_is_supervisor,
    ap.ministry_id AS agent_ministry_id,
    ap.entity_id AS agent_entity_id,
    ap.user_id AS agent_user_id,
    u.full_name AS agent_full_name,
    u.email AS agent_email,
    -- Service request details
    sr.reference AS service_request_reference,
    sr.user_id AS requester_user_id,
    req_user.full_name AS requester_name,
    req_user.email AS requester_email,
    sr.solicitud_type,
    sr.status AS service_request_status,
    sr.priority AS service_request_priority,
    sr.total_amount,
    sr.currency,
    sr.payment_status,
    sr.entity_code AS service_entity_code,
    sr.entity_location_id,
    sr.cita_date,
    sr.cita_time,
    sr.cita_location,
    sr.submitted_at,
    sr.validated_at,
    sr.completed_at AS service_completed_at,
    sr.notes AS service_request_notes,
    sr.rejection_reason,
    -- Ministry/Entity names
    m.name_es AS agent_ministry_name,
    e.name AS agent_entity_name
FROM assignments a
JOIN agent_profiles ap ON a.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
JOIN service_requests sr ON a.item_id = sr.id
JOIN users req_user ON sr.user_id = req_user.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id;

COMMENT ON VIEW v_service_request_assignments IS
    'Service request assignments with full details (joins assignments + service_requests)';

-- ==========================================================================
-- VIEW: v_active_service_request_assignments (for agent dashboards)
-- ==========================================================================
CREATE OR REPLACE VIEW v_active_service_request_assignments AS
SELECT
    a.id AS assignment_id,
    a.item_id AS service_request_id,
    a.item_type AS workflow_code,
    a.agent_profile_id,
    ap.user_id AS agent_user_id,
    u.full_name AS agent_name,
    u.email AS agent_email,
    ap.ministry_id,
    m.ministry_code,
    ap.entity_id,
    e.code AS entity_code,
    a.status AS assignment_status,
    a.priority_level AS assignment_priority,
    a.assigned_at,
    a.deadline AS assignment_deadline,
    -- Service request details
    sr.reference AS service_request_reference,
    sr.solicitud_type,
    sr.status AS service_request_status,
    sr.priority AS service_request_priority,
    sr.total_amount,
    sr.payment_status,
    sr.cita_date,
    sr.cita_time,
    req_user.full_name AS requester_name,
    -- Timing calculations
    ROUND(EXTRACT(EPOCH FROM (NOW() - a.assigned_at)) / 3600, 2) AS hours_since_assigned,
    CASE
        WHEN a.deadline IS NOT NULL AND NOW() > a.deadline THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN a.deadline IS NOT NULL THEN ROUND(EXTRACT(EPOCH FROM (a.deadline - NOW())) / 3600, 2)
        ELSE NULL
    END AS hours_until_deadline
FROM assignments a
JOIN agent_profiles ap ON a.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
JOIN service_requests sr ON a.item_id = sr.id
JOIN users req_user ON sr.user_id = req_user.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id
WHERE a.status IN ('assigned', 'in_progress', 'pending_review');

COMMENT ON VIEW v_active_service_request_assignments IS
    'Active service request assignments for agent dashboards';

-- ============================================================================
-- STEP 11: Create TAX_DECLARATIONS specific views
-- ============================================================================

-- ==========================================================================
-- VIEW: v_declaration_assignments (full details)
-- ==========================================================================
CREATE OR REPLACE VIEW v_declaration_assignments AS
SELECT
    a.id AS assignment_id,
    a.item_id AS declaration_id,
    a.item_type AS declaration_type,
    a.agent_profile_id,
    a.assigned_by_profile_id,
    a.assignment_method,
    a.status AS assignment_status,
    a.notes AS assignment_notes,
    a.priority_level AS assignment_priority,
    a.assigned_at,
    a.started_at,
    a.completed_at AS assignment_completed_at,
    a.deadline AS assignment_deadline,
    a.deadline_met,
    a.reassigned_to_profile_id,
    a.reassigned_at,
    a.reassignment_reason,
    a.quality_score,
    -- Agent profile details
    ap.agent_type,
    ap.is_supervisor AS agent_is_supervisor,
    ap.ministry_id AS agent_ministry_id,
    ap.entity_id AS agent_entity_id,
    ap.user_id AS agent_user_id,
    u.full_name AS agent_full_name,
    u.email AS agent_email,
    -- Tax declaration details
    td.declaration_number AS declaration_reference,
    td.user_id AS taxpayer_user_id,
    taxpayer.full_name AS taxpayer_name,
    taxpayer.email AS taxpayer_email,
    td.fiscal_year,
    td.fiscal_period,
    td.status AS declaration_status,
    td.calculated_tax,
    td.net_tax_due,
    td.submitted_at AS declaration_submitted_at,
    td.processed_at AS declaration_processed_at,
    -- Ministry/Entity names
    m.name_es AS agent_ministry_name,
    e.name AS agent_entity_name
FROM assignments a
JOIN agent_profiles ap ON a.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
JOIN tax_declarations td ON a.item_id = td.id
JOIN users taxpayer ON td.user_id = taxpayer.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id;

COMMENT ON VIEW v_declaration_assignments IS
    'Tax declaration assignments with full details (joins assignments + tax_declarations)';

-- ==========================================================================
-- VIEW: v_active_declaration_assignments (for agent dashboards)
-- ==========================================================================
CREATE OR REPLACE VIEW v_active_declaration_assignments AS
SELECT
    a.id AS assignment_id,
    a.item_id AS declaration_id,
    a.item_type AS declaration_type,
    a.agent_profile_id,
    ap.user_id AS agent_user_id,
    u.full_name AS agent_name,
    u.email AS agent_email,
    ap.ministry_id,
    m.ministry_code,
    ap.entity_id,
    e.code AS entity_code,
    a.status AS assignment_status,
    a.priority_level AS assignment_priority,
    a.assigned_at,
    a.deadline AS assignment_deadline,
    -- Tax declaration details
    td.declaration_number AS declaration_reference,
    td.status AS declaration_status,
    td.calculated_tax,
    td.net_tax_due,
    taxpayer.full_name AS taxpayer_name,
    -- Timing calculations
    ROUND(EXTRACT(EPOCH FROM (NOW() - a.assigned_at)) / 3600, 2) AS hours_since_assigned,
    CASE
        WHEN a.deadline IS NOT NULL AND NOW() > a.deadline THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN a.deadline IS NOT NULL THEN ROUND(EXTRACT(EPOCH FROM (a.deadline - NOW())) / 3600, 2)
        ELSE NULL
    END AS hours_until_deadline
FROM assignments a
JOIN agent_profiles ap ON a.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
JOIN tax_declarations td ON a.item_id = td.id
JOIN users taxpayer ON td.user_id = taxpayer.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id
WHERE a.status IN ('assigned', 'in_progress', 'pending_review');

COMMENT ON VIEW v_active_declaration_assignments IS
    'Active tax declaration assignments for agent dashboards';

-- ============================================================================
-- STEP 12: Update table comment
-- ============================================================================

COMMENT ON TABLE assignments IS
    'Unified assignments table for all modules (tax_declarations, service_requests, etc.). Uses item_id + item_type for polymorphic references. Migration 053: Renamed declaration_id→item_id, declaration_type→item_type. Removed deprecated columns (agent_id, assigned_by, reassigned_to).';

COMMIT;
