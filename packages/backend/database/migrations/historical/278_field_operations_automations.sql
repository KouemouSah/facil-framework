-- ============================================================================
-- Migration 278: Field Operations Automations — Phase 3
-- ============================================================================
-- Adds SLA tracking columns to field_inspections (for idempotent checks),
-- inserts 4 email templates for supervisor notifications,
-- and 2 additional system_rules for configurable SLA thresholds.
--
-- Dependencies: 277 (supervisor field operations)
-- ============================================================================

BEGIN;

-- Set audit context
SET LOCAL app.current_user_id = '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2';

-- ============================================================================
-- 1. SLA tracking columns on service_payments (field-collected)
-- ============================================================================
-- Following the same pattern as service_payments.sla_warning_sent/sla_escalated.
-- These flags ensure scheduler jobs are idempotent (safe multi-instance).

ALTER TABLE service_payments
    ADD COLUMN IF NOT EXISTS field_sla_warning_sent BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE service_payments
    ADD COLUMN IF NOT EXISTS field_sla_escalated BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN service_payments.field_sla_warning_sent
    IS 'True when cash field collection >48h warning was sent to supervisor';
COMMENT ON COLUMN service_payments.field_sla_escalated
    IS 'True when cash field collection >5d escalation was triggered';

-- Partial index for pending field collections (hot path for SLA check)
CREATE INDEX IF NOT EXISTS idx_sp_field_sla_pending
    ON service_payments (created_at)
    WHERE collection_type = 'field'
      AND workflow_status = 'field_collected'
      AND field_sla_warning_sent = false;

-- ============================================================================
-- 2. System rules — additional SLA thresholds
-- ============================================================================

INSERT INTO system_rules (rule_code, rule_category, rule_value, value_type,
                          name_es, name_fr, name_en, description, is_active, effective_from)
VALUES
    ('FIELD_CASH_SLA_WARNING_HOURS', 'compliance', '48'::jsonb, 'number',
     'Alerta cash campo (horas)', 'Alerte cash terrain (heures)', 'Field cash warning (hours)',
     'Hours before sending SLA warning for unreconciled field cash collection', true, CURRENT_DATE),
    ('FIELD_CASH_SLA_ESCALATION_DAYS', 'compliance', '5'::jsonb, 'number',
     'Escalación cash campo (días)', 'Escalade cash terrain (jours)', 'Field cash escalation (days)',
     'Days before escalating unreconciled field cash to entity admin', true, CURRENT_DATE),
    ('FIELD_MED_EXPIRY_GRACE_DAYS', 'compliance', '0'::jsonb, 'number',
     'Gracia MED expirada (días)', 'Grâce MED expirée (jours)', 'MED expiry grace (days)',
     'Grace days after MED deadline before sending expiry alert', true, CURRENT_DATE)
ON CONFLICT (rule_code) DO NOTHING;

-- ============================================================================
-- 3. Email templates — 4 new for field operations
-- ============================================================================

-- 3a. Daily summary for supervisors
INSERT INTO email_templates (
    template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    description_es, description_fr, description_en,
    html_content, variables, category, is_active
) VALUES (
    'inspection_daily_summary',
    'Resumen diario de inspecciones',
    'Résumé quotidien des inspections',
    'Daily inspection summary',
    'Resumen del día — {{entity_code}} — {{date}}',
    'Résumé du jour — {{entity_code}} — {{date}}',
    'Daily summary — {{entity_code}} — {{date}}',
    'Resumen diario enviado al supervisor con estadísticas del día',
    'Résumé quotidien envoyé au superviseur avec les statistiques du jour',
    'Daily summary sent to supervisor with the day''s statistics',
    '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#2d5a03;color:#fff;padding:16px;text-align:center;">
    <h2 style="margin:0;">Resumen de Inspecciones</h2>
    <p style="margin:4px 0 0;opacity:0.9;">{{entity_code}} — {{date}}</p>
  </div>
  <div style="padding:20px;">
    <p>Estimado/a <strong>{{supervisor_name}}</strong>,</p>
    <p>Aquí tiene el resumen de las operaciones de campo del día:</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">Inspecciones realizadas</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;font-size:18px;font-weight:bold;">{{total_inspections}}</td></tr>
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">Conformes</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;color:#155724;">{{conforme}}</td></tr>
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">No conformes</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;color:#b33a3a;">{{non_conforme}}</td></tr>
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">Tasa de conformidad</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">{{conformity_rate}}%</td></tr>
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">Monto recaudado</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;color:#2d5a03;font-weight:bold;">{{collected_amount}} XAF</td></tr>
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">MED emitidas</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">{{med_count}}</td></tr>
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">Scellés propuestos</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">{{seal_count}}</td></tr>
      <tr><td style="padding:8px 12px;background:#f5f5f5;font-weight:bold;border:1px solid #e5e7eb;">Agentes activos</td><td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">{{agents_active}}</td></tr>
    </table>
    {{#alerts}}<div style="background:#fff3cd;border:1px solid #ffc107;padding:12px;border-radius:4px;margin:12px 0;">
      <strong>⚠ Alertas:</strong><br>{{alerts}}
    </div>{{/alerts}}
    <p style="color:#666;font-size:12px;margin-top:20px;">Este resumen fue generado automáticamente por la plataforma Facil.</p>
  </div>
</div>',
    '[
      {"name":"supervisor_name","required":true,"description":"Nombre del supervisor"},
      {"name":"entity_code","required":true,"description":"Código de la entidad"},
      {"name":"date","required":true,"description":"Fecha del resumen"},
      {"name":"total_inspections","required":true,"description":"Total inspecciones del día"},
      {"name":"conforme","required":true,"description":"Cantidad conformes"},
      {"name":"non_conforme","required":true,"description":"Cantidad no conformes"},
      {"name":"conformity_rate","required":true,"description":"Tasa de conformidad %"},
      {"name":"collected_amount","required":true,"description":"Monto total recaudado"},
      {"name":"med_count","required":true,"description":"MED emitidas"},
      {"name":"seal_count","required":true,"description":"Scellés propuestos"},
      {"name":"agents_active","required":true,"description":"Agentes activos"},
      {"name":"alerts","required":false,"description":"Alertas HTML (stale zones, inactive agents)"}
    ]'::jsonb,
    'inspections', true
) ON CONFLICT (template_code) DO NOTHING;

-- 3b. Weekly digest for supervisors
INSERT INTO email_templates (
    template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    description_es, description_fr, description_en,
    html_content, variables, category, is_active
) VALUES (
    'inspection_weekly_digest',
    'Digest semanal de inspecciones',
    'Digest hebdomadaire des inspections',
    'Weekly inspection digest',
    'Digest Semanal — {{entity_code}} — Semana {{week_number}}',
    'Digest Hebdomadaire — {{entity_code}} — Semaine {{week_number}}',
    'Weekly Digest — {{entity_code}} — Week {{week_number}}',
    'Comparativo semanal: esta semana vs semana anterior',
    'Comparatif hebdomadaire : cette semaine vs semaine précédente',
    'Weekly comparison: this week vs previous week',
    '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#2d5a03;color:#fff;padding:16px;text-align:center;">
    <h2 style="margin:0;">Digest Semanal de Inspecciones</h2>
    <p style="margin:4px 0 0;opacity:0.9;">{{entity_code}} — Semana {{week_number}}</p>
  </div>
  <div style="padding:20px;">
    <p>Estimado/a <strong>{{supervisor_name}}</strong>,</p>
    <p>Comparativo de rendimiento semanal:</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px 12px;border:1px solid #e5e7eb;text-align:left;">Métrica</th>
          <th style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">Esta semana</th>
          <th style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">Semana anterior</th>
          <th style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">Variación</th>
        </tr>
      </thead>
      <tbody>{{comparison_rows}}</tbody>
    </table>
    {{#top_agents}}<div style="margin-top:16px;"><strong>Top Agentes:</strong><br>{{top_agents}}</div>{{/top_agents}}
    {{#stale_zones}}<div style="background:#fce4e4;border:1px solid #f5c6cb;padding:12px;border-radius:4px;margin:12px 0;">
      <strong>Zonas sin inspección >30 días:</strong><br>{{stale_zones}}
    </div>{{/stale_zones}}
    <p style="color:#666;font-size:12px;margin-top:20px;">Generado automáticamente por Facil.</p>
  </div>
</div>',
    '[
      {"name":"supervisor_name","required":true,"description":"Nombre del supervisor"},
      {"name":"entity_code","required":true,"description":"Código de la entidad"},
      {"name":"week_number","required":true,"description":"Número de semana ISO"},
      {"name":"comparison_rows","required":true,"description":"HTML filas comparativas"},
      {"name":"top_agents","required":false,"description":"Top agentes de la semana"},
      {"name":"stale_zones","required":false,"description":"Zonas sin inspección reciente"}
    ]'::jsonb,
    'inspections', true
) ON CONFLICT (template_code) DO NOTHING;

-- 3c. Field cash SLA warning
INSERT INTO email_templates (
    template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    description_es, description_fr, description_en,
    html_content, variables, category, is_active
) VALUES (
    'inspection_field_sla_warning',
    'Alerta SLA: cobros de campo sin reconciliar',
    'Alerte SLA : encaissements terrain non réconciliés',
    'SLA Alert: unreconciled field collections',
    '⚠ {{count}} cobro(s) de campo pendiente(s) >{{hours}}h — {{entity_code}}',
    '⚠ {{count}} encaissement(s) terrain en attente >{{hours}}h — {{entity_code}}',
    '⚠ {{count}} field collection(s) pending >{{hours}}h — {{entity_code}}',
    'Alerta enviada al supervisor cuando cobros de campo superan el SLA de reconciliación',
    'Alerte envoyée au superviseur quand les encaissements terrain dépassent le SLA',
    'Alert sent to supervisor when field collections exceed reconciliation SLA',
    '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#f59e0b;color:#fff;padding:16px;text-align:center;">
    <h2 style="margin:0;">⚠ Alerta SLA — Cobros de Campo</h2>
    <p style="margin:4px 0 0;opacity:0.9;">{{entity_code}} — {{count}} cobro(s) pendiente(s)</p>
  </div>
  <div style="padding:20px;">
    <p>Estimado/a <strong>{{supervisor_name}}</strong>,</p>
    <p>Los siguientes cobros de campo llevan más de <strong>{{hours}} horas</strong> sin reconciliar:</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Referencia</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Agente</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Empresa</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:right;">Monto</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Fecha cobro</th>
        </tr>
      </thead>
      <tbody>{{payment_rows}}</tbody>
    </table>
    <p><strong>Acción requerida:</strong> Reconciliar estos cobros en el panel de supervisión.</p>
    <p style="color:#666;font-size:12px;margin-top:20px;">Alerta generada automáticamente por Facil.</p>
  </div>
</div>',
    '[
      {"name":"supervisor_name","required":true,"description":"Nombre del supervisor"},
      {"name":"entity_code","required":true,"description":"Código de la entidad"},
      {"name":"count","required":true,"description":"Cantidad de cobros pendientes"},
      {"name":"hours","required":true,"description":"Horas del SLA"},
      {"name":"payment_rows","required":true,"description":"HTML filas de cobros pendientes"}
    ]'::jsonb,
    'inspections', true
) ON CONFLICT (template_code) DO NOTHING;

-- 3d. MED expired alert
INSERT INTO email_templates (
    template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    description_es, description_fr, description_en,
    html_content, variables, category, is_active
) VALUES (
    'inspection_med_expired',
    'MED expirada sin acción',
    'MED expirée sans action',
    'Expired MED without action',
    '🔴 {{count}} mise(s) en demeure expirada(s) — {{entity_code}}',
    '🔴 {{count}} mise(s) en demeure expirée(s) — {{entity_code}}',
    '🔴 {{count}} expired mise(s) en demeure — {{entity_code}}',
    'Alerta cuando una mise en demeure expira sin que la empresa haya regularizado',
    'Alerte quand une mise en demeure expire sans régularisation de l''entreprise',
    'Alert when a mise en demeure expires without the company regularizing',
    '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#dc2626;color:#fff;padding:16px;text-align:center;">
    <h2 style="margin:0;">🔴 Mise en Demeure Expirada(s)</h2>
    <p style="margin:4px 0 0;opacity:0.9;">{{entity_code}} — {{count}} MED vencida(s)</p>
  </div>
  <div style="padding:20px;">
    <p>Estimado/a <strong>{{supervisor_name}}</strong>,</p>
    <p>Las siguientes mise en demeure han expirado sin regularización por parte de la empresa:</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Empresa</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">NIF</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:right;">Monto impago</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Fecha límite</th>
          <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">Agente</th>
        </tr>
      </thead>
      <tbody>{{med_rows}}</tbody>
    </table>
    <p><strong>Acción requerida:</strong> Evaluar cada caso para iniciar procedimiento de scellé o nueva notificación.</p>
    <p style="color:#666;font-size:12px;margin-top:20px;">Alerta generada automáticamente por Facil.</p>
  </div>
</div>',
    '[
      {"name":"supervisor_name","required":true,"description":"Nombre del supervisor"},
      {"name":"entity_code","required":true,"description":"Código de la entidad"},
      {"name":"count","required":true,"description":"Cantidad de MED expiradas"},
      {"name":"med_rows","required":true,"description":"HTML filas de MED expiradas"}
    ]'::jsonb,
    'inspections', true
) ON CONFLICT (template_code) DO NOTHING;

COMMIT;
