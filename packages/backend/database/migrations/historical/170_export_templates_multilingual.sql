-- Migration 170: Add multilingual support to export_templates
-- Fix: name_es/description_es contained French text instead of Spanish
-- Add: name_fr, name_en, description_fr, description_en columns

-- Step 1: Add multilingual columns
ALTER TABLE export_templates
ADD COLUMN IF NOT EXISTS name_fr VARCHAR(255),
ADD COLUMN IF NOT EXISTS name_en VARCHAR(255),
ADD COLUMN IF NOT EXISTS description_fr TEXT,
ADD COLUMN IF NOT EXISTS description_en TEXT;

-- Step 2: Fix data — name_es/description_es were in French, correct them
UPDATE export_templates SET
    name_es = 'Exportación SAGE X3 Estándar',
    name_fr = 'Export SAGE X3 Standard',
    name_en = 'SAGE X3 Standard Export',
    description_es = 'Exportación estándar para integración SAGE X3 - Diario de Tesorería',
    description_fr = 'Export standard pour intégration SAGE X3 - Journal Trésorerie',
    description_en = 'Standard export for SAGE X3 integration - Treasury Journal'
WHERE code = 'SAGE_X3_STANDARD';

UPDATE export_templates SET
    name_es = 'Informe Ministerial Mensual',
    name_fr = 'Rapport Ministériel Mensuel',
    name_en = 'Monthly Ministry Report',
    description_es = 'Informe mensual PDF para los ministerios',
    description_fr = 'Rapport mensuel PDF pour les ministères',
    description_en = 'Monthly PDF report for ministries'
WHERE code = 'MINISTRY_MONTHLY';

UPDATE export_templates SET
    name_es = 'Conciliación Diaria',
    name_fr = 'Réconciliation Journalière',
    name_en = 'Daily Reconciliation',
    description_es = 'Exportación diaria para verificación de conciliación',
    description_fr = 'Export journalier pour vérification réconciliation',
    description_en = 'Daily export for reconciliation verification'
WHERE code = 'RECONCILIATION_DAILY';

-- Step 3: Add new templates (columns_config required NOT NULL)
INSERT INTO export_templates (code, name_es, name_fr, name_en, export_type, export_format, description_es, description_fr, description_en, config, columns_config, is_active)
VALUES
    ('AUDIT_MONTHLY', 'Informe de Auditoría Mensual', 'Rapport d''Audit Mensuel', 'Monthly Audit Report',
     'audit_report', 'xlsx',
     'Registro detallado de acciones de agentes sobre pagos',
     'Registre détaillé des actions des agents sur les paiements',
     'Detailed record of all agent actions on payments',
     '{"include_agent_actions": true}'::jsonb,
     '[{"source":"payment_reference","target":"Reference"},{"source":"action","target":"Action"},{"source":"agent_name","target":"Agent"},{"source":"created_at","target":"Date"}]'::jsonb,
     true),
    ('BEAC_QUARTERLY', 'Reporte BEAC Trimestral', 'Rapport BEAC Trimestriel', 'BEAC Quarterly Report',
     'bank_central', 'xml',
     'Reporte XML trimestral para el Banco Central (BEAC)',
     'Rapport XML trimestriel pour la Banque Centrale (BEAC)',
     'Quarterly XML report for Central Bank (BEAC)',
     '{"format": "beac_xml_v2"}'::jsonb,
     '[{"source":"payment_reference","target":"REF"},{"source":"total_amount","target":"MONTANT"},{"source":"currency","target":"DEVISE"},{"source":"validated_at","target":"DATE"}]'::jsonb,
     true),
    ('CUSTOM_FILTERED', 'Exportación Personalizada', 'Export Personnalisé', 'Custom Export',
     'custom', 'csv',
     'Exportación personalizada con filtros avanzados',
     'Export personnalisé avec filtres avancés',
     'Custom export with advanced filters',
     '{"allow_custom_filters": true}'::jsonb,
     '[{"source":"payment_reference","target":"Reference"},{"source":"total_amount","target":"Amount"},{"source":"payment_method","target":"Method"},{"source":"workflow_status","target":"Status"}]'::jsonb,
     true)
ON CONFLICT DO NOTHING;
