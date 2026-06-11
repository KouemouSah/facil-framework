-- Migration: Add HTML Content to Email Templates
-- Date: 2026-01-23
-- Description: Add actual html_content to email templates (replacing html_file_path references to non-existent files)
-- Following the same structure as SECURITY_PASSWORD_CHANGED template from migration 015

-- =============================================================================
-- PAYMENT TEMPLATES
-- =============================================================================

-- Payment Completed
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago Completado - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #16a34a; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #16a34a; margin: 0; font-size: 24px; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .amount { font-size: 28px; font-weight: bold; color: #16a34a; text-align: center; margin: 20px 0; }
        .details { background-color: #f9fafb; padding: 15px; border-radius: 4px; margin: 20px 0; }
        .details p { margin: 8px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">✅</div>
            <h1>Pago Completado</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu pago ha sido procesado exitosamente.</p>
            <div class="amount">{{amount}} {{currency}}</div>
            <div class="details">
                <p><strong>Número de recibo:</strong> {{receipt_number}}</p>
                <p><strong>Método de pago:</strong> {{payment_method}}</p>
            </div>
            <div class="info-box">
                <p>Puedes descargar tu recibo desde tu panel de control en Facil.</p>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "amount", "description": "Monto del pago", "example": "50,000", "required": true},
    {"name": "currency", "description": "Moneda", "example": "XAF", "required": true},
    {"name": "receipt_number", "description": "Número de recibo", "example": "REC-2026-001234", "required": true},
    {"name": "payment_method", "description": "Método de pago", "example": "BANGE Mobile Money", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'payment_completed';

-- Payment Failed
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago Fallido - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #dc2626; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #dc2626; margin: 0; font-size: 24px; }
        .error-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .warning-box { background-color: #fffbeb; border: 1px solid #f59e0b; border-radius: 4px; padding: 15px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="error-icon">❌</div>
            <h1>Pago Fallido</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Lamentamos informarte que tu pago no pudo ser procesado.</p>
            <div class="info-box">
                <p><strong>Motivo:</strong> {{reason}}</p>
            </div>
            <div class="warning-box">
                <p><strong>¿Qué puedes hacer?</strong></p>
                <ul>
                    <li>Verifica que tienes fondos suficientes</li>
                    <li>Intenta con otro método de pago</li>
                    <li>Contacta a tu banco si el problema persiste</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "reason", "description": "Motivo del fallo", "example": "Fondos insuficientes", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'payment_failed';

-- Payment Cash Pending
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago en Efectivo Pendiente - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #f59e0b; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #f59e0b; margin: 0; font-size: 24px; }
        .pending-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .amount { font-size: 28px; font-weight: bold; color: #f59e0b; text-align: center; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="pending-icon">⏳</div>
            <h1>Pago en Efectivo Pendiente</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Hemos registrado tu intención de pago en efectivo.</p>
            <div class="amount">{{amount}} {{currency}}</div>
            <div class="info-box">
                <p><strong>Próximos pasos:</strong></p>
                <ol>
                    <li>Acude a la oficina correspondiente</li>
                    <li>Presenta tu referencia de pago</li>
                    <li>Realiza el pago en efectivo</li>
                    <li>Un agente validará tu pago</li>
                </ol>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "amount", "description": "Monto del pago", "example": "50,000", "required": true},
    {"name": "currency", "description": "Moneda", "example": "XAF", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'payment_cash_pending';

-- Payment Cash Validated
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago en Efectivo Validado - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #16a34a; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #16a34a; margin: 0; font-size: 24px; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .amount { font-size: 28px; font-weight: bold; color: #16a34a; text-align: center; margin: 20px 0; }
        .details { background-color: #f9fafb; padding: 15px; border-radius: 4px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">✅</div>
            <h1>Pago en Efectivo Validado</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu pago en efectivo ha sido validado por nuestro agente.</p>
            <div class="amount">{{amount}} {{currency}}</div>
            <div class="details">
                <p><strong>Número de recibo:</strong> {{receipt_number}}</p>
            </div>
            <div class="info-box">
                <p>Tu solicitud continuará siendo procesada. Recibirás notificaciones sobre los siguientes pasos.</p>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "amount", "description": "Monto del pago", "example": "50,000", "required": true},
    {"name": "currency", "description": "Moneda", "example": "XAF", "required": true},
    {"name": "receipt_number", "description": "Número de recibo", "example": "REC-2026-001234", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'payment_cash_validated';

-- Payment Cash Rejected
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago en Efectivo Rechazado - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #dc2626; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #dc2626; margin: 0; font-size: 24px; }
        .error-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="error-icon">❌</div>
            <h1>Pago en Efectivo Rechazado</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Lamentamos informarte que tu pago en efectivo de <strong>{{amount}} {{currency}}</strong> ha sido rechazado.</p>
            <div class="info-box">
                <p><strong>Motivo:</strong> {{reason}}</p>
            </div>
            <p>Por favor, contacta con soporte o intenta realizar el pago nuevamente.</p>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "amount", "description": "Monto del pago", "example": "50,000", "required": true},
    {"name": "currency", "description": "Moneda", "example": "XAF", "required": true},
    {"name": "reason", "description": "Motivo del rechazo", "example": "Monto incorrecto", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'payment_cash_rejected';

-- =============================================================================
-- REQUEST TEMPLATES
-- =============================================================================

-- Request Submitted
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Solicitud Recibida - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #2563eb; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #2563eb; margin: 0; font-size: 24px; }
        .info-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #eff6ff; border-left: 4px solid #2563eb; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .details { background-color: #f9fafb; padding: 15px; border-radius: 4px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="info-icon">📋</div>
            <h1>Solicitud Recibida</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Hemos recibido tu solicitud y está siendo procesada.</p>
            <div class="details">
                <p><strong>Referencia:</strong> {{reference}}</p>
                <p><strong>Servicio:</strong> {{service_name}}</p>
            </div>
            <div class="info-box">
                <p><strong>Próximos pasos:</strong></p>
                <ol>
                    <li>Tu solicitud será revisada por un agente</li>
                    <li>Te notificaremos sobre el estado de tu solicitud</li>
                    <li>Si se requieren documentos adicionales, te contactaremos</li>
                </ol>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "reference", "description": "Referencia de la solicitud", "example": "REQ-2026-001234", "required": true},
    {"name": "service_name", "description": "Nombre del servicio", "example": "Certificado de Residencia", "required": false},
    {"name": "workflow_code", "description": "Código del workflow", "example": "RESIDENCIA", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'request_submitted';

-- Request Approved
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Solicitud Aprobada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #16a34a; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #16a34a; margin: 0; font-size: 24px; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .appointment-box { background-color: #eff6ff; border: 2px solid #2563eb; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center; }
        .appointment-box h3 { color: #2563eb; margin: 0 0 15px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">✅</div>
            <h1>Solicitud Aprobada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>¡Excelente noticias! Tu solicitud ha sido aprobada.</p>
            <div class="appointment-box">
                <h3>📅 Detalles de tu Cita</h3>
                <p><strong>Fecha:</strong> {{appointment_date}}</p>
                <p><strong>Hora:</strong> {{appointment_time}}</p>
                <p><strong>Lugar:</strong> {{location}}</p>
            </div>
            <div class="info-box">
                <p><strong>Recuerda traer:</strong></p>
                <ul>
                    <li>Documento de identidad original</li>
                    <li>Esta confirmación de cita</li>
                    <li>Documentos adicionales si fueron solicitados</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "workflow_code", "description": "Código del workflow", "example": "RESIDENCIA", "required": false},
    {"name": "appointment_date", "description": "Fecha de la cita", "example": "25/01/2026", "required": false},
    {"name": "appointment_time", "description": "Hora de la cita", "example": "10:00", "required": false},
    {"name": "location", "description": "Lugar de la cita", "example": "Oficina Central Malabo", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'request_approved';

-- Request Rejected
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Solicitud Rechazada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #dc2626; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #dc2626; margin: 0; font-size: 24px; }
        .error-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .help-box { background-color: #eff6ff; border: 1px solid #2563eb; border-radius: 4px; padding: 15px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="error-icon">❌</div>
            <h1>Solicitud Rechazada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Lamentamos informarte que tu solicitud ha sido rechazada.</p>
            <div class="info-box">
                <p><strong>Motivo del rechazo:</strong></p>
                <p>{{reason}}</p>
            </div>
            <div class="help-box">
                <p><strong>¿Necesitas ayuda?</strong></p>
                <p>Puedes crear una nueva solicitud corrigiendo los problemas indicados o contactar con nuestro soporte.</p>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "workflow_code", "description": "Código del workflow", "example": "RESIDENCIA", "required": false},
    {"name": "reason", "description": "Motivo del rechazo", "example": "Documentos incompletos", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'request_rejected';

-- Request Completed
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Solicitud Completada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #16a34a; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #16a34a; margin: 0; font-size: 24px; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">🎉</div>
            <h1>Solicitud Completada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>¡Felicitaciones! Tu solicitud ha sido completada exitosamente.</p>
            <div class="info-box">
                <p>Tu documento está listo. Puedes descargarlo desde tu panel de control o recogerlo en la oficina correspondiente.</p>
            </div>
            <p>Gracias por usar Facil.</p>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "workflow_code", "description": "Código del workflow", "example": "RESIDENCIA", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'request_completed';

-- Request Cancelled
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Solicitud Cancelada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #6b7280; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #6b7280; margin: 0; font-size: 24px; }
        .cancel-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #f3f4f6; border-left: 4px solid #6b7280; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="cancel-icon">🚫</div>
            <h1>Solicitud Cancelada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu solicitud ha sido cancelada.</p>
            <div class="info-box">
                <p><strong>Motivo:</strong> {{reason}}</p>
            </div>
            <p>Puedes crear una nueva solicitud en cualquier momento desde tu panel de control.</p>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "reason", "description": "Motivo de la cancelación", "example": "Cancelado por el usuario", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'request_cancelled';

-- =============================================================================
-- APPOINTMENT TEMPLATES
-- =============================================================================

-- Appointment Booked
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cita Confirmada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #16a34a; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #16a34a; margin: 0; font-size: 24px; }
        .calendar-icon { font-size: 48px; margin-bottom: 10px; }
        .appointment-box { background-color: #eff6ff; border: 2px solid #2563eb; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center; }
        .appointment-box h3 { color: #2563eb; margin: 0 0 15px 0; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="calendar-icon">📅</div>
            <h1>Cita Confirmada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu cita ha sido confirmada exitosamente.</p>
            <div class="appointment-box">
                <h3>Detalles de tu Cita</h3>
                <p><strong>Fecha:</strong> {{appointment_date}}</p>
                <p><strong>Hora:</strong> {{appointment_time}}</p>
                <p><strong>Lugar:</strong> {{location}}</p>
            </div>
            <div class="info-box">
                <p><strong>Recuerda:</strong></p>
                <ul>
                    <li>Llega 15 minutos antes de tu cita</li>
                    <li>Trae tu documento de identidad</li>
                    <li>Si no puedes asistir, cancela con anticipación</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "appointment_date", "description": "Fecha de la cita", "example": "25/01/2026", "required": true},
    {"name": "appointment_time", "description": "Hora de la cita", "example": "10:00", "required": true},
    {"name": "location", "description": "Lugar de la cita", "example": "Oficina Central Malabo", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'appointment_booked';

-- Appointment Reminder
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recordatorio de Cita - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #f59e0b; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #f59e0b; margin: 0; font-size: 24px; }
        .bell-icon { font-size: 48px; margin-bottom: 10px; }
        .appointment-box { background-color: #fffbeb; border: 2px solid #f59e0b; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center; }
        .appointment-box h3 { color: #f59e0b; margin: 0 0 15px 0; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="bell-icon">🔔</div>
            <h1>Recordatorio de Cita</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Te recordamos que tienes una cita programada para <strong>mañana</strong>.</p>
            <div class="appointment-box">
                <h3>📅 Detalles de tu Cita</h3>
                <p><strong>Fecha:</strong> {{appointment_date}}</p>
                <p><strong>Hora:</strong> {{appointment_time}}</p>
                <p><strong>Lugar:</strong> {{location}}</p>
            </div>
            <div class="info-box">
                <p><strong>Recuerda traer:</strong></p>
                <ul>
                    <li>Documento de identidad original</li>
                    <li>Todos los documentos requeridos</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "appointment_date", "description": "Fecha de la cita", "example": "25/01/2026", "required": true},
    {"name": "appointment_time", "description": "Hora de la cita", "example": "10:00", "required": true},
    {"name": "location", "description": "Lugar de la cita", "example": "Oficina Central Malabo", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'appointment_reminder';

-- Appointment Cancelled
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cita Cancelada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #dc2626; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #dc2626; margin: 0; font-size: 24px; }
        .cancel-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .help-box { background-color: #eff6ff; border: 1px solid #2563eb; border-radius: 4px; padding: 15px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="cancel-icon">❌</div>
            <h1>Cita Cancelada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu cita programada para el <strong>{{appointment_date}} a las {{appointment_time}}</strong> ha sido cancelada.</p>
            <div class="info-box">
                <p><strong>Motivo:</strong> {{reason}}</p>
            </div>
            <div class="help-box">
                <p>Puedes reprogramar tu cita desde tu panel de control o contactar con soporte para más información.</p>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "appointment_date", "description": "Fecha de la cita", "example": "25/01/2026", "required": true},
    {"name": "appointment_time", "description": "Hora de la cita", "example": "10:00", "required": true},
    {"name": "reason", "description": "Motivo de la cancelación", "example": "Cancelado por el usuario", "required": false}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'appointment_cancelled';

-- Appointment Completed
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cita Completada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #16a34a; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #16a34a; margin: 0; font-size: 24px; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">✅</div>
            <h1>Cita Completada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu cita ha sido completada exitosamente.</p>
            <div class="info-box">
                <p>Tu trámite continúa en proceso. Te notificaremos cuando esté listo para recoger.</p>
            </div>
            <p>Gracias por usar Facil.</p>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'appointment_completed';

-- Appointment No Show
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No Asistencia a Cita - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #f59e0b; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #f59e0b; margin: 0; font-size: 24px; }
        .warning-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .help-box { background-color: #eff6ff; border: 1px solid #2563eb; border-radius: 4px; padding: 15px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="warning-icon">⚠️</div>
            <h1>No Asistencia Registrada</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Hemos registrado que no asististe a tu cita programada.</p>
            <div class="info-box">
                <p><strong>Importante:</strong> Tu solicitud ha sido marcada como no asistencia. Esto puede afectar el procesamiento de tu trámite.</p>
            </div>
            <div class="help-box">
                <p><strong>¿Qué puedes hacer?</strong></p>
                <ul>
                    <li>Contacta con soporte para reprogramar tu cita</li>
                    <li>Crea una nueva solicitud si es necesario</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'appointment_no_show';

-- =============================================================================
-- DOCUMENT TEMPLATES
-- =============================================================================

-- Document Validated
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documento Validado - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #16a34a; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #16a34a; margin: 0; font-size: 24px; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">📄✅</div>
            <h1>Documento Validado</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu documento ha sido validado correctamente.</p>
            <div class="info-box">
                <p>Tu solicitud continúa siendo procesada. Te notificaremos sobre los siguientes pasos.</p>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'document_validated';

-- Document Rejected
UPDATE email_templates SET html_content = '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documento Rechazado - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #dc2626; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #dc2626; margin: 0; font-size: 24px; }
        .error-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .help-box { background-color: #eff6ff; border: 1px solid #2563eb; border-radius: 4px; padding: 15px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="error-icon">📄❌</div>
            <h1>Documento Rechazado</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Tu documento ha sido rechazado y necesita ser corregido.</p>
            <div class="info-box">
                <p><strong>Motivo:</strong> {{reason}}</p>
            </div>
            <div class="help-box">
                <p><strong>¿Qué debes hacer?</strong></p>
                <ol>
                    <li>Revisa el motivo del rechazo</li>
                    <li>Prepara un nuevo documento corregido</li>
                    <li>Súbelo desde tu panel de control</li>
                </ol>
            </div>
        </div>
        <div class="footer">
            <p><strong>Facil Platform</strong></p>
            <p>Tramites Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
variables = '[
    {"name": "user_name", "description": "Nombre del usuario", "example": "Juan García", "required": true},
    {"name": "reason", "description": "Motivo del rechazo", "example": "Documento ilegible", "required": true}
]'::jsonb,
updated_at = NOW()
WHERE template_code = 'document_rejected';

-- =============================================================================
-- Clear html_file_path for all templates that now have html_content
-- =============================================================================
UPDATE email_templates
SET html_file_path = NULL
WHERE html_content IS NOT NULL
AND html_file_path IS NOT NULL;
