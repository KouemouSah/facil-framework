-- Migration 115: Dynamic custom sub-items + completed menu default
-- Adds JSONB custom_sub_items column to workflow_menu_mapping
-- This allows admins to add custom sub-menus via the UI without SQL migrations
-- Date: 2026-02-21

BEGIN;

-- A: Add custom_sub_items JSONB column
ALTER TABLE workflow_menu_mapping
    ADD COLUMN IF NOT EXISTS custom_sub_items JSONB NOT NULL DEFAULT '[]';

-- B: Seed "Completados" for ALL existing mappings (visible by default for all agents)
UPDATE workflow_menu_mapping
SET custom_sub_items = '[{
    "id": "completed",
    "title_key": "agent.nav.completed",
    "icon": "CheckCircle2",
    "action": "completed",
    "filter_params": {"status": "DOSSIER_VALIDE"},
    "display_order": 50,
    "is_active": true
}]'::jsonb
WHERE custom_sub_items = '[]'::jsonb;

COMMIT;
