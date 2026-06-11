-- Migration 203: Service Bundles & Zones + Payment Plans Rehab
-- Part of Phase 3: Fiscal Services Audit — Bundles/Zone-Based Pricing
-- Plan: .claude/plans/unified-swimming-matsumoto.md
--
-- Creates:
--   1. commerce_zones (12 zones géographiques A1→D3)
--   2. service_bundles (~15 types de commerce)
--   3. service_bundle_items (~1200 items prix matrice)
-- Alters:
--   4. service_requests: +bundle_id, +zone_id (nullable)
--   5. payment_plans: +service_payment_id, DROP FK tax_declarations

BEGIN;

-- ============================================================
-- 1. commerce_zones — 12 zones géographiques (Precios.pdf)
-- ============================================================
CREATE TABLE IF NOT EXISTS commerce_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_code VARCHAR(5) NOT NULL UNIQUE,
    zone_tier CHAR(1) NOT NULL,  -- A, B, C, D
    zone_rank INT NOT NULL,      -- 1, 2, 3
    name_es VARCHAR(200) NOT NULL,
    description_es TEXT,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_commerce_zones_tier ON commerce_zones(zone_tier);
COMMENT ON TABLE commerce_zones IS 'Zones géographiques GE pour tarification commerciale (Precios.pdf décret présidentiel)';

-- ============================================================
-- 2. service_bundles — Types de commerce (bar, restaurant, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS service_bundles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bundle_code VARCHAR(50) NOT NULL UNIQUE,
    commerce_type VARCHAR(100) NOT NULL,
    name_es VARCHAR(300) NOT NULL,
    description_es TEXT,
    legal_reference TEXT,  -- Référence au décret/article
    is_active BOOLEAN NOT NULL DEFAULT true,
    -- Installment configuration
    installment_eligible BOOLEAN NOT NULL DEFAULT false,
    max_installments INT NOT NULL DEFAULT 1 CHECK (max_installments >= 1 AND max_installments <= 12),
    installment_frequency VARCHAR(20) NOT NULL DEFAULT 'monthly'
        CHECK (installment_frequency IN ('monthly', 'bi-monthly', 'quarterly')),
    -- Audit
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_service_bundles_active ON service_bundles(is_active) WHERE is_active = true;
CREATE INDEX idx_service_bundles_commerce ON service_bundles(commerce_type);
COMMENT ON TABLE service_bundles IS 'Bundles de services fiscaux par type de commerce (licences commerciales GE)';

-- ============================================================
-- 3. service_bundle_items — Matrice prix (bundle × zone × service)
-- ============================================================
CREATE TABLE IF NOT EXISTS service_bundle_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bundle_id UUID NOT NULL REFERENCES service_bundles(id) ON DELETE CASCADE,
    fiscal_service_id INT NOT NULL REFERENCES fiscal_services(id) ON DELETE RESTRICT,
    zone_id UUID NOT NULL REFERENCES commerce_zones(id) ON DELETE RESTRICT,
    ministry_id INT REFERENCES ministries(id) ON DELETE SET NULL,  -- Dénormalisé pour perf
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    is_fixed_across_zones BOOLEAN NOT NULL DEFAULT false,
    display_order INT NOT NULL DEFAULT 0,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Un seul prix par (bundle, service, zone)
    UNIQUE (bundle_id, fiscal_service_id, zone_id)
);

CREATE INDEX idx_bundle_items_bundle_zone ON service_bundle_items(bundle_id, zone_id);
CREATE INDEX idx_bundle_items_service ON service_bundle_items(fiscal_service_id);
CREATE INDEX idx_bundle_items_active ON service_bundle_items(bundle_id) WHERE is_active = true;
COMMENT ON TABLE service_bundle_items IS 'Matrice de prix: montant par (bundle, service fiscal, zone géographique)';

-- ============================================================
-- 4. ALTER service_requests — Ajouter lien bundle + zone
-- ============================================================
ALTER TABLE service_requests
    ADD COLUMN IF NOT EXISTS bundle_id UUID REFERENCES service_bundles(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS zone_id UUID REFERENCES commerce_zones(id) ON DELETE SET NULL;

CREATE INDEX idx_service_requests_bundle ON service_requests(bundle_id)
    WHERE bundle_id IS NOT NULL;

COMMENT ON COLUMN service_requests.bundle_id IS 'Bundle de services commerciaux (NULL pour les demandes non-bundle)';
COMMENT ON COLUMN service_requests.zone_id IS 'Zone géographique sélectionnée pour tarification bundle';

-- ============================================================
-- 5. ALTER payment_plans — Migrer vers service_payments
-- ============================================================

-- 5a. Ajouter service_payment_id
ALTER TABLE payment_plans
    ADD COLUMN IF NOT EXISTS service_payment_id UUID REFERENCES service_payments(id) ON DELETE CASCADE;

-- 5b. Rendre tax_declaration_id nullable (était NOT NULL, 0 lignes = safe)
ALTER TABLE payment_plans
    ALTER COLUMN tax_declaration_id DROP NOT NULL;

-- 5c. Drop FK et UNIQUE vers tax_declarations (deprecated)
ALTER TABLE payment_plans
    DROP CONSTRAINT IF EXISTS payment_plans_tax_declaration_id_fkey;
ALTER TABLE payment_plans
    DROP CONSTRAINT IF EXISTS payment_plans_tax_declaration_id_key;

-- 5d. Ajouter index sur service_payment_id
CREATE INDEX idx_payment_plans_service_payment ON payment_plans(service_payment_id)
    WHERE service_payment_id IS NOT NULL;

-- 5e. Ajouter constraint: nouveaux plans DOIVENT avoir service_payment_id
-- Note: On ne peut pas mettre NOT NULL car la colonne existe déjà (même avec 0 lignes, ALTER safe)
-- On utilise un CHECK qui accepte les anciennes lignes (tax_declaration_id set) ET les nouvelles (service_payment_id set)
ALTER TABLE payment_plans
    ADD CONSTRAINT chk_payment_plan_source
    CHECK (service_payment_id IS NOT NULL OR tax_declaration_id IS NOT NULL);

COMMENT ON COLUMN payment_plans.service_payment_id IS 'Lien vers service_payments (architecture unifiée)';
COMMENT ON COLUMN payment_plans.tax_declaration_id IS 'DEPRECATED — Sera supprimé en Phase 5. Utiliser service_payment_id.';

-- ============================================================
-- Updated_at trigger for new tables
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_updated_at_commerce_zones') THEN
        CREATE TRIGGER set_updated_at_commerce_zones
            BEFORE UPDATE ON commerce_zones
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_updated_at_service_bundles') THEN
        CREATE TRIGGER set_updated_at_service_bundles
            BEFORE UPDATE ON service_bundles
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_updated_at_service_bundle_items') THEN
        CREATE TRIGGER set_updated_at_service_bundle_items
            BEFORE UPDATE ON service_bundle_items
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END$$;

COMMIT;
