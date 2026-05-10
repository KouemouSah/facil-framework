-- Migration 220: License notification templates (email + SMS)
-- Adds LICENSE_GENERATED email template and SMS template for license issuance notifications.
-- Part of Session 1B — License PDF Redesign Phase 4.

BEGIN;

-- ── Email template: LICENSE_GENERATED ────────────────────────────────────────

INSERT INTO email_templates (
    template_code,
    name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    description_es, description_fr, description_en,
    html_content,
    variables, category, is_active,
    created_at, updated_at
) VALUES (
    'LICENSE_GENERATED',
    'Licencia comercial generada',
    'Licence commerciale générée',
    'Commercial license generated',
    'Su licencia comercial {{license_ref}} está disponible',
    'Votre licence commerciale {{license_ref}} est disponible',
    'Your commercial license {{license_ref}} is available',
    'Email enviado cuando se genera una licencia comercial, con PDF adjunto',
    'Email envoyé lors de la génération d''une licence commerciale, avec PDF joint',
    'Email sent when a commercial license is generated, with PDF attachment',
    '<h2>Licencia Comercial Generada</h2>
<p>Estimado/a <strong>{{company_name}}</strong>,</p>
<p>Su licencia comercial para el año fiscal <strong>{{fiscal_year}}</strong> ha sido generada correctamente.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
  <tr><td style="padding:6px 12px;background:#f5f5f5;font-weight:bold;">Referencia</td><td style="padding:6px 12px;">{{license_ref}}</td></tr>
  <tr><td style="padding:6px 12px;background:#f5f5f5;font-weight:bold;">NIF / Nº Registro</td><td style="padding:6px 12px;">{{nif}}</td></tr>
  <tr><td style="padding:6px 12px;background:#f5f5f5;font-weight:bold;">Total Obligaciones</td><td style="padding:6px 12px;">{{total_amount}} XAF</td></tr>
  <tr><td style="padding:6px 12px;background:#f5f5f5;font-weight:bold;">Estado</td><td style="padding:6px 12px;">{{status}}</td></tr>
</table>
<p>Encontrará el documento PDF adjunto a este correo. También puede descargarlo desde su panel en la plataforma Facil.</p>
<p><strong>AVISO:</strong> Este documento es un justificante provisional que acredita que la licencia comercial oficial se encuentra en proceso de edición.</p>
<p>Atentamente,<br>Dirección General de Impuestos — Guinea Ecuatorial</p>',
    '[
      {"name": "company_name", "required": true, "description": "Nombre de la empresa", "example": "Tienda Hermionne"},
      {"name": "license_ref", "required": true, "description": "Referencia de la licencia", "example": "LIC-2026-A1B2C3D4"},
      {"name": "fiscal_year", "required": true, "description": "Año fiscal", "example": "2026"},
      {"name": "nif", "required": false, "description": "NIF o Nº Registro", "example": "PE-8253"},
      {"name": "total_amount", "required": true, "description": "Total obligaciones", "example": "170,750"},
      {"name": "status", "required": true, "description": "Estado de la licencia", "example": "Pendiente"}
    ]'::jsonb,
    'license',
    true,
    NOW(), NOW()
)
ON CONFLICT (template_code) DO NOTHING;


-- ── SMS template: LICENSE_GENERATED ──────────────────────────────────────────

INSERT INTO sms_templates (
    template_code,
    name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    variables, category, max_segments, is_active,
    created_at, updated_at
) VALUES (
    'LICENSE_GENERATED',
    'Licencia comercial generada',
    'Licence commerciale générée',
    'Commercial license generated',
    'FACIL: Su licencia comercial {{license_ref}} esta disponible en su panel. Total: {{total_amount}} XAF. Descargue el PDF desde facil.gq',
    'FACIL: Votre licence commerciale {{license_ref}} est disponible. Total: {{total_amount}} XAF. Telechargez le PDF sur facil.gq',
    'FACIL: Your commercial license {{license_ref}} is available. Total: {{total_amount}} XAF. Download the PDF at facil.gq',
    '[
      {"name": "license_ref", "required": true, "description": "Referencia de la licencia"},
      {"name": "total_amount", "required": true, "description": "Total obligaciones en XAF"}
    ]'::jsonb,
    'license',
    1,
    true,
    NOW(), NOW()
)
ON CONFLICT (template_code) DO NOTHING;

COMMIT;
