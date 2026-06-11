-- Migration 309: Citizen alert templates for obligation lifecycle
--
-- 3 alert types x 3 channels (email + SMS + push) x 3 languages (es/fr/en)
-- Templates: obligation_overdue, obligation_penalty_applied, obligation_reminder

BEGIN;

-- ============================================================================
-- 1. EMAIL TEMPLATES
-- ============================================================================

INSERT INTO email_templates (template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    html_content, variables, category, is_active)
VALUES
-- OVERDUE
('obligation_overdue',
 'Obligaciones Vencidas', 'Obligations en Retard', 'Overdue Obligations',
 'Obligaciones vencidas - {{company_name}}',
 'Obligations en retard - {{company_name}}',
 'Overdue obligations - {{company_name}}',
 '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
<h2 style="color:#dc2626">Obligaciones Vencidas</h2>
<p>Estimado/a {{user_name}},</p>
<p>Le informamos que <strong>{{obligations_count}} obligacion(es)</strong> de la empresa <strong>{{company_name}}</strong> han superado su fecha de vencimiento.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
<tr style="background:#fee2e2"><td style="padding:8px;font-weight:bold">Monto total vencido</td><td style="padding:8px;text-align:right;font-weight:bold">{{total_amount}} XAF</td></tr>
</table>
<p>Le recomendamos regularizar su situacion lo antes posible para evitar penalidades adicionales.</p>
<p style="margin-top:20px"><a href="https://facil.gq/dashboard/empresas" style="background:#dc2626;color:white;padding:10px 20px;border-radius:4px;text-decoration:none">Ver mis obligaciones</a></p>
<p style="color:#888;font-size:12px;margin-top:20px">Este mensaje es automatico. No responda a este correo.</p>
</div>',
 '["user_name","company_name","obligations_count","total_amount"]'::jsonb,
 'fiscal_alerts', true),

-- PENALTY APPLIED
('obligation_penalty_applied',
 'Penalidad Aplicada', 'Penalite Appliquee', 'Penalty Applied',
 'Penalidad aplicada - {{company_name}}',
 'Penalite appliquee - {{company_name}}',
 'Penalty applied - {{company_name}}',
 '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
<h2 style="color:#f59e0b">Penalidad Aplicada</h2>
<p>Estimado/a {{user_name}},</p>
<p>Se ha aplicado una penalidad a <strong>{{obligations_affected}} obligacion(es)</strong> de la empresa <strong>{{company_name}}</strong> por retraso en el pago.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
<tr style="background:#fef3c7"><td style="padding:8px;font-weight:bold">Penalidad total</td><td style="padding:8px;text-align:right;font-weight:bold;color:#dc2626">{{penalty_total}} XAF</td></tr>
</table>
<p>Regularice su situacion para evitar que la penalidad aumente.</p>
<p style="margin-top:20px"><a href="https://facil.gq/dashboard/empresas" style="background:#f59e0b;color:white;padding:10px 20px;border-radius:4px;text-decoration:none">Pagar ahora</a></p>
<p style="color:#888;font-size:12px;margin-top:20px">Este mensaje es automatico. No responda a este correo.</p>
</div>',
 '["user_name","company_name","penalty_total","obligations_affected"]'::jsonb,
 'fiscal_alerts', true),

-- REMINDER (polyvalent: deadline + renewal)
('obligation_reminder',
 'Recordatorio Fiscal', 'Rappel Fiscal', 'Fiscal Reminder',
 'Recordatorio - {{company_name}}',
 'Rappel - {{company_name}}',
 'Reminder - {{company_name}}',
 '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
<h2 style="color:#2563eb">Recordatorio Fiscal</h2>
<p>Estimado/a {{user_name}},</p>
<p>{{message}}</p>
<p>Empresa: <strong>{{company_name}}</strong></p>
<p style="margin-top:20px"><a href="https://facil.gq/dashboard/empresas" style="background:#2563eb;color:white;padding:10px 20px;border-radius:4px;text-decoration:none">Ver mis empresas</a></p>
<p style="color:#888;font-size:12px;margin-top:20px">Este mensaje es automatico. No responda a este correo.</p>
</div>',
 '["user_name","company_name","message","fiscal_year"]'::jsonb,
 'fiscal_alerts', true)
ON CONFLICT (template_code) DO NOTHING;

-- ============================================================================
-- 2. SMS TEMPLATES
-- ============================================================================

INSERT INTO sms_templates (template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    variables, category, max_segments, is_active)
VALUES
('OBLIGATION_OVERDUE',
 'Obligaciones Vencidas', 'Obligations en Retard', 'Overdue Obligations',
 'FACIL: {{obligations_count}} obligacion(es) de {{company_name}} han vencido. Monto: {{total_amount}} XAF. Regularice en facil.gq',
 'FACIL: {{obligations_count}} obligation(s) de {{company_name}} en retard. Montant: {{total_amount}} XAF. Regularisez sur facil.gq',
 'FACIL: {{obligations_count}} obligation(s) of {{company_name}} overdue. Amount: {{total_amount}} XAF. Regularize at facil.gq',
 '["company_name","obligations_count","total_amount"]'::jsonb,
 'fiscal_alerts', 2, true),

('OBLIGATION_PENALTY_APPLIED',
 'Penalidad Aplicada', 'Penalite Appliquee', 'Penalty Applied',
 'FACIL: Penalidad de {{penalty_total}} XAF aplicada a {{company_name}}. Pague para evitar incrementos. facil.gq',
 'FACIL: Penalite de {{penalty_total}} XAF appliquee a {{company_name}}. Payez pour eviter les augmentations. facil.gq',
 'FACIL: Penalty of {{penalty_total}} XAF applied to {{company_name}}. Pay to avoid increases. facil.gq',
 '["company_name","penalty_total"]'::jsonb,
 'fiscal_alerts', 2, true),

('OBLIGATION_REMINDER',
 'Recordatorio Fiscal', 'Rappel Fiscal', 'Fiscal Reminder',
 'FACIL: Recordatorio para {{company_name}} - {{message}}. facil.gq',
 'FACIL: Rappel pour {{company_name}} - {{message}}. facil.gq',
 'FACIL: Reminder for {{company_name}} - {{message}}. facil.gq',
 '["company_name","message"]'::jsonb,
 'fiscal_alerts', 2, true)
ON CONFLICT (template_code) DO NOTHING;

-- ============================================================================
-- 3. PUSH TEMPLATES
-- ============================================================================

INSERT INTO push_templates (template_code, name_es, name_fr, name_en,
    title_es, title_fr, title_en,
    body_es, body_fr, body_en,
    click_action, variables, platform, ttl_seconds, is_active)
VALUES
('OBLIGATION_OVERDUE',
 'Obligaciones Vencidas', 'Obligations en Retard', 'Overdue Obligations',
 'Obligaciones vencidas', 'Obligations en retard', 'Overdue obligations',
 '{{obligations_count}} obligacion(es) de {{company_name}} vencidas. {{total_amount}} XAF.',
 '{{obligations_count}} obligation(s) de {{company_name}} en retard. {{total_amount}} XAF.',
 '{{obligations_count}} obligation(s) of {{company_name}} overdue. {{total_amount}} XAF.',
 '/dashboard/empresas', '["company_name","obligations_count","total_amount"]'::jsonb,
 'all', 86400, true),

('OBLIGATION_PENALTY_APPLIED',
 'Penalidad Aplicada', 'Penalite Appliquee', 'Penalty Applied',
 'Penalidad aplicada', 'Penalite appliquee', 'Penalty applied',
 'Penalidad de {{penalty_total}} XAF a {{company_name}}.',
 'Penalite de {{penalty_total}} XAF a {{company_name}}.',
 'Penalty of {{penalty_total}} XAF to {{company_name}}.',
 '/dashboard/empresas', '["company_name","penalty_total"]'::jsonb,
 'all', 86400, true),

('OBLIGATION_REMINDER',
 'Recordatorio Fiscal', 'Rappel Fiscal', 'Fiscal Reminder',
 'Recordatorio fiscal', 'Rappel fiscal', 'Fiscal reminder',
 '{{company_name}}: {{message}}',
 '{{company_name}}: {{message}}',
 '{{company_name}}: {{message}}',
 '/dashboard/empresas', '["company_name","message"]'::jsonb,
 'all', 86400, true)
ON CONFLICT (template_code) DO NOTHING;

COMMIT;
