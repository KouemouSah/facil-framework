-- Migration 311: Add certificate_url + certificate_number to commercial_licenses
--
-- The certificate PDF is generated and stored in Firebase when license
-- reaches 'complete' status, but the URL was never persisted in BD.
-- Without this, the citizen can't re-download the certificate.

ALTER TABLE commercial_licenses
ADD COLUMN IF NOT EXISTS certificate_number VARCHAR(50) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS certificate_url TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS certificate_generated_at TIMESTAMPTZ DEFAULT NULL;

COMMENT ON COLUMN commercial_licenses.certificate_number IS 'CLC-YYYY-CITY-ZONE-XXXXX format';
COMMENT ON COLUMN commercial_licenses.certificate_url IS 'Firebase Storage URL of the generated certificate PDF';
COMMENT ON COLUMN commercial_licenses.certificate_generated_at IS 'When the certificate was generated';
