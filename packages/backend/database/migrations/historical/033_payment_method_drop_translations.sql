-- Migration 033: Remove translation columns from payment_method_configurations
-- Translations are handled via the unified translations system (entity_translations table)
-- Date: 2026-01-08

-- Drop the label_fr and label_en columns
ALTER TABLE payment_method_configurations
DROP COLUMN IF EXISTS label_fr,
DROP COLUMN IF EXISTS label_en;

-- Add comment to document the change
COMMENT ON TABLE payment_method_configurations IS
'Payment method configurations. Translations for labels are managed via entity_translations table with entity_type=payment_method';

-- Verify the change
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'payment_method_configurations'
AND table_schema = 'public'
ORDER BY ordinal_position;
