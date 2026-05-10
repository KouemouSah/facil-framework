-- ============================================================================
-- Migration 049: Add hierarchical workflow columns
-- ============================================================================
-- Purpose:
--   1. Add parent_workflow_code for hierarchical grouping in UI
--   2. Add tags for sub-categorization
--   3. Add is_parent flag for category headers
--
-- NOTE: This migration only adds columns. Data synchronization (tariffs,
-- parent relationships, tags) should be done via Python scripts that read
-- from the predefined workflow classes (source of truth).
--
-- Date: 2025-01-16
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ADD HIERARCHICAL COLUMNS TO WORKFLOWS TABLE
-- ============================================================================

-- Add parent_workflow_code for grouping (e.g., all PASAPORTE_* share parent PASAPORTE)
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS parent_workflow_code VARCHAR(50);

-- Add tags for sub-categorization (JSONB array: ["pasaporte", "identidad"])
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;

-- Add is_parent flag to identify parent workflows (for UI grouping)
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS is_parent BOOLEAN DEFAULT FALSE;

-- Index for parent lookup
CREATE INDEX IF NOT EXISTS idx_workflows_parent ON workflows(parent_workflow_code);
CREATE INDEX IF NOT EXISTS idx_workflows_tags ON workflows USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_workflows_is_parent ON workflows(is_parent) WHERE is_parent = TRUE;

COMMENT ON COLUMN workflows.parent_workflow_code IS 'For hierarchical grouping in admin UI - e.g., PASAPORTE_NUEVO has parent PASAPORTE';
COMMENT ON COLUMN workflows.tags IS 'JSONB array of tags for sub-categorization';
COMMENT ON COLUMN workflows.is_parent IS 'TRUE = this is a parent workflow (category header in UI)';

-- ============================================================================
-- 2. CREATE VIEW FOR HIERARCHICAL WORKFLOWS
-- ============================================================================

DROP VIEW IF EXISTS v_workflows_hierarchy;

CREATE VIEW v_workflows_hierarchy AS
SELECT
    w.code,
    w.name_es,
    w.description_es,
    w.category,
    w.entity_code,
    w.workflow_type,
    w.requires_agent_validation,
    w.requires_appointment,
    w.is_generic,
    COALESCE(w.is_parent, FALSE) as is_parent,
    w.parent_workflow_code,
    COALESCE(w.tags, '[]'::jsonb) as tags,
    w.sla_hours,
    w.display_order,
    w.is_active,
    pw.name_es as parent_name_es,
    (SELECT COUNT(*) FROM workflow_document_requirements WHERE workflow_code = w.code) as documents_count,
    (SELECT COUNT(*) FROM workflow_tariffs WHERE workflow_code = w.code AND is_active = TRUE) as tariffs_count,
    (SELECT jsonb_agg(jsonb_build_object(
        'solicitud_type', wt.solicitud_type,
        'amount', wt.amount,
        'tariff_type', wt.tariff_type,
        'percentage_rate', wt.percentage_rate
    )) FROM workflow_tariffs wt WHERE wt.workflow_code = w.code AND wt.is_active = TRUE) as tariffs
FROM workflows w
LEFT JOIN workflows pw ON w.parent_workflow_code = pw.code
ORDER BY w.display_order, w.code;

COMMENT ON VIEW v_workflows_hierarchy IS 'Workflows with parent relationship and tariffs for hierarchical admin UI';

COMMIT;
