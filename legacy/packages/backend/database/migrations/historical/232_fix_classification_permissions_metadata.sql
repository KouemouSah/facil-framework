-- Fix: classification permissions metadata
-- is_critical was defaulted to false by migration 230 (column omitted from INSERT).
-- module_name was 'companies' (plural), should be 'company' (singular) per convention.
-- The registry bulk_create uses ON CONFLICT DO NOTHING, so it cannot self-correct.

BEGIN;

-- Fix is_critical for sensitive classification operations
UPDATE permissions
SET is_critical = true, module_name = 'company'
WHERE name IN ('company.classify', 'company.validate_draft', 'company.import_csv');

-- Fix module_name only for view_classification (is_critical stays false)
UPDATE permissions
SET module_name = 'company'
WHERE name = 'company.view_classification';

COMMIT;
