-- Migration 308: Add representante_legal column to companies (NOT NULL)
--
-- The legal representative name is extracted from the certificado_padron
-- OCR (field empresa.representante_legal) but was never stored.
-- Critical for the license certificate (CLC document).
--
-- For AUTONOMO: representante = owner/proprietor
-- For SL/SA: representante = appointed administrator
--
-- This column is REQUIRED — every company must have a legal representative.

ALTER TABLE companies
ADD COLUMN IF NOT EXISTS representante_legal VARCHAR(255);

-- Populate existing companies from their owner (temporary seed data)
UPDATE companies c
SET representante_legal = COALESCE(
    (SELECT u.first_name || ' ' || u.last_name
     FROM user_company_roles ucr
     JOIN users u ON u.id = ucr.user_id
     WHERE ucr.company_id = c.id AND ucr.role = 'company_owner'
     LIMIT 1),
    'Representante Legal'
)
WHERE representante_legal IS NULL;

-- Make NOT NULL after populating
ALTER TABLE companies ALTER COLUMN representante_legal SET NOT NULL;

COMMENT ON COLUMN companies.representante_legal IS
  'Legal representative name — extracted from certificado_padron OCR or set by admin. NOT NULL.';
