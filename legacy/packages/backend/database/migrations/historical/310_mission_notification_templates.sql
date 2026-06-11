-- Migration 310: Mission notification templates
--
-- 5 mission events x 3 channels (email + SMS + push) x 3 languages (es/fr/en)
-- Events: mission_agent_assigned, mission_started, mission_completed_summary,
--         mission_cancelled, mission_daily_reminder

BEGIN;

-- ============================================================================
-- 1. EMAIL TEMPLATES
-- ============================================================================

INSERT INTO email_templates (template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    html_content, variables, category, is_active)
VALUES
-- AGENT ASSIGNED TO MISSION
('mission_agent_assigned',
 'Asignacion a Mision', 'Affectation a Mission', 'Mission Assignment',
 'Mision de campo asignada - {{mission_date}}',
 'Mission de terrain assignee - {{mission_date}}',
 'Field Mission Assigned - {{mission_date}}',
 '<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto">
<div style="background:#1B5E20;padding:20px;text-align:center">
<h1 style="color:#fff;margin:0;font-size:22px">Mision de Campo</h1>
</div>
<div style="padding:24px;background:#fff">
<p>Estimado/a <strong>{{agent_name}}</strong>,</p>
<p>Ha sido asignado/a a una mision de campo:</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Fecha</td>
<td style="padding:8px;border-bottom:1px solid #eee;font-weight:600">{{mission_date}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Titulo</td>
<td style="padding:8px;border-bottom:1px solid #eee">{{mission_title}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Zonas</td>
<td style="padding:8px;border-bottom:1px solid #eee">{{zone_names}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Objetivo</td>
<td style="padding:8px;border-bottom:1px solid #eee">{{target_inspections}} inspecciones</td></tr>
<tr><td style="padding:8px;color:#666">Supervisor</td>
<td style="padding:8px">{{supervisor_name}}</td></tr>
</table>
<p style="color:#666;font-size:13px">Abra la app Facil Inspector para ver los detalles.</p>
</div>
<div style="background:#f5f5f5;padding:12px;text-align:center;font-size:11px;color:#999">
Facil - Plataforma de Servicios Fiscales de Guinea Ecuatorial
</div></div>',
 '["agent_name","mission_date","mission_title","zone_names","target_inspections","supervisor_name"]',
 'inspection', true),

-- MISSION STARTED
('mission_started',
 'Mision Iniciada', 'Mission Demarree', 'Mission Started',
 'Mision iniciada - {{mission_date}}',
 'Mission demarree - {{mission_date}}',
 'Mission Started - {{mission_date}}',
 '<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto">
<div style="background:#1565C0;padding:20px;text-align:center">
<h1 style="color:#fff;margin:0;font-size:22px">Mision en Curso</h1>
</div>
<div style="padding:24px;background:#fff">
<p>La mision <strong>{{mission_title}}</strong> del {{mission_date}} ha sido iniciada.</p>
<p>Zonas: {{zone_names}}</p>
<p>Objetivo: {{target_inspections}} inspecciones con {{agent_count}} agentes.</p>
</div></div>',
 '["mission_date","mission_title","zone_names","target_inspections","agent_count"]',
 'inspection', true),

-- MISSION COMPLETED SUMMARY
('mission_completed_summary',
 'Resumen Mision Completada', 'Resume Mission Terminee', 'Mission Completed Summary',
 'Mision completada - {{mission_date}} - {{actual_inspections}}/{{target_inspections}}',
 'Mission terminee - {{mission_date}} - {{actual_inspections}}/{{target_inspections}}',
 'Mission Completed - {{mission_date}} - {{actual_inspections}}/{{target_inspections}}',
 '<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto">
<div style="background:#2E7D32;padding:20px;text-align:center">
<h1 style="color:#fff;margin:0;font-size:22px">Mision Completada</h1>
</div>
<div style="padding:24px;background:#fff">
<p>Estimado/a <strong>{{supervisor_name}}</strong>,</p>
<p>La mision <strong>{{mission_title}}</strong> del {{mission_date}} ha sido completada.</p>
<h3 style="color:#2E7D32;margin-top:20px">Resultados</h3>
<table style="width:100%;border-collapse:collapse;margin:12px 0">
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Inspecciones</td>
<td style="padding:8px;border-bottom:1px solid #eee;font-weight:700">{{actual_inspections}} / {{target_inspections}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Agentes</td>
<td style="padding:8px;border-bottom:1px solid #eee">{{agent_count}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Conformes</td>
<td style="padding:8px;border-bottom:1px solid #eee;color:#2E7D32">{{conforme_count}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Non conformes</td>
<td style="padding:8px;border-bottom:1px solid #eee;color:#C62828">{{non_conforme_count}}</td></tr>
<tr><td style="padding:8px;color:#666">Montant collecte</td>
<td style="padding:8px;font-weight:700">{{collected_amount}} XAF</td></tr>
</table>
<p style="color:#666;font-size:13px">{{completion_notes}}</p>
</div>
<div style="background:#f5f5f5;padding:12px;text-align:center;font-size:11px;color:#999">
Facil - Plataforma de Servicios Fiscales de Guinea Ecuatorial
</div></div>',
 '["supervisor_name","mission_date","mission_title","actual_inspections","target_inspections","agent_count","conforme_count","non_conforme_count","collected_amount","completion_notes"]',
 'inspection', true),

-- MISSION CANCELLED
('mission_cancelled',
 'Mision Cancelada', 'Mission Annulee', 'Mission Cancelled',
 'Mision cancelada - {{mission_date}}',
 'Mission annulee - {{mission_date}}',
 'Mission Cancelled - {{mission_date}}',
 '<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto">
<div style="background:#C62828;padding:20px;text-align:center">
<h1 style="color:#fff;margin:0;font-size:22px">Mision Cancelada</h1>
</div>
<div style="padding:24px;background:#fff">
<p>Estimado/a <strong>{{agent_name}}</strong>,</p>
<p>La mision <strong>{{mission_title}}</strong> prevista el {{mission_date}} ha sido cancelada por el supervisor.</p>
<p style="color:#666">{{cancellation_reason}}</p>
</div></div>',
 '["agent_name","mission_date","mission_title","cancellation_reason"]',
 'inspection', true),

-- DAILY REMINDER (J-1)
('mission_daily_reminder',
 'Recordatorio Mision', 'Rappel Mission', 'Mission Reminder',
 'Recordatorio: Mision manana {{mission_date}}',
 'Rappel: Mission demain {{mission_date}}',
 'Reminder: Mission tomorrow {{mission_date}}',
 '<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto">
<div style="background:#E65100;padding:20px;text-align:center">
<h1 style="color:#fff;margin:0;font-size:22px">Recordatorio de Mision</h1>
</div>
<div style="padding:24px;background:#fff">
<p>Estimado/a <strong>{{agent_name}}</strong>,</p>
<p>Le recordamos que tiene una mision de campo asignada para manana:</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Fecha</td>
<td style="padding:8px;border-bottom:1px solid #eee;font-weight:600">{{mission_date}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Titulo</td>
<td style="padding:8px;border-bottom:1px solid #eee">{{mission_title}}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Zonas</td>
<td style="padding:8px;border-bottom:1px solid #eee">{{zone_names}}</td></tr>
<tr><td style="padding:8px;color:#666">Objetivo</td>
<td style="padding:8px">{{target_inspections}} inspecciones</td></tr>
</table>
</div></div>',
 '["agent_name","mission_date","mission_title","zone_names","target_inspections"]',
 'inspection', true)

ON CONFLICT (template_code) DO NOTHING;

-- ============================================================================
-- 2. SMS TEMPLATES
-- ============================================================================

INSERT INTO sms_templates (template_code, content_es, content_fr, content_en,
    category, max_segments, variables, is_active)
VALUES
('MISSION_ASSIGNED',
 '[Facil] Mision {{mission_date}}: {{zone_names}}. Objetivo: {{target_inspections}} inspecciones. Contacte supervisor.',
 '[Facil] Mission {{mission_date}}: {{zone_names}}. Objectif: {{target_inspections}} inspections. Contactez superviseur.',
 '[Facil] Mission {{mission_date}}: {{zone_names}}. Target: {{target_inspections}} inspections. Contact supervisor.',
 'inspection', 2, '["mission_date","zone_names","target_inspections"]', true),

('MISSION_REMINDER',
 '[Facil] Recordatorio: Mision manana {{mission_date}}. Zonas: {{zone_names}}. Objetivo: {{target_inspections}} insp.',
 '[Facil] Rappel: Mission demain {{mission_date}}. Zones: {{zone_names}}. Objectif: {{target_inspections}} insp.',
 '[Facil] Reminder: Mission tomorrow {{mission_date}}. Zones: {{zone_names}}. Target: {{target_inspections}} insp.',
 'inspection', 2, '["mission_date","zone_names","target_inspections"]', true),

('MISSION_CANCELLED_SMS',
 '[Facil] Mision {{mission_date}} CANCELADA. {{mission_title}}. Contacte supervisor.',
 '[Facil] Mission {{mission_date}} ANNULEE. {{mission_title}}. Contactez superviseur.',
 '[Facil] Mission {{mission_date}} CANCELLED. {{mission_title}}. Contact supervisor.',
 'inspection', 1, '["mission_date","mission_title"]', true)

ON CONFLICT (template_code) DO NOTHING;

-- ============================================================================
-- 3. PUSH NOTIFICATION TEMPLATES
-- ============================================================================

INSERT INTO push_templates (template_code, title_es, title_fr, title_en,
    body_es, body_fr, body_en,
    category, variables, is_active)
VALUES
('mission_agent_assigned',
 'Mision asignada', 'Mission assignee', 'Mission assigned',
 'Mision {{mission_date}} - {{zone_names}}. Objetivo: {{target_inspections}} inspecciones.',
 'Mission {{mission_date}} - {{zone_names}}. Objectif: {{target_inspections}} inspections.',
 'Mission {{mission_date}} - {{zone_names}}. Target: {{target_inspections}} inspections.',
 'inspection', '["mission_date","zone_names","target_inspections"]', true),

('mission_started',
 'Mision iniciada', 'Mission demarree', 'Mission started',
 'La mision {{mission_title}} ha comenzado.',
 'La mission {{mission_title}} a demarre.',
 'Mission {{mission_title}} has started.',
 'inspection', '["mission_title"]', true),

('mission_cancelled',
 'Mision cancelada', 'Mission annulee', 'Mission cancelled',
 'La mision {{mission_title}} del {{mission_date}} ha sido cancelada.',
 'La mission {{mission_title}} du {{mission_date}} a ete annulee.',
 'Mission {{mission_title}} on {{mission_date}} has been cancelled.',
 'inspection', '["mission_title","mission_date"]', true),

('mission_daily_reminder',
 'Recordatorio mision', 'Rappel mission', 'Mission reminder',
 'Mision manana {{mission_date}} - {{zone_names}}.',
 'Mission demain {{mission_date}} - {{zone_names}}.',
 'Mission tomorrow {{mission_date}} - {{zone_names}}.',
 'inspection', '["mission_date","zone_names"]', true)

ON CONFLICT (template_code) DO NOTHING;

COMMIT;
