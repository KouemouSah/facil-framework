-- Migration 184: Fix workflow_menu_mapping.menu_title_key to match i18n keys
-- DB had Spanish-style keys (agent.nav.pasaporte) but i18n files use English-style (agent.nav.passports)
-- This caused MISSING_MESSAGE errors in the frontend

UPDATE workflow_menu_mapping SET menu_title_key = 'agent.nav.passports' WHERE workflow_pattern = 'PASAPORTE_%';
UPDATE workflow_menu_mapping SET menu_title_key = 'agent.nav.residences' WHERE workflow_pattern = 'RESIDENCIA_%';
UPDATE workflow_menu_mapping SET menu_title_key = 'agent.nav.licenses' WHERE workflow_pattern = 'CONDUCIR_%';
UPDATE workflow_menu_mapping SET menu_title_key = 'agent.nav.vehicles' WHERE workflow_pattern = 'VEHICULO_%';
UPDATE workflow_menu_mapping SET menu_title_key = 'agent.nav.contracts' WHERE workflow_pattern = 'CONTRATO_%';
