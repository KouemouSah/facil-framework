-- Migration 206: Correct Service Bundle Seed Data
-- Source: Precios.pdf (Decreto Presidencial GE)
-- Generated from verified precios_data.json (948 items, 0 verification errors)
-- Replaces incorrect data from migration 204

BEGIN;

-- ============================================================
-- 1. UPDATE MINISTRY NAMES (current government structure)
-- Source: ministerios.md (Decreto de Gobierno)
-- ============================================================

UPDATE ministries SET name_es = 'MINISTERIO DE HACIENDA, PLANIFICACION Y DESARROLLO ECONOMICO',
  description_es = 'Excmo. Sr. Don Ivan BACALE EBE MOLINA'
WHERE id = 91;

UPDATE ministries SET name_es = 'MINISTERIO DE INFORMACION, PRENSA Y CULTURA',
  description_es = 'Excmo. Sr. Don Jeronimo OSA OSA ECORO'
WHERE id = 92;

UPDATE ministries SET name_es = 'MINISTERIO DE ASUNTOS EXTERIORES, COOPERACION INTERNACIONAL Y DIASPORA',
  description_es = 'Excmo. Sr. Don Simeon OYONO ESONO ANGUE'
WHERE id = 85;

UPDATE ministries SET name_es = 'MINISTERIO DE AVIACION CIVIL E INFRAESTRUCTURAS AEROPORTUARIAS',
  description_es = 'Excmo. Sr. Don Bartolome MONSUY MANE ANDEME'
WHERE id = 86;

UPDATE ministries SET name_es = 'MINISTERIO DE INTERIOR Y ADMINISTRACION LOCAL',
  description_es = 'Excmo. Sr. Don Victoriano ENGONGA KEA'
WHERE id = 93;

UPDATE ministries SET name_es = 'MINISTERIO DE HIDROCARBUROS Y DESARROLLO MINERO',
  description_es = 'Excmo. Sr. Don Antonio OBURU ONDO'
WHERE id = 94;

UPDATE ministries SET name_es = 'MINISTERIO DE OBRAS PUBLICAS Y URBANISMO',
  description_es = 'Excmo. Sr. Don Clemente FEREIRO VILLARINO'
WHERE id = 95;

UPDATE ministries SET name_es = 'MINISTERIO DE EDUCACION, CIENCIAS, ENSENANZA PROFESIONAL Y DEPORTES',
  description_es = 'Excmo. Sr. Don Clemente ENGONGA NGUEMA ONGUENE'
WHERE id = 90;

UPDATE ministries SET name_es = 'MINISTERIO DE TRANSPORTE, TELECOMUNICACIONES Y SISTEMAS DE INTELIGENCIA ARTIFICIAL',
  description_es = 'Excmo. Sr. Don Honorato EVITA OMA'
WHERE id = 97;

-- Ministry 88 (old CULTURA) — update name to reflect current structure
UPDATE ministries SET name_es = 'MINISTERIO DE IGUALDAD DE GENERO, ASUNTOS SOCIALES Y ARTESANIA',
  description_es = 'Excma. Sra. Dona Consuelo NGUEMA OYANA'
WHERE id = 88;

-- Ministry 87 — KEEP as COMERCIO (owns sector 99 with 69 fiscal services)
UPDATE ministries SET name_es = 'MINISTERIO DE COMERCIO Y PROMOCION DE PEQUENAS Y MEDIANAS EMPRESAS',
  description_es = 'Sector de Comercio - servicios de licencias comerciales, importacion/exportacion, PYMES'
WHERE id = 87;

-- NEW MINISTRIES
INSERT INTO ministries (id, ministry_code, name_es, description_es) VALUES
  (103, 'M-015', 'MINISTERIO DE TURISMO E INFRAESTRUCTURAS TURISTICAS',
   'Excmo. Sr. Don Antonio OLIVEIRA BORUPU')
ON CONFLICT (id) DO UPDATE SET name_es = EXCLUDED.name_es, description_es = EXCLUDED.description_es;

INSERT INTO ministries (id, ministry_code, name_es, description_es) VALUES
  (104, 'M-016', 'MINISTERIO DE AGRICULTURA, GANADERIA, BOSQUES, PESCA Y MEDIO AMBIENTE',
   'Excmo. Sr. Don Juan Jose NDONG TOM')
ON CONFLICT (id) DO UPDATE SET name_es = EXCLUDED.name_es, description_es = EXCLUDED.description_es;

INSERT INTO ministries (id, ministry_code, name_es, description_es) VALUES
  (105, 'M-017', 'MINISTERIO DE ELECTRICIDAD Y ENERGIAS RENOVABLES',
   'Excmo. Sr. Don Gervasio ENGONGA MBA')
ON CONFLICT (id) DO UPDATE SET name_es = EXCLUDED.name_es, description_es = EXCLUDED.description_es;

INSERT INTO ministries (id, ministry_code, name_es, description_es) VALUES
  (106, 'M-018', 'MINISTERIO DE LA FUNCION PUBLICA Y REFORMA ADMINISTRATIVA Y SEGURIDAD SOCIAL',
   'Excmo. Sr. Don Candido MUATETEMA BAHITA')
ON CONFLICT (id) DO UPDATE SET name_es = EXCLUDED.name_es, description_es = EXCLUDED.description_es;

-- ============================================================
-- 2. FISCAL SERVICES (rename + create)
-- ============================================================

-- Rename T-189 (Hoja comercial -> Ficha comercial, per PDF)
UPDATE fiscal_services SET name_es = 'Ficha comercial' WHERE id = 196 AND service_code = 'T-189';

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-993', 'Contribucion Mobiliaria Fiscal (CMF)', 392, 'administrative_tax', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-994', 'Cuota Anual comercial', 371, 'registration_fee', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-995', 'Certificado de Comercio', 374, 'document_processing', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-996', 'Certificado de Actualizacion PE', 374, 'document_processing', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-997', 'Rotulos no Luminosos', 374, 'license_permit', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-998', 'Autorizacion de venta Pescados abacer\u00edas', 374, 'license_permit', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-999', 'Licencia de Turismo', 438, 'license_permit', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-1000', 'Inspeccion Anual comercial', 374, 'inspection_fee', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-1001', 'Licencia Medio Ambiental', 374, 'license_permit', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

INSERT INTO fiscal_services (service_code, name_es, category_id, service_type, calculation_method, tasa_expedicion, status)
VALUES ('T-1002', 'Licencia de Cultura', 374, 'license_permit', 'tiered_rates', 0, 'active')
ON CONFLICT (service_code) DO UPDATE SET name_es = EXCLUDED.name_es;

-- ============================================================
-- 3. DELETE OLD INCORRECT SEED DATA (migration 204)
-- 0 FK references from service_requests — safe to delete
-- ============================================================

DELETE FROM service_bundle_items;  -- 252 incorrect items
DELETE FROM service_bundles;  -- 10 incorrect bundles

-- ============================================================
-- 4. UPDATE ZONE NAMES (PDF categories, not city names)
-- ============================================================

UPDATE commerce_zones SET name_es = 'Capitales de Regiones', description_es = 'Malabo, Bata - centros comerciales principales' WHERE zone_code = 'A1';
UPDATE commerce_zones SET name_es = 'Capitales de Regiones (2)', description_es = 'Malabo, Bata - zonas secundarias' WHERE zone_code = 'A2';
UPDATE commerce_zones SET name_es = 'Capitales de Regiones (3)', description_es = 'Malabo, Bata - periferia' WHERE zone_code = 'A3';
UPDATE commerce_zones SET name_es = 'Capitales de Provincias', description_es = 'Ebebiyin, Mongomo, Evinayong y similares' WHERE zone_code = 'B1';
UPDATE commerce_zones SET name_es = 'Capitales de Provincias (2)', description_es = 'Capitales provinciales - zonas secundarias' WHERE zone_code = 'B2';
UPDATE commerce_zones SET name_es = 'Capitales de Provincias (3)', description_es = 'Capitales provinciales - periferia' WHERE zone_code = 'B3';
UPDATE commerce_zones SET name_es = 'Capitales Distritales y Municipales', description_es = 'Luba, Riaba, Niefang, Anisok y similares' WHERE zone_code = 'C1';
UPDATE commerce_zones SET name_es = 'Capitales Distritales y Municipales (2)', description_es = 'Distritos - zonas secundarias' WHERE zone_code = 'C2';
UPDATE commerce_zones SET name_es = 'Capitales Distritales y Municipales (3)', description_es = 'Distritos - periferia' WHERE zone_code = 'C3';
UPDATE commerce_zones SET name_es = 'Consejos de Poblados', description_es = 'Poblados principales' WHERE zone_code = 'D1';
UPDATE commerce_zones SET name_es = 'Consejos de Poblados (2)', description_es = 'Poblados secundarios' WHERE zone_code = 'D2';
UPDATE commerce_zones SET name_es = 'Consejos de Poblados (3)', description_es = 'Poblados rurales remotos' WHERE zone_code = 'D3';

-- ============================================================
-- 5. INSERT CORRECT BUNDLES (10 from Precios.pdf)
-- ============================================================

INSERT INTO service_bundles (bundle_code, commerce_type, name_es, description_es, legal_reference,
                             installment_eligible, max_installments, installment_frequency)
VALUES
    ('ABACERIAS', 'abaceria', 'Abacerias, Factorias y Comercio en General', 'Bundle de servicios fiscales para abacerias, factorias y comercio en general', 'Decreto Presidencial - Precios de Servicios Publicos', true, 4, 'monthly'),
    ('FERRETERIAS', 'ferreteria', 'Ferreterias', 'Bundle de servicios fiscales para ferreterias', 'Decreto Presidencial - Precios de Servicios Publicos', true, 4, 'monthly'),
    ('CAFETERIAS_PASTELERIAS', 'cafeteria_pasteleria', 'Cafeterias-Pastelerias, Panaderias y Snack Bar', 'Bundle de servicios fiscales para cafeterias-pastelerias, panaderias y snack bar', 'Decreto Presidencial - Precios de Servicios Publicos', true, 4, 'monthly'),
    ('BARES_RESTAURANTES', 'bar_restaurante', 'Bares y Restaurantes', 'Bundle de servicios fiscales para bares y restaurantes', 'Decreto Presidencial - Precios de Servicios Publicos', true, 4, 'monthly'),
    ('DISCOTECAS', 'discoteca', 'Discotecas y Similares', 'Bundle de servicios fiscales para discotecas y similares', 'Decreto Presidencial - Precios de Servicios Publicos', true, 4, 'monthly'),
    ('CLINICAS_FARMACIAS', 'clinica_farmacia', 'Clinicas, Farmacias y Similares', 'Bundle de servicios fiscales para clinicas, farmacias y similares', 'Decreto Presidencial - Precios de Servicios Publicos', true, 4, 'monthly'),
    ('TALLERES_BLOQUERIAS', 'taller_bloqueria', 'Talleres y Bloquerias en General', 'Bundle de servicios fiscales para talleres y bloquerias en general', 'Decreto Presidencial - Precios de Servicios Publicos', true, 4, 'monthly'),
    ('TALLERES_ARTESANALES', 'taller_artesanal', 'Talleres y Tiendas Artesanales', 'Bundle de servicios fiscales para talleres y tiendas artesanales', 'Decreto Presidencial - Precios de Servicios Publicos', false, 2, 'monthly'),
    ('VIDEOS_CLUBS', 'video_club', 'Video Clubs y Similares', 'Bundle de servicios fiscales para video clubs y similares', 'Decreto Presidencial - Precios de Servicios Publicos', false, 2, 'monthly'),
    ('CARPINTERIAS', 'carpinteria', 'Carpinterias en General', 'Bundle de servicios fiscales para carpinterias en general', 'Decreto Presidencial - Precios de Servicios Publicos', false, 2, 'monthly');

-- ============================================================
-- 6. INSERT CORRECT BUNDLE ITEMS (948 from verified PDF data)
-- Uses subqueries to resolve UUIDs and fiscal_service IDs
-- ============================================================

-- ABACERIAS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 30000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 104, 27000, false, 8, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'ABACERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-998'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 104, 27000, false, 8, true);

-- FERRETERIAS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 30000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 50000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 100000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 5000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 20000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 10000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 30000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 20000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 100000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 5000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 20000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 10000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 30000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'FERRETERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true);

-- CAFETERIAS_PASTELERIAS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 103, 90000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 50000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 5000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 20000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 10000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 103, 60000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 103, 90000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 103, 60000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 103, 90000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 103, 60000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 103, 90000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 103, 6000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CAFETERIAS_PASTELERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 103, 45000, false, 9, true);

-- BARES_RESTAURANTES
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 103, 60000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 103, 30000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 103, 60000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 103, 60000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 103, 30000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 103, 60000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 103, 45000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'BARES_RESTAURANTES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 103, 30000, false, 9, true);

-- DISCOTECAS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 103, 300000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 103, 180000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 103, 120000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 103, 300000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 103, 180000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 103, 120000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 103, 300000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 103, 180000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 103, 120000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 103, 300000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 103, 180000, false, 9, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'DISCOTECAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-999'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 103, 120000, false, 9, true);

-- CLINICAS_FARMACIAS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CLINICAS_FARMACIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true);

-- TALLERES_BLOQUERIAS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 105, 120000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 105, 90000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 105, 45000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 105, 120000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 105, 90000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 105, 45000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 105, 120000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 105, 90000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 105, 45000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 105, 120000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 105, 90000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 104, 180000, false, 11, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 105, 45000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_BLOQUERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1001'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 104, 180000, false, 11, true);

-- TALLERES_ARTESANALES
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 9000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'TALLERES_ARTESANALES'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 9000, false, 12, true);

-- VIDEOS_CLUBS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 2000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 2000, false, 12, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'VIDEOS_CLUBS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1002'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 2000, false, 12, true);

-- CARPINTERIAS
INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 480000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 105, 120000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 216000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 105, 90000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 60000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 105, 45000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'A3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 120000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 105, 12000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 45000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 105, 90000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 105, 45000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'B3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 30000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 60000, false, 2, true);

INSERT INTO service_bundle_items (bundle_id, fiscal_service_id, zone_id, ministry_id, amount, is_fixed_across_zones, display_order, is_active)
VALUES
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 105, 120000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 24000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 105, 90000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 18000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 105, 45000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'C3'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 60000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 105, 12000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D1'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 30000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 105, 12000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D2'), 92, 18000, false, 7, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-993'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 9000, false, 1, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-994'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 2, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-189'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 3, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-995'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 12000, false, 4, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-190'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 6000, false, 5, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-996'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 91, 3000, false, 6, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-1000'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 105, 12000, false, 10, true),
    ((SELECT id FROM service_bundles WHERE bundle_code = 'CARPINTERIAS'), (SELECT id FROM fiscal_services WHERE service_code = 'T-997'), (SELECT id FROM commerce_zones WHERE zone_code = 'D3'), 92, 18000, false, 7, true);

-- ============================================================
-- 7. VERIFICATION QUERIES (run after migration)
-- ============================================================

-- Expected: 948 items total
-- SELECT COUNT(*) FROM service_bundle_items;
-- Expected: 10 bundles
-- SELECT COUNT(*) FROM service_bundles;
-- Verify BARES_RESTAURANTES A1 total = 642,000 XAF:
-- SELECT SUM(sbi.amount) FROM service_bundle_items sbi
--   JOIN service_bundles sb ON sb.id = sbi.bundle_id
--   JOIN commerce_zones cz ON cz.id = sbi.zone_id
--   WHERE sb.bundle_code = 'BARES_RESTAURANTES' AND cz.zone_code = 'A1';

COMMIT;