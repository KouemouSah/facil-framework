-- Migration: 024_seed_workflow_tariffs.sql
-- Date: 2025-12-27
-- Description: Données initiales des tarifs et suppléments
-- Author: TaxasGE Development Team
-- Note: Ces données peuvent être modifiées via l'interface admin sans redéploiement

-- ============================================================================
-- 1. SUPPLÉMENTS (Cédulas, Pólizas, Timbres)
-- ============================================================================

INSERT INTO tariff_supplements (code, name_es, amount, legal_reference)
VALUES
    ('CEDULA_PERSONAL', 'Cédula Personal', 1500, 'Ley de Tasas Fiscales'),
    ('POLIZA', 'Póliza', 1000, 'Ley de Tasas Fiscales'),
    ('TIMBRE_FISCAL', 'Timbre Fiscal', 500, 'Ley de Tasas Fiscales')
ON CONFLICT (code) DO UPDATE SET
    name_es = EXCLUDED.name_es,
    amount = EXCLUDED.amount,
    legal_reference = EXCLUDED.legal_reference;

-- ============================================================================
-- 2. TARIFS CARNET FUNCIONARIO
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('carnet_funcionario', 'expedicion', 3500, 'Ley 2/2014, Art. 47'),
    ('carnet_funcionario', 'renovacion', 3500, 'Ley 2/2014, Art. 47'),
    ('carnet_funcionario', 'duplicado', 3500, 'Ley 2/2014, Art. 47')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 3. TARIFS CERTIFICADO ADMINISTRATIVO
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('certificado_administrativo', 'expedicion', 2000, 'Precios_por_los_servicios.pdf'),
    ('certificado_administrativo', 'renovacion', 2000, 'Precios_por_los_servicios.pdf')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. TARIFS PERMISO EXTRAORDINARIO
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('permiso_extraordinario', 'expedicion', 1500, 'Precios_por_los_servicios.pdf')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 5. TARIFS PROMOCION ADMINISTRATIVA
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('promocion_administrativa', 'expedicion', 5000, 'Precios_por_los_servicios.pdf')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 6. TARIFS RESIDENCIA (exemple - à ajuster selon tarifs réels)
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('residencia', 'expedicion', 25000, 'Ley de Extranjería'),
    ('residencia', 'renovacion', 20000, 'Ley de Extranjería'),
    ('residencia_renovacion', 'renovacion', 20000, 'Ley de Extranjería')
ON CONFLICT DO NOTHING;

-- Configuration suppléments pour Residencia (Cédulas requises)
INSERT INTO workflow_supplement_config (workflow_code, supplement_code, quantity_per_request, is_required)
VALUES
    ('residencia', 'CEDULA_PERSONAL', 1, TRUE),
    ('residencia', 'POLIZA', 1, TRUE),
    ('residencia_renovacion', 'CEDULA_PERSONAL', 1, TRUE),
    ('residencia_renovacion', 'POLIZA', 1, TRUE)
ON CONFLICT (workflow_code, supplement_code) DO UPDATE SET
    quantity_per_request = EXCLUDED.quantity_per_request,
    is_required = EXCLUDED.is_required;

-- ============================================================================
-- 7. TARIFS CERTIFICADO CONDUCIR (exemple)
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('certificado_conducir_nuevo', 'expedicion', 15000, 'DGT'),
    ('certificado_conducir_renovacion', 'renovacion', 12000, 'DGT')
ON CONFLICT DO NOTHING;

-- Configuration suppléments (Cédula requise)
INSERT INTO workflow_supplement_config (workflow_code, supplement_code, quantity_per_request, is_required)
VALUES
    ('certificado_conducir_nuevo', 'CEDULA_PERSONAL', 1, TRUE),
    ('certificado_conducir_renovacion', 'CEDULA_PERSONAL', 1, TRUE)
ON CONFLICT (workflow_code, supplement_code) DO UPDATE SET
    quantity_per_request = EXCLUDED.quantity_per_request,
    is_required = EXCLUDED.is_required;

-- ============================================================================
-- 8. TARIFS PASAPORTE (exemple - lié à fiscal_services si existe)
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('pasaporte_nuevo', 'expedicion', 55000, 'CNEDOGE'),
    ('pasaporte_renovacion', 'renovacion', 45000, 'CNEDOGE')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 9. TARIFS TRANSFERENCIA VEHICULO (exemple)
-- ============================================================================

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('transferencia_vehiculo', 'expedicion', 35000, 'DGT Tráfico')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 10. TARIFS RENOVACION VEHICULO (CUVE, ITV)
-- ============================================================================
-- Note: Workflow pour renouvellement des papiers du véhicule (CUVE + ITV)
-- Distinct de transferencia_vehiculo qui est pour le changement de propriétaire
-- ⚠️ IMPORTANT: Montant à définir via interface admin - valeur placeholder

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference, is_active)
VALUES
    ('renovacion_vehiculo', 'renovacion', 0, 'DGT Tráfico - À CONFIGURER VIA ADMIN', FALSE)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 11. TARIFS CONTRATO ONRC (pourcentage - géré différemment)
-- ============================================================================
-- Note: ONRC utilise un pourcentage (0.5%) du montant du contrat
-- Ceci sera géré par le RBC Calculator avec fiscal_services

INSERT INTO workflow_tariffs (workflow_code, solicitud_type, amount, legal_reference)
VALUES
    ('contrato_onrc', 'expedicion', 10000, 'ONRC - Minimum 10,000 XAF ou 0.5% du contrat')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICATION: Afficher le résumé
-- ============================================================================

-- Cette requête peut être exécutée pour vérifier les données
-- SELECT * FROM v_workflow_tariffs_summary;

-- ============================================================================
-- END OF SEED DATA
-- ============================================================================
