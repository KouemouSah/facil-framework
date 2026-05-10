-- Migration 213: Add public_installment_visible toggle to service_bundles
-- Controls whether installment preview is shown on public /licencias-comerciales page
-- Default: false (hidden). Admin can enable per bundle when ready.

ALTER TABLE service_bundles
ADD COLUMN IF NOT EXISTS public_installment_visible BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN service_bundles.public_installment_visible
IS 'Whether to show installment payment preview on public licencias-comerciales page';
