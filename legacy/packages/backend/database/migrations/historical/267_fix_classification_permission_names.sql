-- Fix classification permission naming: companies.* → company.* (singular convention)
-- The migration 230 incorrectly used plural resource names.
-- All other permissions use singular resource names (company.view, company.create, etc.)

BEGIN;

-- Rename permissions to match convention
UPDATE permissions SET name = 'company.classify', resource = 'company'
WHERE name = 'companies.classify';

UPDATE permissions SET name = 'company.validate_draft', resource = 'company'
WHERE name = 'companies.validate_draft';

UPDATE permissions SET name = 'company.import_csv', resource = 'company'
WHERE name = 'companies.import_csv';

UPDATE permissions SET name = 'company.view_classification', resource = 'company'
WHERE name = 'companies.view_classification';

-- Also update role_permissions references (uses permission_id FK, so name change propagates)
-- The role_permissions table references permissions by ID, not name, so the FK is fine.
-- But we need to update any direct name references if they exist.

COMMIT;
