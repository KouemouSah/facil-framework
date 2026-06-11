-- Migration 087: Create workflow_display_config table
-- Purpose: Allow customization of PendingPage columns and sections per workflow
-- Date: 2026-02-01

-- =============================================================================
-- CREATE TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS workflow_display_config (
    id SERIAL PRIMARY KEY,
    workflow_pattern VARCHAR(50) NOT NULL UNIQUE,

    -- Configuration for list view (columns to display)
    -- Default: reference, fullName, solicitudType, createdAt, status, priority
    list_columns JSONB NOT NULL DEFAULT '["reference", "fullName", "solicitudType", "createdAt", "status", "priority"]',

    -- Configuration for preview panel (sections to display)
    preview_sections JSONB NOT NULL DEFAULT '["info", "extractedData", "documents", "contact", "appointment"]',

    -- Custom labels (optional, for overriding default translations)
    labels JSONB DEFAULT '{}',

    -- Metadata
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comment
COMMENT ON TABLE workflow_display_config IS 'Configuration for PendingPage display per workflow pattern';
COMMENT ON COLUMN workflow_display_config.workflow_pattern IS 'SQL LIKE pattern to match workflows (e.g., PASAPORTE_%)';
COMMENT ON COLUMN workflow_display_config.list_columns IS 'Array of column IDs to show in request list';
COMMENT ON COLUMN workflow_display_config.preview_sections IS 'Array of section IDs to show in request preview';
COMMENT ON COLUMN workflow_display_config.labels IS 'Custom labels for overriding translations';

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_workflow_display_config_pattern
    ON workflow_display_config(workflow_pattern);

CREATE INDEX IF NOT EXISTS idx_workflow_display_config_active
    ON workflow_display_config(is_active)
    WHERE is_active = true;

-- =============================================================================
-- TRIGGER FOR updated_at
-- =============================================================================

CREATE TRIGGER tr_workflow_display_config_updated_at
    BEFORE UPDATE ON workflow_display_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SEED DATA - Only migrated workflows (PASAPORTE)
-- Other workflows will be added after their migration to new architecture
-- =============================================================================

INSERT INTO workflow_display_config (workflow_pattern, list_columns, preview_sections, labels) VALUES
-- Passports (only migrated workflow as of 2026-02-01)
-- Uses only validated system columns from service_requests table
('PASAPORTE_%',
 '["reference", "fullName", "solicitudType", "createdAt", "priority", "status"]'::jsonb,
 '["info", "extractedData", "documents", "contact", "appointment"]'::jsonb,
 '{"pageTitle": "agent.pending.passportRequests"}'::jsonb)

ON CONFLICT (workflow_pattern) DO NOTHING;

-- NOTE: Add more workflow configurations here after their migration:
-- RESIDENCIA_%, CONDUCIR_%, VEHICULO_%, CERTIFICADO_%, VERIFICACION_%, PAGO_%

-- =============================================================================
-- GRANT PERMISSIONS (if needed)
-- =============================================================================

-- Grant read access to authenticated users
-- GRANT SELECT ON workflow_display_config TO authenticated;
-- GRANT ALL ON workflow_display_config TO service_role;
