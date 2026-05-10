-- ============================================================================
-- Migration 218: Bundle Workflow Foundations — OMS Database Layer
-- ============================================================================
-- Creates the complete database foundation for the Obligation Management System
-- (OMS) powering commercial licensing in Equatorial Guinea.
--
-- 6 PHASES:
--   1. Extend existing tables (cities, companies, service_bundles, items, payments)
--   2. Centralized configuration engine (fiscal_config_rules + recompute function)
--   3. Core business tables (commercial_licenses, license_obligations, events)
--   4. New entities + entity_locations (8 entities × 2 sites = 16 locations)
--   5. Triggers (updated_at + auto-recompute on config change)
--   6. Ministry-to-entity routing view (v_obligation_routing)
--
-- IDEMPOTENT: All DDL uses IF NOT EXISTS / IF EXISTS. Safe to re-run.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: Extend Existing Tables
-- ============================================================================

-- 1.1 cities: add zone_id (links to commerce_zones for pricing + tier classification)
-- -----------------------------------------------------------------------------------
-- zone_id is the ONLY addition needed:
--   - Pricing: cities.zone_id = service_bundle_items.zone_id → same tariff
--   - Admin level: derivable via commerce_zones.zone_tier (A/B/C/D)
ALTER TABLE cities ADD COLUMN IF NOT EXISTS zone_id UUID REFERENCES commerce_zones(id);
ALTER TABLE cities ADD COLUMN IF NOT EXISTS provincia VARCHAR(50);

COMMENT ON COLUMN cities.zone_id IS 'Commerce zone for pricing — determines tariffs for businesses in this city. Tier derivable via commerce_zones.zone_tier.';
COMMENT ON COLUMN cities.provincia IS 'Province administrative GQ (BIOKO-NORTE, LITORAL, KIE-NTEM, etc.) — from DGPE documents ubicacion.provincia';

-- Populate provincia from official GQ administrative divisions
UPDATE cities SET provincia = 'BIOKO-NORTE' WHERE name IN ('Malabo', 'Baney');
UPDATE cities SET provincia = 'LITORAL' WHERE name = 'Bata';
UPDATE cities SET provincia = 'KIE-NTEM' WHERE name = 'Ebebiyin';
UPDATE cities SET provincia = 'CENTRO-SUR' WHERE name = 'Evinayong';
UPDATE cities SET provincia = 'WELE-NZAS' WHERE name = 'Mongomo';
UPDATE cities SET provincia = 'DJIBLOHO' WHERE name = 'Oyala';

CREATE INDEX IF NOT EXISTS idx_cities_provincia ON cities(provincia) WHERE provincia IS NOT NULL;

-- Populate zone mappings from fiscal law
-- A-tier (zone_tier=A) = Capitales de Regiones
UPDATE cities SET zone_id = (SELECT id FROM commerce_zones WHERE zone_code = 'A1')
WHERE name = 'Malabo';

UPDATE cities SET zone_id = (SELECT id FROM commerce_zones WHERE zone_code = 'A2')
WHERE name = 'Bata';

UPDATE cities SET zone_id = (SELECT id FROM commerce_zones WHERE zone_code = 'A3')
WHERE name = 'Oyala';

-- B-tier (zone_tier=B) = Capitales de Provincias
UPDATE cities SET zone_id = (SELECT id FROM commerce_zones WHERE zone_code = 'B1')
WHERE name = 'Ebebiyin';

UPDATE cities SET zone_id = (SELECT id FROM commerce_zones WHERE zone_code = 'B2')
WHERE name = 'Evinayong';

UPDATE cities SET zone_id = (SELECT id FROM commerce_zones WHERE zone_code = 'B3')
WHERE name = 'Mongomo';

-- C-tier (zone_tier=C) = Capitales Distritales
UPDATE cities SET zone_id = (SELECT id FROM commerce_zones WHERE zone_code = 'C1')
WHERE name = 'Baney';

CREATE INDEX IF NOT EXISTS idx_cities_zone ON cities(zone_id) WHERE zone_id IS NOT NULL;

-- Fix is_capital for provincial capitals (were incorrectly false)
UPDATE cities SET is_capital = true, description = 'Capital de la provincia de Litoral' WHERE name = 'Bata';
UPDATE cities SET is_capital = true, description = 'Capital de la provincia de Kie-Ntem' WHERE name = 'Ebebiyin';
UPDATE cities SET is_capital = true, description = 'Capital de la provincia de Centro Sur' WHERE name = 'Evinayong';
UPDATE cities SET is_capital = true, description = 'Capital de la provincia de Wele-Nzas' WHERE name = 'Mongomo';
UPDATE cities SET is_capital = true, description = 'Capital nacional y de la provincia de Bioko Norte' WHERE name = 'Malabo';
UPDATE cities SET is_capital = true, description = 'Capital de la provincia de Djibloho, nueva capital administrativa' WHERE name = 'Oyala';
UPDATE cities SET description = 'Distrito de Bioko Norte' WHERE name = 'Baney';

-- Insert missing cities (10 cities covering the 2 missing provinces + district capitals)
INSERT INTO cities (name, region, provincia, is_capital, description, zone_id, is_active) VALUES
    ('Luba',                'Insular',     'BIOKO-SUR',   true,  'Capital de la provincia de Bioko Sur',    (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), true),
    ('San Antonio de Pale', 'Insular',     'ANNOBON',     true,  'Capital de la provincia de Annobon',       (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), true),
    ('Mbini',               'Continental', 'LITORAL',     false, 'Distrito de Litoral (ex-Rio Benito)',      (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), true),
    ('Niefang',             'Continental', 'CENTRO-SUR',  false, 'Distrito de Centro Sur',                  (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), true),
    ('Micomeseng',          'Continental', 'KIE-NTEM',    false, 'Distrito de Kie-Ntem',                    (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), true),
    ('Anisok',              'Continental', 'WELE-NZAS',   false, 'Distrito de Wele-Nzas',                   (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), true),
    ('Riaba',               'Insular',     'BIOKO-SUR',   false, 'Distrito de Bioko Sur',                   (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), true),
    ('Cogo',                'Continental', 'LITORAL',     false, 'Distrito fronterizo con Gabon',            (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), true),
    ('Akurenam',            'Continental', 'CENTRO-SUR',  false, 'Poblado de Centro Sur',                   (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), true),
    ('Nsork',               'Continental', 'KIE-NTEM',    false, 'Poblado de Kie-Ntem',                     (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), true)
ON CONFLICT DO NOTHING;


-- 1.2 entity_locations: populate city_id from cities table
-- --------------------------------------------------------
UPDATE entity_locations el SET city_id = c.id
FROM cities c WHERE LOWER(el.city) = LOWER(c.name) AND el.city_id IS NULL;


-- 1.3 companies: extend with OCR-aligned licensing fields
-- --------------------------------------------------------
-- Columns aligned 1:1 with OCR schemas:
--   certificado_actualizacion_empresarial_gq.json
--   certificado_registro_empresarial_gq.json
-- Pipeline: OCR extraction → auto-populate companies → LLM classification → regimen_fiscal
--
-- REMOVED: license_status, license_expiry_date, last_renewal_date (derivable from commercial_licenses)
-- REMOVED: primary_sector_id (FK to sectors/ministries — unrelated to sector_actividad from OCR)
ALTER TABLE companies DROP COLUMN IF EXISTS primary_sector_id;
-- REMOVED: city (text free — replaced by city_id FK to cities table)
ALTER TABLE companies DROP COLUMN IF EXISTS city;

-- Identity (from OCR empresa section)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS nif VARCHAR(20);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS forma_juridica VARCHAR(50);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS nacionalidad VARCHAR(50);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS capital_social NUMERIC(15,2);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS registration_number VARCHAR(30);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS registration_date DATE;

-- Activity classification (from OCR actividad section)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS sector_actividad VARCHAR(50);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS subsector_actividad VARCHAR(100);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS objeto_social TEXT;

-- Commerce/bundle classification (derived by LLM from OCR fields)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS commerce_type VARCHAR(50);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS regimen_fiscal VARCHAR(20) DEFAULT 'pendiente'
    CHECK (regimen_fiscal IN ('bundle', 'declarativo', 'mixto', 'exento', 'pendiente'));

-- Operational data (from OCR datos_operativos section)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS employee_count INTEGER;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS establishment_count INTEGER;

-- Geolocation (FK references)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS zone_id UUID REFERENCES commerce_zones(id);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS city_id UUID REFERENCES cities(id);

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_nif ON companies(nif) WHERE nif IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_reg_num ON companies(registration_number)
    WHERE registration_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_zone ON companies(zone_id) WHERE zone_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_commerce_type ON companies(commerce_type)
    WHERE commerce_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_regimen ON companies(regimen_fiscal)
    WHERE regimen_fiscal IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_forma_juridica ON companies(forma_juridica)
    WHERE forma_juridica IS NOT NULL;

-- Comments
COMMENT ON COLUMN companies.nif IS 'NIF fiscal GE (from OCR: empresa.nif) — unique business identifier, format XXXXXWC-XX';
COMMENT ON COLUMN companies.forma_juridica IS 'Legal form (from OCR: empresa.forma_juridica) — SOCIEDAD LIMITADA, SOCIEDAD ANONIMA, SUCURSAL, EMPRESA INDIVIDUAL, AUTONOMO';
COMMENT ON COLUMN companies.nacionalidad IS 'Company nationality (from OCR: empresa.nacionalidad_empresa)';
COMMENT ON COLUMN companies.capital_social IS 'Capital social in XAF (from OCR: empresa.capital_social)';
COMMENT ON COLUMN companies.sector_actividad IS 'Economic sector (from OCR: actividad.sector) — Primario, Secundario, Terciario';
COMMENT ON COLUMN companies.subsector_actividad IS 'Economic subsector (from OCR: actividad.subsector) — COMERCIO, SERVICIOS, etc.';
COMMENT ON COLUMN companies.objeto_social IS 'Business activity description (from OCR: actividad.objeto_social)';
COMMENT ON COLUMN companies.commerce_type IS 'Maps to service_bundles.commerce_type (abaceria, bar_restaurante, etc.) — set by LLM classifier';
COMMENT ON COLUMN companies.regimen_fiscal IS 'Classification result: bundle (AUTONOMO+COMERCIO), declarativo (SL/SA+SERVICIOS), mixto, exento, pendiente';
COMMENT ON COLUMN companies.registration_number IS 'PE-XXXX number from commercial registry (from OCR: documento.numero_expediente_vue)';
COMMENT ON COLUMN companies.employee_count IS 'Number of employees (from OCR: datos_operativos.numero_empleados)';
COMMENT ON COLUMN companies.establishment_count IS 'Number of establishments (from OCR: datos_operativos.numero_establecimientos)';


-- 1.4 service_bundles: processing mode + deadline
-- ------------------------------------------------
ALTER TABLE service_bundles ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(20)
    NOT NULL DEFAULT 'per_line'
    CHECK (processing_mode IN ('per_line', 'consolidated'));

ALTER TABLE service_bundles ADD COLUMN IF NOT EXISTS deadline_month INTEGER
    NOT NULL DEFAULT 4 CHECK (deadline_month BETWEEN 1 AND 12);
ALTER TABLE service_bundles ADD COLUMN IF NOT EXISTS deadline_day INTEGER
    NOT NULL DEFAULT 30 CHECK (deadline_day BETWEEN 1 AND 31);

COMMENT ON COLUMN service_bundles.processing_mode IS 'per_line=Mode A (ministry routing), consolidated=Mode B (polyvalent agent)';
COMMENT ON COLUMN service_bundles.deadline_month IS 'Default payment deadline month for all items in this bundle';
COMMENT ON COLUMN service_bundles.deadline_day IS 'Default payment deadline day for all items in this bundle';


-- 1.5 service_bundle_items: materialized config + document requirements
-- ---------------------------------------------------------------------
ALTER TABLE service_bundle_items ADD COLUMN IF NOT EXISTS effective_penalty JSONB;
ALTER TABLE service_bundle_items ADD COLUMN IF NOT EXISTS effective_deadline JSONB;
ALTER TABLE service_bundle_items ADD COLUMN IF NOT EXISTS config_resolved_at TIMESTAMPTZ;

ALTER TABLE service_bundle_items ADD COLUMN IF NOT EXISTS requires_document BOOLEAN
    NOT NULL DEFAULT false;
ALTER TABLE service_bundle_items ADD COLUMN IF NOT EXISTS document_template_id INTEGER
    REFERENCES document_templates(id) ON DELETE SET NULL;

COMMENT ON COLUMN service_bundle_items.effective_penalty IS 'Pre-computed from fiscal_config_rules. NULL = no penalty. DO NOT edit directly.';
COMMENT ON COLUMN service_bundle_items.effective_deadline IS 'Pre-computed from fiscal_config_rules. NULL = inherits bundle deadline.';
COMMENT ON COLUMN service_bundle_items.requires_document IS 'If true, citizen must upload a document to pay this item';


-- 1.6 service_payments: add fee_type for payment routing
-- -------------------------------------------------------
ALTER TABLE service_payments ADD COLUMN IF NOT EXISTS fee_type VARCHAR(20)
    CHECK (fee_type IN ('tesoro', 'municipal', 'chamber'));

CREATE INDEX IF NOT EXISTS idx_sp_fee_type ON service_payments(fee_type)
    WHERE fee_type IS NOT NULL;

COMMENT ON COLUMN service_payments.fee_type IS 'For license payments: routes to TESORO/AYUNTAMIENTO/CAMARA validator';


-- ============================================================================
-- PHASE 2: Centralized Configuration Engine
-- ============================================================================

-- 2.1 fiscal_config_rules: specificity-based config resolution
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fiscal_config_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- WHAT: type of configuration
    config_type VARCHAR(30) NOT NULL
        CHECK (config_type IN ('penalty', 'deadline', 'installment', 'processing_mode')),

    -- WHERE: scope (NULL = wildcard = applies to all at this level)
    bundle_id UUID REFERENCES service_bundles(id) ON DELETE CASCADE,
    fee_type VARCHAR(20) CHECK (fee_type IS NULL OR fee_type IN ('tesoro', 'municipal', 'chamber')),
    ministry_id INTEGER REFERENCES ministries(id) ON DELETE CASCADE,
    item_id UUID REFERENCES service_bundle_items(id) ON DELETE CASCADE,

    -- WHEN: temporal validity
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,  -- NULL = no expiration

    -- THE RULE
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- SPECIFICITY: auto-computed (higher = more specific = wins in resolution)
    -- item(50) > ministry(30) > fee_type(20) > bundle(10) > global(0)
    specificity INTEGER GENERATED ALWAYS AS (
        (CASE WHEN bundle_id IS NOT NULL THEN 1 ELSE 0 END) * 10 +
        (CASE WHEN fee_type IS NOT NULL THEN 1 ELSE 0 END) * 20 +
        (CASE WHEN ministry_id IS NOT NULL THEN 1 ELSE 0 END) * 30 +
        (CASE WHEN item_id IS NOT NULL THEN 1 ELSE 0 END) * 50
    ) STORED,

    -- METADATA
    name_es VARCHAR(200),
    description TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Prevent duplicate scope combinations
CREATE UNIQUE INDEX IF NOT EXISTS idx_fcr_unique_scope ON fiscal_config_rules(
    config_type,
    COALESCE(bundle_id::text, '__ALL__'),
    COALESCE(fee_type, '__ALL__'),
    COALESCE(ministry_id::text, '__ALL__'),
    COALESCE(item_id::text, '__ALL__')
);

-- Resolution query index (most-specific-first)
CREATE INDEX IF NOT EXISTS idx_fcr_resolution ON fiscal_config_rules(
    config_type, specificity DESC, effective_from, effective_to
) WHERE is_enabled = true;

-- Bundle-scoped queries (admin UI)
CREATE INDEX IF NOT EXISTS idx_fcr_bundle ON fiscal_config_rules(bundle_id, config_type)
    WHERE bundle_id IS NOT NULL;

COMMENT ON TABLE fiscal_config_rules IS 'Centralized config engine: penalties, deadlines, installments. Specificity-based resolution with materialization to service_bundle_items.';
COMMENT ON COLUMN fiscal_config_rules.specificity IS 'Auto-computed: item(50) > ministry(30) > fee_type(20) > bundle(10) > global(0). Highest wins.';
COMMENT ON COLUMN fiscal_config_rules.config IS 'Penalty: {"rate":0,"grace_days":0,"max_rate":0,"type":"percentage"}. Deadline: {"month":4,"day":30}';


-- 2.2 Seed global defaults (penalties=0 by design)
-- -------------------------------------------------

-- Global penalty default: DISABLED (rate=0). Admin must configure explicitly.
INSERT INTO fiscal_config_rules (config_type, is_enabled, config, name_es, description)
VALUES (
    'penalty', true,
    '{"rate": 0, "grace_days": 0, "max_rate": 0, "type": "percentage"}'::jsonb,
    'Penalidad global por defecto',
    'Penalidades desactivadas por defecto (rate=0). El administrador debe configurar explícitamente.'
) ON CONFLICT DO NOTHING;

-- Global deadline default: Q1 (April 30)
INSERT INTO fiscal_config_rules (config_type, is_enabled, config, name_es, description)
VALUES (
    'deadline', true,
    '{"month": 4, "day": 30, "type": "fixed_date", "grace_days": 0}'::jsonb,
    'Fecha límite global Q1',
    'Todos los bundles deben pagarse antes del 30 de abril del ejercicio fiscal.'
) ON CONFLICT DO NOTHING;

-- Global installment default
INSERT INTO fiscal_config_rules (config_type, is_enabled, config, name_es, description)
VALUES (
    'installment', true,
    '{"max_installments": 1, "frequency": "monthly", "min_amount": 10000}'::jsonb,
    'Configuración cuotas por defecto',
    'Sin fraccionamiento por defecto. Administrador puede habilitar por bundle.'
) ON CONFLICT DO NOTHING;


-- 2.3 Recompute function: resolves rules by specificity, materializes on items
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION recompute_effective_configs(p_bundle_id UUID DEFAULT NULL)
RETURNS INTEGER AS $$
DECLARE
    v_affected INTEGER := 0;
BEGIN
    UPDATE service_bundle_items sbi SET
        effective_penalty = (
            SELECT fcr.config FROM fiscal_config_rules fcr
            WHERE fcr.config_type = 'penalty'
              AND fcr.is_enabled = true
              AND (fcr.bundle_id = sbi.bundle_id OR fcr.bundle_id IS NULL)
              AND (fcr.fee_type = sbi.fee_type OR fcr.fee_type IS NULL)
              AND (fcr.ministry_id = sbi.ministry_id OR fcr.ministry_id IS NULL)
              AND (fcr.item_id = sbi.id OR fcr.item_id IS NULL)
              AND fcr.effective_from <= CURRENT_DATE
              AND (fcr.effective_to IS NULL OR fcr.effective_to >= CURRENT_DATE)
            ORDER BY fcr.specificity DESC
            LIMIT 1
        ),
        effective_deadline = (
            SELECT fcr.config FROM fiscal_config_rules fcr
            WHERE fcr.config_type = 'deadline'
              AND fcr.is_enabled = true
              AND (fcr.bundle_id = sbi.bundle_id OR fcr.bundle_id IS NULL)
              AND (fcr.fee_type = sbi.fee_type OR fcr.fee_type IS NULL)
              AND (fcr.ministry_id = sbi.ministry_id OR fcr.ministry_id IS NULL)
              AND (fcr.item_id = sbi.id OR fcr.item_id IS NULL)
              AND fcr.effective_from <= CURRENT_DATE
              AND (fcr.effective_to IS NULL OR fcr.effective_to >= CURRENT_DATE)
            ORDER BY fcr.specificity DESC
            LIMIT 1
        ),
        config_resolved_at = NOW()
    WHERE (p_bundle_id IS NULL OR sbi.bundle_id = p_bundle_id)
      AND sbi.is_active = true;

    GET DIAGNOSTICS v_affected = ROW_COUNT;
    RETURN v_affected;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION recompute_effective_configs IS 'Resolves fiscal_config_rules by specificity and materializes results on service_bundle_items. Call after any config change.';

-- Run initial recompute (populates effective_penalty/effective_deadline for all active items)
SELECT recompute_effective_configs();


-- ============================================================================
-- PHASE 3: Core Business Tables
-- ============================================================================

-- 3.1 commercial_licenses: annual dossier (1 per company × bundle × fiscal year)
-- -------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commercial_licenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Business identity
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    service_request_id UUID REFERENCES service_requests(id) ON DELETE SET NULL,

    -- Bundle + zone + year
    bundle_id UUID NOT NULL REFERENCES service_bundles(id) ON DELETE RESTRICT,
    zone_id UUID NOT NULL REFERENCES commerce_zones(id) ON DELETE RESTRICT,
    city_id UUID REFERENCES cities(id) ON DELETE SET NULL,
    fiscal_year INTEGER NOT NULL,
    processing_mode VARCHAR(20) NOT NULL DEFAULT 'per_line'
        CHECK (processing_mode IN ('per_line', 'consolidated')),

    -- Financial summary
    total_amount NUMERIC(12,2) NOT NULL,
    amount_paid NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
    penalty_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (penalty_amount >= 0),

    -- Obligation tracking
    obligations_total INTEGER NOT NULL DEFAULT 0,
    obligations_paid INTEGER NOT NULL DEFAULT 0,
    obligations_overdue INTEGER NOT NULL DEFAULT 0,
    compliance_score NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN obligations_total > 0
            THEN ROUND((obligations_paid::numeric / obligations_total) * 100, 2)
            ELSE 0
        END
    ) STORED,

    -- Lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'partial', 'complete', 'overdue', 'suspended', 'closed')),
    deadline DATE,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,

    -- Audit
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One dossier per company per bundle per fiscal year
    UNIQUE (company_id, bundle_id, fiscal_year)
);

CREATE INDEX IF NOT EXISTS idx_cl_company ON commercial_licenses(company_id);
CREATE INDEX IF NOT EXISTS idx_cl_fiscal_year ON commercial_licenses(fiscal_year, status);
CREATE INDEX IF NOT EXISTS idx_cl_status ON commercial_licenses(status)
    WHERE status IN ('open', 'partial', 'overdue');
CREATE INDEX IF NOT EXISTS idx_cl_deadline ON commercial_licenses(deadline)
    WHERE status IN ('open', 'partial');
CREATE INDEX IF NOT EXISTS idx_cl_service_request ON commercial_licenses(service_request_id)
    WHERE service_request_id IS NOT NULL;

COMMENT ON TABLE commercial_licenses IS 'Annual commercial license dossier. 1 per company × bundle × fiscal year. Stays OPEN until all obligations paid or fiscal year closes.';
COMMENT ON COLUMN commercial_licenses.compliance_score IS 'Auto-computed: (paid/total)*100. Used for dashboard ranking and alerts.';


-- 3.2 license_obligations: 1 per bundle item per license
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS license_obligations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parent dossier
    license_id UUID NOT NULL REFERENCES commercial_licenses(id) ON DELETE CASCADE,

    -- What: which bundle item this obligation corresponds to
    bundle_item_id UUID NOT NULL REFERENCES service_bundle_items(id) ON DELETE RESTRICT,
    fiscal_service_id INTEGER NOT NULL REFERENCES fiscal_services(id) ON DELETE RESTRICT,
    ministry_id INTEGER REFERENCES ministries(id) ON DELETE SET NULL,
    fee_type VARCHAR(20) NOT NULL
        CHECK (fee_type IN ('tesoro', 'municipal', 'chamber')),

    -- Financial
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    penalty_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (penalty_amount >= 0),
    due_date DATE,

    -- Config snapshot (from effective_* at creation time — immutable after creation)
    penalty_config JSONB,
    deadline_config JSONB,

    -- Lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending',          -- not yet paid
            'selected',         -- user selected for payment (in cart)
            'payment_pending',  -- payment created, awaiting validation
            'paid',             -- payment validated by TESORO/AYUNT/CAMARA
            'processing',       -- routed to ministry agent (post-TESORO, Mode A)
            'completed',        -- agent processed + document issued
            'overdue',          -- deadline passed, not paid
            'waived',           -- admin waived this obligation
            'cancelled'         -- licence cancelled
        )),

    -- Payment link
    payment_id UUID REFERENCES service_payments(id) ON DELETE SET NULL,
    paid_at TIMESTAMPTZ,

    -- Documents
    user_document_id UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,
    issued_document_id UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,

    -- Historical compliance (auto-checked on routing)
    previous_year_paid BOOLEAN,
    previous_year_checked_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One obligation per item per license
    UNIQUE (license_id, bundle_item_id)
);

-- Agent dashboard: obligations routed for processing
CREATE INDEX IF NOT EXISTS idx_lo_processing ON license_obligations(fee_type, ministry_id, status)
    WHERE status IN ('paid', 'processing');

-- Overdue check cron
CREATE INDEX IF NOT EXISTS idx_lo_overdue ON license_obligations(due_date, status)
    WHERE status = 'pending' AND due_date IS NOT NULL;

-- Payment lookup
CREATE INDEX IF NOT EXISTS idx_lo_payment ON license_obligations(payment_id)
    WHERE payment_id IS NOT NULL;

-- License grouping
CREATE INDEX IF NOT EXISTS idx_lo_license ON license_obligations(license_id);

-- Fee type aggregation
CREATE INDEX IF NOT EXISTS idx_lo_fee_type ON license_obligations(license_id, fee_type);

COMMENT ON TABLE license_obligations IS 'Individual fiscal obligation within a commercial license. 1 per bundle_item per license. Tracks payment, agent processing, document issuance.';
COMMENT ON COLUMN license_obligations.penalty_config IS 'Snapshot of effective_penalty at obligation creation. Immutable — config changes dont retroactively affect existing obligations.';
COMMENT ON COLUMN license_obligations.issued_document_id IS 'Official document uploaded by ministry agent after processing (e.g., CMF certificate, Ficha comercial)';


-- 3.3 license_compliance_events: append-only audit trail
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS license_compliance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- References
    license_id UUID NOT NULL REFERENCES commercial_licenses(id) ON DELETE CASCADE,
    obligation_id UUID REFERENCES license_obligations(id) ON DELETE SET NULL,

    -- Event
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN (
        'license_created',
        'obligation_created',
        'payment_initiated',
        'payment_validated',
        'obligation_routed',
        'agent_approved',
        'agent_rejected',
        'document_issued',
        'obligation_completed',
        'overdue_flagged',
        'penalty_applied',
        'reminder_sent',
        'license_completed',
        'license_renewed',
        'license_suspended',
        'config_changed',
        'waived'
    )),
    event_data JSONB DEFAULT '{}'::jsonb,

    -- Who
    triggered_by UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL = system
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lce_license ON license_compliance_events(license_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lce_obligation ON license_compliance_events(obligation_id, created_at DESC)
    WHERE obligation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_lce_type ON license_compliance_events(event_type, created_at DESC);

COMMENT ON TABLE license_compliance_events IS 'Append-only audit trail for commercial license lifecycle. Every state change is recorded.';


-- ============================================================================
-- PHASE 4: Entities and Locations
-- ============================================================================

-- 4.1 New entities (8 total: 2 payment validators + 6 ministry entities)
-- -----------------------------------------------------------------------

-- Payment validators
INSERT INTO entities (code, name, entity_type, workflow_codes)
VALUES
    ('AYUNTAMIENTO', 'Ayuntamiento', 'entity', '[]'::jsonb),
    ('CAMARA_COMERCIO', 'Cámara de Comercio', 'entity', '[]'::jsonb)
ON CONFLICT (code) DO NOTHING;

-- Ministry entities for Mode A post-TESORO processing
-- MIN_COMERCIO carries the LICENCIA_COMERCIAL workflow
INSERT INTO entities (code, name, entity_type, ministry_id, workflow_codes)
VALUES
    ('MIN_HACIENDA', 'Ministerio de Hacienda', 'entity', 91, '[]'::jsonb),
    ('MIN_COMERCIO', 'Ministerio de Comercio', 'entity', 87, '["LICENCIA_COMERCIAL"]'::jsonb),
    ('MIN_INFORMACION', 'Ministerio de Información', 'entity', 92, '[]'::jsonb),
    ('MIN_TURISMO', 'Ministerio de Turismo', 'entity', 103, '[]'::jsonb),
    ('MIN_AGRICULTURA', 'Ministerio de Agricultura', 'entity', 104, '[]'::jsonb),
    ('MIN_ELECTRICIDAD', 'Ministerio de Electricidad', 'entity', 105, '[]'::jsonb)
ON CONFLICT (code) DO NOTHING;


-- 4.2 Entity locations (2 per entity = 16 locations: Malabo + Bata)
-- ------------------------------------------------------------------
DO $$
DECLARE
    v_malabo_id UUID := (SELECT id FROM cities WHERE name = 'Malabo');
    v_bata_id UUID := (SELECT id FROM cities WHERE name = 'Bata');
    v_entity_codes TEXT[] := ARRAY[
        'AYUNTAMIENTO', 'CAMARA_COMERCIO',
        'MIN_HACIENDA', 'MIN_COMERCIO', 'MIN_INFORMACION',
        'MIN_TURISMO', 'MIN_AGRICULTURA', 'MIN_ELECTRICIDAD'
    ];
    v_code TEXT;
    v_entity_id UUID;
BEGIN
    FOREACH v_code IN ARRAY v_entity_codes LOOP
        SELECT id INTO v_entity_id FROM entities WHERE code = v_code;
        IF v_entity_id IS NULL THEN
            RAISE NOTICE 'Entity % not found, skipping', v_code;
            CONTINUE;
        END IF;

        -- Malabo (Insular)
        INSERT INTO entity_locations (
            entity_code, entity_id, city, city_id, region,
            location_name, is_main_office, is_active
        ) VALUES (
            v_code, v_entity_id, 'Malabo', v_malabo_id, 'Insular',
            v_code || ' Malabo', true, true
        ) ON CONFLICT (entity_code, location_name) DO NOTHING;

        -- Bata (Continental)
        INSERT INTO entity_locations (
            entity_code, entity_id, city, city_id, region,
            location_name, is_main_office, is_active
        ) VALUES (
            v_code, v_entity_id, 'Bata', v_bata_id, 'Continental',
            v_code || ' Bata', false, true
        ) ON CONFLICT (entity_code, location_name) DO NOTHING;
    END LOOP;
END $$;


-- ============================================================================
-- PHASE 5: Triggers and Functions
-- ============================================================================

-- 5.1 updated_at triggers for new tables
-- ----------------------------------------
DO $$
DECLARE
    v_tables TEXT[] := ARRAY[
        'commercial_licenses',
        'license_obligations',
        'fiscal_config_rules'
    ];
    v_table TEXT;
BEGIN
    FOREACH v_table IN ARRAY v_tables LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_updated_at_' || v_table) THEN
            EXECUTE format(
                'CREATE TRIGGER set_updated_at_%s BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()',
                v_table, v_table
            );
        END IF;
    END LOOP;
END $$;


-- 5.2 Auto-recompute trigger on fiscal_config_rules changes
-- -----------------------------------------------------------
-- Optimized: FOR EACH STATEMENT (not FOR EACH ROW)
-- Batch-safe: if admin modifies 50 rules in 1 statement, recompute fires ONCE.
-- Full recompute (NULL) is safe: ~1062 items = <500ms.
CREATE OR REPLACE FUNCTION fn_auto_recompute_on_config_change()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM recompute_effective_configs(NULL);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auto_recompute_config ON fiscal_config_rules;
CREATE TRIGGER trg_auto_recompute_config
    AFTER INSERT OR UPDATE OR DELETE ON fiscal_config_rules
    FOR EACH STATEMENT EXECUTE FUNCTION fn_auto_recompute_on_config_change();

COMMENT ON TRIGGER trg_auto_recompute_config ON fiscal_config_rules IS
    'Auto-materializes config changes to service_bundle_items. FOR EACH STATEMENT = batch-safe (1 recompute per batch).';


-- ============================================================================
-- PHASE 6: Ministry-to-Entity Routing View
-- ============================================================================

CREATE OR REPLACE VIEW v_obligation_routing AS
SELECT
    e.id AS entity_id,
    e.code AS entity_code,
    e.ministry_id,
    el.id AS entity_location_id,
    el.city,
    el.region,
    CASE
        WHEN e.code = 'AYUNTAMIENTO' THEN 'municipal'
        WHEN e.code = 'CAMARA_COMERCIO' THEN 'chamber'
        ELSE 'tesoro'
    END AS fee_type
FROM entities e
JOIN entity_locations el ON el.entity_id = e.id AND el.is_active = true
WHERE e.code IN (
    'AYUNTAMIENTO', 'CAMARA_COMERCIO',
    'MIN_HACIENDA', 'MIN_COMERCIO', 'MIN_INFORMACION',
    'MIN_TURISMO', 'MIN_AGRICULTURA', 'MIN_ELECTRICIDAD',
    'TESORO'
);

COMMENT ON VIEW v_obligation_routing IS 'Resolves (fee_type, ministry_id, region) → (entity_id, entity_location_id) for obligation routing';


COMMIT;


-- ============================================================================
-- ROLLBACK (run manually if needed — DO NOT include in migration runner)
-- ============================================================================
-- DROP VIEW IF EXISTS v_obligation_routing;
-- DROP TRIGGER IF EXISTS trg_auto_recompute_config ON fiscal_config_rules;
-- DROP FUNCTION IF EXISTS fn_auto_recompute_on_config_change();
-- DROP FUNCTION IF EXISTS recompute_effective_configs(UUID);
-- DROP TABLE IF EXISTS license_compliance_events;
-- DROP TABLE IF EXISTS license_obligations;
-- DROP TABLE IF EXISTS commercial_licenses;
-- DROP TABLE IF EXISTS fiscal_config_rules;
-- DELETE FROM entity_locations WHERE entity_code IN ('AYUNTAMIENTO','CAMARA_COMERCIO','MIN_HACIENDA','MIN_COMERCIO','MIN_INFORMACION','MIN_TURISMO','MIN_AGRICULTURA','MIN_ELECTRICIDAD');
-- DELETE FROM entities WHERE code IN ('AYUNTAMIENTO','CAMARA_COMERCIO','MIN_HACIENDA','MIN_COMERCIO','MIN_INFORMACION','MIN_TURISMO','MIN_AGRICULTURA','MIN_ELECTRICIDAD');
-- ALTER TABLE service_payments DROP COLUMN IF EXISTS fee_type;
-- ALTER TABLE service_bundle_items DROP COLUMN IF EXISTS effective_penalty;
-- ALTER TABLE service_bundle_items DROP COLUMN IF EXISTS effective_deadline;
-- ALTER TABLE service_bundle_items DROP COLUMN IF EXISTS config_resolved_at;
-- ALTER TABLE service_bundle_items DROP COLUMN IF EXISTS requires_document;
-- ALTER TABLE service_bundle_items DROP COLUMN IF EXISTS document_template_id;
-- ALTER TABLE service_bundles DROP COLUMN IF EXISTS processing_mode;
-- ALTER TABLE service_bundles DROP COLUMN IF EXISTS deadline_month;
-- ALTER TABLE service_bundles DROP COLUMN IF EXISTS deadline_day;
-- ALTER TABLE companies DROP COLUMN IF EXISTS nif;
-- ALTER TABLE companies DROP COLUMN IF EXISTS commerce_type;
-- ALTER TABLE companies DROP COLUMN IF EXISTS forma_juridica;
-- ALTER TABLE companies DROP COLUMN IF EXISTS zone_id;
-- ALTER TABLE companies DROP COLUMN IF EXISTS city_id;
-- ALTER TABLE companies DROP COLUMN IF EXISTS registration_number;
-- ALTER TABLE companies DROP COLUMN IF EXISTS registration_date;
-- ALTER TABLE companies DROP COLUMN IF EXISTS license_status;
-- ALTER TABLE companies DROP COLUMN IF EXISTS license_expiry_date;
-- ALTER TABLE companies DROP COLUMN IF EXISTS last_renewal_date;
-- ALTER TABLE companies DROP COLUMN IF EXISTS employee_count;
-- ALTER TABLE cities DROP COLUMN IF EXISTS zone_id;
