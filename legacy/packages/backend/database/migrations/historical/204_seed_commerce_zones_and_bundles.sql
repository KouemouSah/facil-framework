-- Migration 204: Seed Commerce Zones & Bundles
-- Données initiales pour Phase 3 — Bundles/Zone-Based Pricing
-- Zones basées sur le décret présidentiel (Precios.pdf)
-- Bundles représentatifs avec vrais service_codes de la BD

BEGIN;

-- ============================================================
-- 1. Commerce Zones (12 zones GE)
-- ============================================================
-- Tier A: Capitales (Malabo, Bata)
-- Tier B: Villes principales
-- Tier C: Villes secondaires
-- Tier D: Zones rurales

INSERT INTO commerce_zones (zone_code, zone_tier, zone_rank, name_es, description_es, display_order)
VALUES
    ('A1', 'A', 1, 'Malabo Centro',       'Capital — zona centro comercial principal',      1),
    ('A2', 'A', 2, 'Bata Centro',         'Capital continental — zona centro comercial',     2),
    ('A3', 'A', 3, 'Malabo/Bata Periferia', 'Zonas periféricas de las capitales',            3),
    ('B1', 'B', 1, 'Ebebiyín',            'Ciudad principal fronteriza con Camerún y Gabón', 4),
    ('B2', 'B', 2, 'Mongomo',             'Ciudad principal región oriental',                5),
    ('B3', 'B', 3, 'Evinayong',           'Ciudad principal región centro-sur',              6),
    ('C1', 'C', 1, 'Luba / Riaba',        'Ciudades secundarias isla de Bioko',              7),
    ('C2', 'C', 2, 'Niefang / Añisok',    'Ciudades secundarias continentales',              8),
    ('C3', 'C', 3, 'Acurenam / Nsork',    'Ciudades secundarias interiores',                 9),
    ('D1', 'D', 1, 'Corisco / Annobón',   'Islas menores',                                  10),
    ('D2', 'D', 2, 'Zona Rural Bioko',    'Zonas rurales isla de Bioko',                    11),
    ('D3', 'D', 3, 'Zona Rural Continental', 'Zonas rurales región continental',              12)
ON CONFLICT (zone_code) DO NOTHING;

-- ============================================================
-- 2. Service Bundles (types de commerce)
-- ============================================================
-- installment_eligible = true pour bundles > 500,000 XAF (zone A1)
-- max_installments = 4 pour les gros montants, 2 pour les moyens

INSERT INTO service_bundles (bundle_code, commerce_type, name_es, description_es, legal_reference,
                             installment_eligible, max_installments, installment_frequency)
VALUES
    ('BARES', 'bar',
     'Licencia de Apertura de Bar',
     'Bundle de servicios fiscales requeridos para la apertura y operación de un bar',
     'Decreto Presidencial — Precios de Servicios Públicos, Capítulo Comercio',
     true, 4, 'monthly'),

    ('RESTAURANTES', 'restaurante',
     'Licencia de Apertura de Restaurante',
     'Bundle de servicios para apertura y operación de restaurante',
     'Decreto Presidencial — Precios de Servicios Públicos',
     true, 4, 'monthly'),

    ('CAFETERIAS', 'cafeteria',
     'Licencia de Apertura de Cafetería',
     'Bundle de servicios para apertura y operación de cafetería',
     'Decreto Presidencial — Precios de Servicios Públicos',
     false, 1, 'monthly'),

    ('FARMACIAS', 'farmacia',
     'Licencia de Apertura de Farmacia',
     'Bundle de servicios para apertura y operación de farmacia',
     'Decreto Presidencial — Precios de Servicios Públicos',
     true, 4, 'monthly'),

    ('FERRETERIAS', 'ferreteria',
     'Licencia de Apertura de Ferretería',
     'Bundle de servicios para apertura y operación de ferretería',
     'Decreto Presidencial — Precios de Servicios Públicos',
     false, 2, 'monthly'),

    ('DISCOTECAS', 'discoteca',
     'Licencia de Apertura de Discoteca',
     'Bundle de servicios para apertura y operación de discoteca o sala de fiestas',
     'Decreto Presidencial — Precios de Servicios Públicos',
     true, 4, 'monthly'),

    ('PELUQUERIAS', 'peluqueria',
     'Licencia de Apertura de Peluquería',
     'Bundle de servicios para apertura y operación de peluquería',
     'Decreto Presidencial — Precios de Servicios Públicos',
     false, 1, 'monthly'),

    ('TALLERES', 'taller',
     'Licencia de Apertura de Taller',
     'Bundle de servicios para apertura y operación de taller mecánico o artesanal',
     'Decreto Presidencial — Precios de Servicios Públicos',
     false, 2, 'monthly'),

    ('HOTELES', 'hotel',
     'Licencia de Apertura de Hotel',
     'Bundle de servicios para apertura y operación de hotel o alojamiento turístico',
     'Decreto Presidencial — Precios de Servicios Públicos',
     true, 4, 'quarterly'),

    ('CLINICAS', 'clinica',
     'Licencia de Apertura de Clínica',
     'Bundle de servicios para apertura y operación de clínica o consultorio médico',
     'Decreto Presidencial — Precios de Servicios Públicos',
     true, 4, 'monthly')
ON CONFLICT (bundle_code) DO NOTHING;

-- ============================================================
-- 3. Service Bundle Items (matrice prix)
-- ============================================================
-- Chaque bundle contient des services de différents ministères.
-- Les montants varient par zone (A=100%, B=75%, C=50%, D=35% approximatif).
-- On utilise les vrais service_codes de la BD fiscal_services.
--
-- Services communs aux bundles commerciaux:
--   T-183 Licencia general (Comercio)           = 100,000
--   T-189 Hoja comercial (Comercio)              = 10,000
--   T-190 Libreta comercial (Comercio)           = 10,000
--   T-191 Certificado de apertura (Comercio)     = 5,000
--   T-170 Empresas minoristas cuota (Comercio)   = 50,000
--   T-169 Empresas mayoristas cuota (Comercio)   = 50,000
--   T-409 Cert. Solvencia Tributaria (Hacienda)  = 2,000
--   T-402 Cert. Solvencia Bancaria (Hacienda)    = 27,500

-- Helper: Insert items for a bundle across all zones with tier-based pricing
-- Zone A = base_amount, B = 75%, C = 50%, D = 35%

-- =============================================
-- BARES — 8 services, ~642,000 XAF zone A1
-- =============================================
DO $$
DECLARE
    v_bundle_id UUID;
    v_zone RECORD;
    v_multiplier NUMERIC;
BEGIN
    SELECT id INTO v_bundle_id FROM service_bundles WHERE bundle_code = 'BARES';

    FOR v_zone IN SELECT id, zone_tier, zone_code FROM commerce_zones ORDER BY display_order LOOP
        -- Tier multiplier: A=1.0, B=0.75, C=0.50, D=0.35
        v_multiplier := CASE v_zone.zone_tier
            WHEN 'A' THEN 1.0 WHEN 'B' THEN 0.75 WHEN 'C' THEN 0.50 ELSE 0.35 END;

        -- T-183 Licencia general (Comercio)
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(100000 * v_multiplier, 0), 1, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-183'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        -- T-189 Hoja comercial (Comercio) — fixed across zones
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               10000, 2, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-189'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        -- T-190 Libreta comercial (Comercio) — fixed
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               10000, 3, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-190'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        -- T-191 Certificado de apertura (Comercio) — fixed
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               5000, 4, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-191'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        -- T-170 Cuota anual minorista (Comercio)
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(50000 * v_multiplier, 0), 5, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-170'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        -- T-402 Cert. Solvencia Bancaria (Hacienda) — fixed
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%hacienda%' LIMIT 1),
               27500, 6, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-402'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        -- T-409 Cert. Solvencia Tributaria (Hacienda) — fixed
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%hacienda%' LIMIT 1),
               2000, 7, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-409'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        -- T-180 Autorización profesional 6 meses (Comercio)
        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(50000 * v_multiplier, 0), 8, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-180'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;
    END LOOP;
END$$;

-- =============================================
-- RESTAURANTES — Similar to BARES but higher amounts
-- =============================================
DO $$
DECLARE
    v_bundle_id UUID;
    v_zone RECORD;
    v_multiplier NUMERIC;
BEGIN
    SELECT id INTO v_bundle_id FROM service_bundles WHERE bundle_code = 'RESTAURANTES';

    FOR v_zone IN SELECT id, zone_tier FROM commerce_zones ORDER BY display_order LOOP
        v_multiplier := CASE v_zone.zone_tier
            WHEN 'A' THEN 1.0 WHEN 'B' THEN 0.75 WHEN 'C' THEN 0.50 ELSE 0.35 END;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(135000 * v_multiplier, 0), 1, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-185'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               10000, 2, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-189'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               10000, 3, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-190'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               5000, 4, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-191'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(50000 * v_multiplier, 0), 5, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-169'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%hacienda%' LIMIT 1),
               27500, 6, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-402'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%hacienda%' LIMIT 1),
               2000, 7, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-409'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(50000 * v_multiplier, 0), 8, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-180'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;
    END LOOP;
END$$;

-- =============================================
-- CAFETERIAS — Smaller bundle, 5 services
-- =============================================
DO $$
DECLARE
    v_bundle_id UUID;
    v_zone RECORD;
    v_multiplier NUMERIC;
BEGIN
    SELECT id INTO v_bundle_id FROM service_bundles WHERE bundle_code = 'CAFETERIAS';

    FOR v_zone IN SELECT id, zone_tier FROM commerce_zones ORDER BY display_order LOOP
        v_multiplier := CASE v_zone.zone_tier
            WHEN 'A' THEN 1.0 WHEN 'B' THEN 0.75 WHEN 'C' THEN 0.50 ELSE 0.35 END;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(100000 * v_multiplier, 0), 1, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-183'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               10000, 2, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-189'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               5000, 3, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-191'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%hacienda%' LIMIT 1),
               2000, 4, true
        FROM fiscal_services fs WHERE fs.service_code = 'T-409'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;

        INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, display_order, is_fixed_across_zones)
        SELECT v_bundle_id, fs.id, v_zone.id,
               (SELECT m.id FROM ministries m WHERE m.name_es ILIKE '%comercio%' LIMIT 1),
               ROUND(50000 * v_multiplier, 0), 5, false
        FROM fiscal_services fs WHERE fs.service_code = 'T-170'
        ON CONFLICT (bundle_id, fiscal_service_id, zone_id) DO NOTHING;
    END LOOP;
END$$;

-- =============================================
-- Verification queries (run after execution)
-- =============================================
-- SELECT COUNT(*) as total_zones FROM commerce_zones;
-- SELECT COUNT(*) as total_bundles FROM service_bundles;
-- SELECT COUNT(*) as total_items FROM service_bundle_items;
-- SELECT sb.bundle_code, cz.zone_code, SUM(sbi.amount) as total_xaf
-- FROM service_bundle_items sbi
-- JOIN service_bundles sb ON sb.id = sbi.bundle_id
-- JOIN commerce_zones cz ON cz.id = sbi.zone_id
-- GROUP BY sb.bundle_code, cz.zone_code
-- ORDER BY sb.bundle_code, cz.zone_code;

COMMIT;
