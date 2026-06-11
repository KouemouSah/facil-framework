-- Migration 291: Fix bundle dossier linking (1:1 licence ↔ service_request)
-- Date: 2026-04-11
-- Context: Plan .claude/plans/INSPECTION_BUNDLE_P1_DETAIL.md
--          Corrige les bugs B1-B7 de INSPECTION_BUNDLE_PAYMENT_FIX_PLAN.md
--          Rattrape la migration 287 qui a partiellement failed en prod.
--
-- État BD avant migration (vérifié via psycopg2 2026-04-11):
--   - service_requests.source: N'EXISTE PAS (ALTER 287 failed silencieusement)
--   - idx_sr_company_year_active: N'EXISTE PAS (CREATE INDEX 287 failed)
--   - 0 service_requests avec commercial_license_id (colonne n'existe pas)
--   - 13 commercial_licenses avec service_request_id = NULL
--   - valid_workflow_codes.FIELD_INSPECTION: EXISTS (créé 2026-04-07)
--   - workflows.BUNDLE_PAYMENT: EXISTS
--   - generate_service_request_reference: BUGGÉE (lowercase cases, pas d'advisory lock)
--
-- Décisions validées (INSPECTION_BUNDLE_P1_DETAIL.md §7):
--   D1: Patch fonction generate_service_request_reference (pas de nouvelle sequence)
--   D2: Obligations pending/overdue → payment_pending (pas paid direct)
--   D3: Recovery déterministe sur UniqueViolationError (pas de retry backoff)
--   D4: FK service_requests.commercial_license_id ON DELETE RESTRICT
--   D5: Lock ordering canonique + timeouts transaction-scoped
--
-- Stratégie: additive only, pas de destructive drops sur données existantes.
-- Idempotent: peut être rejoué sans effet de bord.

BEGIN;

-- ============================================================
-- 1. PATCH fonction generate_service_request_reference (D1)
-- ============================================================
-- Bugs corrigés dans la fonction existante:
--   BUG-A: Pas d'advisory lock → race condition possible
--          (alors que generate_batch_reference a pg_advisory_xact_lock)
--   BUG-B: Switch hardcodé lowercase ('residencia%') mais codes UPPERCASE
--          en prod → tous les refs tombent sur 'SRV' (12/12 rows prod)
--   BUG-C: Pas de cas pour BUNDLE_PAYMENT ni FIELD_INSPECTION
--
-- Action: CREATE OR REPLACE sans DROP (idempotent + safe, ne casse pas
-- les refs existantes qui sont déjà persistées).

CREATE OR REPLACE FUNCTION public.generate_service_request_reference(
    p_workflow_code character varying
) RETURNS character varying
LANGUAGE plpgsql
AS $function$
DECLARE
    v_prefix VARCHAR(10);
    v_year VARCHAR(4);
    v_sequence INTEGER;
    v_reference VARCHAR(50);
    v_code_upper VARCHAR(100);
BEGIN
    -- BUG-A FIX: Advisory lock pour sérialiser les appels concurrents
    -- Key stable = hashtext d'une chaîne connue (reproducible across restarts)
    PERFORM pg_advisory_xact_lock(hashtext('service_request_reference_gen'));

    v_code_upper := UPPER(p_workflow_code);

    -- BUG-B FIX: Matching UPPERCASE explicite
    -- BUG-C FIX: Ajout BUNDLE_PAYMENT (LIC) et FIELD_INSPECTION (FLD)
    v_prefix := CASE
        WHEN v_code_upper LIKE 'RESIDENCIA%' THEN 'RES'
        WHEN v_code_upper LIKE 'PASAPORTE%' THEN 'PAS'
        WHEN v_code_upper LIKE 'FP_CARNET_FUNCIONARIO%' THEN 'CFN'
        WHEN v_code_upper LIKE 'CONDUCIR%' THEN 'CON'
        WHEN v_code_upper LIKE 'VEHICULO%' THEN 'VHC'
        WHEN v_code_upper LIKE 'CONTRATO%' THEN 'CTR'
        WHEN v_code_upper LIKE 'FP_VERIFICACION%' THEN 'VER'
        WHEN v_code_upper LIKE 'FP_PROMOCION%' THEN 'PRO'
        WHEN v_code_upper LIKE 'FP_CERTIFICADO%' THEN 'CER'
        WHEN v_code_upper LIKE 'FP_PERMISO%' THEN 'PER'
        WHEN v_code_upper LIKE 'PRORROGA%'
             OR v_code_upper LIKE 'PERMANENCIA%'
             OR v_code_upper LIKE 'SALIDA%' THEN 'VIS'
        WHEN v_code_upper = 'BUNDLE_PAYMENT' THEN 'LIC'
        WHEN v_code_upper = 'FIELD_INSPECTION' THEN 'FLD'
        ELSE 'SRV'
    END;

    v_year := TO_CHAR(NOW(), 'YYYY');

    -- Next sequence number for this prefix+year
    -- SPLIT_PART(ref, '-', 3) = 'NNNNN' part of 'PREFIX-YYYY-NNNNN'
    SELECT COALESCE(MAX(
        CAST(NULLIF(SPLIT_PART(reference, '-', 3), '') AS INTEGER)
    ), 0) + 1
    INTO v_sequence
    FROM service_requests
    WHERE reference LIKE v_prefix || '-' || v_year || '-%';

    v_reference := v_prefix || '-' || v_year || '-' || LPAD(v_sequence::TEXT, 5, '0');

    RETURN v_reference;
END;
$function$;

COMMENT ON FUNCTION public.generate_service_request_reference IS
    'Génère une référence unique PREFIX-YYYY-NNNNN pour un service_request. '
    'Advisory lock pour éviter race conditions. Patched 2026-04-11 (migration 291). '
    'Préfixes: RES, PAS, CFN, CON, VHC, CTR, VER, PRO, CER, PER, VIS, LIC, FLD, SRV.';

-- ============================================================
-- 2. Ajouter colonne `source` sur service_requests (rattrape 287)
-- ============================================================
-- Migration 287 avait ADD COLUMN dans un BEGIN/COMMIT qui a rollback.
-- Ici on fait ça proprement, check constraint idempotent.

ALTER TABLE service_requests
    ADD COLUMN IF NOT EXISTS source VARCHAR(30) NOT NULL DEFAULT 'citizen_wizard';

COMMENT ON COLUMN service_requests.source IS
    'Origin of this request: citizen_wizard (online), field_inspection (agent terrain), admin_import (migration), batch (bulk)';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_sr_source'
          AND conrelid = 'service_requests'::regclass
    ) THEN
        ALTER TABLE service_requests
            ADD CONSTRAINT chk_sr_source
            CHECK (source IN ('citizen_wizard', 'field_inspection', 'admin_import', 'batch'));
    END IF;
END $$;

-- ============================================================
-- 3. Ajouter colonnes pour lien 1:1 commercial_licenses (D4)
-- ============================================================

ALTER TABLE service_requests
    ADD COLUMN IF NOT EXISTS commercial_license_id UUID;

-- Add FK only if it doesn't exist (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_sr_commercial_license'
          AND conrelid = 'service_requests'::regclass
    ) THEN
        ALTER TABLE service_requests
            ADD CONSTRAINT fk_sr_commercial_license
            FOREIGN KEY (commercial_license_id)
            REFERENCES commercial_licenses(id)
            ON DELETE RESTRICT;
    END IF;
END $$;

ALTER TABLE service_requests
    ADD COLUMN IF NOT EXISTS fiscal_year INTEGER;

COMMENT ON COLUMN service_requests.commercial_license_id IS
    'FK vers commercial_licenses — NOT NULL pour dossiers bundle (FIELD_INSPECTION ou BUNDLE_PAYMENT). NULL pour autres workflows. ON DELETE RESTRICT (protection).';

COMMENT ON COLUMN service_requests.fiscal_year IS
    'Année fiscale dénormalisée depuis commercial_licenses (accélère les queries de reporting et exclusion cleanup)';

-- ============================================================
-- 4. Backfill (données existantes)
-- ============================================================
-- État prod 2026-04-11: 0 service_requests bundle, 13 commercial_licenses
-- orphelines → aucun backfill nécessaire pour créer des liens.
-- Les licences seront liées au premier field_payment (lazy create).
--
-- On traite quand même les éventuels SR bundle legacy (staging/dev).
-- Si commercial_licenses.service_request_id est déjà rempli côté licence,
-- on propage l'info côté service_requests.

UPDATE service_requests sr
SET commercial_license_id = cl.id,
    fiscal_year = cl.fiscal_year,
    bundle_id = COALESCE(sr.bundle_id, cl.bundle_id),
    source = CASE
        WHEN sr.workflow_code = 'FIELD_INSPECTION' THEN 'field_inspection'
        WHEN sr.workflow_code = 'BUNDLE_PAYMENT' THEN 'citizen_wizard'
        ELSE sr.source
    END
FROM commercial_licenses cl
WHERE cl.service_request_id = sr.id
  AND sr.commercial_license_id IS NULL;

-- ============================================================
-- 5. UNIQUE partial index : 1 SR max par licence (D3 safety net)
-- ============================================================
-- Garde-fou BD : empêche 2 service_requests pour la même licence
-- même en cas de bug applicatif. Utilisé par le recovery
-- UniqueViolationError dans CollectionService._find_or_create_bundle_dossier.

CREATE UNIQUE INDEX IF NOT EXISTS idx_sr_commercial_license_unique
    ON service_requests (commercial_license_id)
    WHERE commercial_license_id IS NOT NULL;

-- ============================================================
-- 6. Index de lookup rapide
-- ============================================================

-- Index pour filtrer par source (cleanup exclusion Phase 2)
CREATE INDEX IF NOT EXISTS idx_sr_source
    ON service_requests (source)
    WHERE source != 'citizen_wizard';

-- Index pour les queries de reporting par année fiscale
CREATE INDEX IF NOT EXISTS idx_sr_fiscal_year
    ON service_requests (fiscal_year)
    WHERE fiscal_year IS NOT NULL;

-- ============================================================
-- 7. Trigger d'intégrité : bundle SR doit avoir commercial_license_id
-- ============================================================
-- Garantit qu'un INSERT/UPDATE avec workflow_code bundle a bien
-- commercial_license_id + fiscal_year non NULL, et source cohérent.

CREATE OR REPLACE FUNCTION fn_enforce_bundle_sr_integrity()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.workflow_code IN ('BUNDLE_PAYMENT', 'FIELD_INSPECTION') THEN
        IF NEW.commercial_license_id IS NULL THEN
            RAISE EXCEPTION
                'service_request with workflow_code % must have commercial_license_id (bundle integrity)',
                NEW.workflow_code
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.fiscal_year IS NULL THEN
            RAISE EXCEPTION
                'service_request with workflow_code % must have fiscal_year (bundle integrity)',
                NEW.workflow_code
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.source NOT IN ('citizen_wizard', 'field_inspection') THEN
            RAISE EXCEPTION
                'bundle service_request source must be citizen_wizard or field_inspection, got %',
                NEW.source
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    -- Non-bundle workflows: no constraint (trigger is no-op)
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_bundle_sr_integrity ON service_requests;
CREATE TRIGGER trg_enforce_bundle_sr_integrity
    BEFORE INSERT OR UPDATE ON service_requests
    FOR EACH ROW
    EXECUTE FUNCTION fn_enforce_bundle_sr_integrity();

-- ============================================================
-- 8. Trigger de synchronisation: commercial_licenses.service_request_id
-- ============================================================
-- Quand un service_request est créé/updaté avec commercial_license_id,
-- on met à jour commercial_licenses.service_request_id (bidirectionnel).
-- Idempotent: n'écrase pas un lien existant différent.

CREATE OR REPLACE FUNCTION fn_sync_license_service_request_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.commercial_license_id IS NOT NULL THEN
        UPDATE commercial_licenses
            SET service_request_id = NEW.id,
                updated_at = NOW()
            WHERE id = NEW.commercial_license_id
              AND (service_request_id IS NULL OR service_request_id = NEW.id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_license_sr_id ON service_requests;
CREATE TRIGGER trg_sync_license_sr_id
    AFTER INSERT OR UPDATE OF commercial_license_id ON service_requests
    FOR EACH ROW
    WHEN (NEW.commercial_license_id IS NOT NULL)
    EXECUTE FUNCTION fn_sync_license_service_request_id();

-- ============================================================
-- 9. Sanity checks (non-destructifs, informatifs)
-- ============================================================

DO $$
DECLARE
    v_orphan_licenses INTEGER;
    v_broken_sr INTEGER;
    v_has_source_col BOOLEAN;
    v_has_cl_col BOOLEAN;
BEGIN
    -- Verify columns exist
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'service_requests' AND column_name = 'source'
    ) INTO v_has_source_col;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'service_requests' AND column_name = 'commercial_license_id'
    ) INTO v_has_cl_col;

    IF NOT v_has_source_col THEN
        RAISE EXCEPTION 'Migration 291: source column creation failed';
    END IF;
    IF NOT v_has_cl_col THEN
        RAISE EXCEPTION 'Migration 291: commercial_license_id column creation failed';
    END IF;

    -- Count orphan licenses (expected 13 on 2026-04-11 prod)
    SELECT COUNT(*) INTO v_orphan_licenses
    FROM commercial_licenses
    WHERE service_request_id IS NULL;

    RAISE NOTICE 'Migration 291: % orphan commercial_licenses (lazy-create on first field payment)',
        v_orphan_licenses;

    -- Count SRs that should have commercial_license_id but don't
    SELECT COUNT(*) INTO v_broken_sr
    FROM service_requests
    WHERE workflow_code IN ('BUNDLE_PAYMENT', 'FIELD_INSPECTION')
      AND commercial_license_id IS NULL;

    IF v_broken_sr > 0 THEN
        RAISE WARNING 'Migration 291: % service_requests in bundle/field workflow without commercial_license_id — manual investigation needed',
            v_broken_sr;
    END IF;

    RAISE NOTICE 'Migration 291: sanity checks passed';
END $$;

COMMIT;

-- ============================================================
-- ROLLBACK (manual execution if needed)
-- ============================================================
-- NOTE: Ne PAS rollback le CREATE OR REPLACE FUNCTION de la section 1 —
--       la version précédente est buggée (lowercase + no advisory lock).
--       Si rollback nécessaire, restaurer depuis git history migration 020.
--
-- BEGIN;
-- DROP TRIGGER IF EXISTS trg_sync_license_sr_id ON service_requests;
-- DROP FUNCTION IF EXISTS fn_sync_license_service_request_id();
-- DROP TRIGGER IF EXISTS trg_enforce_bundle_sr_integrity ON service_requests;
-- DROP FUNCTION IF EXISTS fn_enforce_bundle_sr_integrity();
-- DROP INDEX IF EXISTS idx_sr_fiscal_year;
-- DROP INDEX IF EXISTS idx_sr_source;
-- DROP INDEX IF EXISTS idx_sr_commercial_license_unique;
-- ALTER TABLE service_requests DROP CONSTRAINT IF EXISTS fk_sr_commercial_license;
-- ALTER TABLE service_requests DROP COLUMN IF EXISTS fiscal_year;
-- ALTER TABLE service_requests DROP COLUMN IF EXISTS commercial_license_id;
-- ALTER TABLE service_requests DROP CONSTRAINT IF EXISTS chk_sr_source;
-- ALTER TABLE service_requests DROP COLUMN IF EXISTS source;
-- COMMIT;
