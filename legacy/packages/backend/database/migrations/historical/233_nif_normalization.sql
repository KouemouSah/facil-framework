-- Migration 233: NIF & Registration Number Normalization
-- Part of OMS Companies Phase 1 — Database & Performance Foundation
--
-- Adds:
--   1. normalize_identifier() — IMMUTABLE function (uppercase, trim, strip spaces)
--   2. BEFORE INSERT/UPDATE trigger — auto-normalizes nif + registration_number
--   3. CHECK constraints — NIF format ^[A-Z0-9]{5,20}$, PE format ^PE-\d{3,10}$
--   4. Cross-check function — autonomo must have PE-XXXX, others must have NIF
--
-- VERIFIED against actual DB:
--   companies.nif: VARCHAR, nullable, UNIQUE partial index
--   companies.registration_number: VARCHAR, nullable, UNIQUE partial index
--   companies.forma_juridica: VARCHAR, nullable
--   Existing trigger: trigger_update_companies (BEFORE UPDATE, updated_at)
--   Existing CHECK: companies_regimen_fiscal_check

BEGIN;

-- ════════════════════════════════════════════════════════════════════
-- 1. Normalization function (reusable for any identifier)
-- ════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION normalize_identifier(val TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT UPPER(TRIM(REGEXP_REPLACE(val, '\s+', '', 'g')))
$$;

COMMENT ON FUNCTION normalize_identifier(TEXT) IS
    'Normalize identifiers: uppercase, trim whitespace, strip internal spaces. '
    'IMMUTABLE for index compatibility.';

-- ════════════════════════════════════════════════════════════════════
-- 2. Trigger function: normalize + cross-check on INSERT/UPDATE
-- ════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION trg_normalize_company_identifiers()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Normalize NIF (uppercase, trim, strip spaces)
    IF NEW.nif IS NOT NULL AND NEW.nif != '' THEN
        NEW.nif := normalize_identifier(NEW.nif);
    ELSE
        NEW.nif := NULL;  -- empty string → NULL (for UNIQUE index)
    END IF;

    -- Normalize registration_number
    IF NEW.registration_number IS NOT NULL AND NEW.registration_number != '' THEN
        NEW.registration_number := normalize_identifier(NEW.registration_number);
    ELSE
        NEW.registration_number := NULL;
    END IF;

    -- Normalize forma_juridica (lowercase for consistency)
    IF NEW.forma_juridica IS NOT NULL THEN
        NEW.forma_juridica := LOWER(TRIM(NEW.forma_juridica));
    END IF;

    -- Cross-check: autonomo ↔ PE-XXXX (WARNING via RAISE NOTICE, not blocking)
    -- Blocking would break CSV import with partial data
    IF NEW.forma_juridica = 'autonomo' THEN
        IF NEW.registration_number IS NULL AND NEW.nif IS NOT NULL THEN
            RAISE NOTICE 'Company %: autonomo should have registration_number (PE-XXXX), has NIF instead',
                NEW.legal_name;
        END IF;
    ELSIF NEW.forma_juridica IS NOT NULL AND NEW.forma_juridica != '' THEN
        IF NEW.nif IS NULL AND NEW.registration_number IS NOT NULL
           AND NEW.registration_number LIKE 'PE-%' THEN
            RAISE NOTICE 'Company %: non-autonomo (%) has PE-format registration_number',
                NEW.legal_name, NEW.forma_juridica;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

-- Trigger fires BEFORE INSERT and UPDATE, BEFORE the existing updated_at trigger
CREATE TRIGGER trg_company_normalize_identifiers
    BEFORE INSERT OR UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION trg_normalize_company_identifiers();

-- ════════════════════════════════════════════════════════════════════
-- 3. CHECK constraints (soft — allow NULL, validate format if present)
-- ════════════════════════════════════════════════════════════════════

-- NIF: 5-20 alphanumeric chars (post-normalization = uppercase)
ALTER TABLE companies
    ADD CONSTRAINT chk_companies_nif_format
    CHECK (nif IS NULL OR nif ~ '^[A-Z0-9]{5,20}$');

-- Registration number: either PE-XXXX format or general alphanumeric
-- PE-XXXX: PE- followed by 3-10 digits
-- Other: 3-30 alphanumeric + hyphens (for non-PE registrations)
ALTER TABLE companies
    ADD CONSTRAINT chk_companies_reg_num_format
    CHECK (
        registration_number IS NULL
        OR registration_number ~ '^PE-[0-9]{3,10}$'
        OR registration_number ~ '^[A-Z0-9-]{3,30}$'
    );

-- ════════════════════════════════════════════════════════════════════
-- 4. Normalize existing data (if any)
-- ════════════════════════════════════════════════════════════════════

-- Normalize existing NIFs
UPDATE companies
SET nif = normalize_identifier(nif)
WHERE nif IS NOT NULL AND nif != normalize_identifier(nif);

-- Normalize existing registration_numbers
UPDATE companies
SET registration_number = normalize_identifier(registration_number)
WHERE registration_number IS NOT NULL
  AND registration_number != normalize_identifier(registration_number);

-- Clean empty strings to NULL
UPDATE companies SET nif = NULL WHERE nif = '';
UPDATE companies SET registration_number = NULL WHERE registration_number = '';

COMMIT;
