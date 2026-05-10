/**
 * Email Template Starter Templates
 * Pre-designed HTML templates for email creation
 */

export interface StarterTemplate {
  id: string
  name: string
  description: string
  category: string
  preview: string // Thumbnail or short description
  htmlContent: string
}

// Base email wrapper with Facil branding
const baseEmailWrapper = (content: string) => `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Facil</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }
    .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; }
    .header { background-color: #1e40af; padding: 20px; text-align: center; }
    .header h1 { color: #ffffff; margin: 0; font-size: 24px; }
    .content { padding: 30px; }
    .footer { background-color: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #64748b; }
    .button { display: inline-block; background-color: #1e40af; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; }
    .button:hover { background-color: #1e3a8a; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Facil</h1>
    </div>
    <div class="content">
      ${content}
    </div>
    <div class="footer">
      <p>© 2026 Facil - Plataforma Digital AI de Tramites de Guinea Ecuatorial</p>
      <p>Este es un correo automático, por favor no responda a este mensaje.</p>
    </div>
  </div>
</body>
</html>`

export const STARTER_TEMPLATES: StarterTemplate[] = [
  {
    id: 'blank',
    name: 'Plantilla en Blanco',
    description: 'Comienza desde cero con una plantilla vacía',
    category: 'system',
    preview: 'Lienzo en blanco para crear tu propio diseño',
    htmlContent: baseEmailWrapper(`
      <h2>Título del Email</h2>
      <p>Escribe aquí el contenido de tu email...</p>
    `),
  },
  {
    id: 'welcome',
    name: 'Bienvenida',
    description: 'Plantilla para dar la bienvenida a nuevos usuarios',
    category: 'auth',
    preview: 'Email de bienvenida con mensaje personalizado',
    htmlContent: baseEmailWrapper(`
      <h2>¡Bienvenido/a a Facil, {{user_name}}!</h2>
      <p>Nos alegra que te hayas unido a nuestra plataforma de servicios fiscales.</p>
      <p>Con Facil podrás:</p>
      <ul>
        <li>Consultar servicios fiscales disponibles</li>
        <li>Realizar declaraciones de impuestos</li>
        <li>Gestionar tus pagos de manera segura</li>
        <li>Recibir notificaciones importantes</li>
      </ul>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{platform_url}}" class="button">Acceder a la Plataforma</a>
      </p>
      <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'notification',
    name: 'Notificación General',
    description: 'Plantilla para notificaciones generales',
    category: 'notifications',
    preview: 'Notificación con título y mensaje',
    htmlContent: baseEmailWrapper(`
      <h2>{{notification_title}}</h2>
      <p>Estimado/a {{user_name}},</p>
      <p>{{notification_message}}</p>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{action_url}}" class="button">{{action_text}}</a>
      </p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'payment_confirmation',
    name: 'Confirmación de Pago',
    description: 'Confirmar el recibo de un pago',
    category: 'payments',
    preview: 'Confirmación de pago con detalles',
    htmlContent: baseEmailWrapper(`
      <h2>Confirmación de Pago</h2>
      <p>Estimado/a {{user_name}},</p>
      <p>Hemos recibido su pago correctamente. A continuación los detalles:</p>
      <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <tr style="background-color: #f8fafc;">
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Referencia:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{payment_reference}}</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Monto:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{payment_amount}} XAF</td>
        </tr>
        <tr style="background-color: #f8fafc;">
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Fecha:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{payment_date}}</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Concepto:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{payment_concept}}</td>
        </tr>
      </table>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{receipt_url}}" class="button">Ver Recibo</a>
      </p>
      <p>Gracias por utilizar Facil.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'declaration_reminder',
    name: 'Recordatorio de Declaración',
    description: 'Recordar a los usuarios sobre declaraciones pendientes',
    category: 'reminders',
    preview: 'Recordatorio con fecha límite',
    htmlContent: baseEmailWrapper(`
      <h2>Recordatorio: Declaración Pendiente</h2>
      <p>Estimado/a {{user_name}},</p>
      <p>Le recordamos que tiene una declaración pendiente:</p>
      <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0;">
        <strong>{{declaration_type}}</strong><br>
        Fecha límite: <strong>{{deadline_date}}</strong>
      </div>
      <p>Le recomendamos completar su declaración antes de la fecha límite para evitar recargos.</p>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{declaration_url}}" class="button">Completar Declaración</a>
      </p>
      <p>Si ya ha completado esta declaración, puede ignorar este mensaje.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'alert',
    name: 'Alerta Importante',
    description: 'Alertas urgentes para los usuarios',
    category: 'alerts',
    preview: 'Alerta con estilo de urgencia',
    htmlContent: baseEmailWrapper(`
      <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
        <h2 style="color: #dc2626; margin-top: 0;">⚠️ {{alert_title}}</h2>
        <p style="color: #7f1d1d;">{{alert_message}}</p>
      </div>
      <p>Estimado/a {{user_name}},</p>
      <p>{{alert_details}}</p>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{action_url}}" class="button" style="background-color: #dc2626;">{{action_text}}</a>
      </p>
      <p>Si tiene alguna pregunta, contacte con soporte.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'declaration_approved',
    name: 'Declaración Aprobada',
    description: 'Notificar aprobación de declaración',
    category: 'declarations',
    preview: 'Confirmación de aprobación',
    htmlContent: baseEmailWrapper(`
      <div style="background-color: #dcfce7; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 20px; text-align: center;">
        <span style="font-size: 48px;">✅</span>
        <h2 style="color: #16a34a; margin: 10px 0;">Declaración Aprobada</h2>
      </div>
      <p>Estimado/a {{user_name}},</p>
      <p>Nos complace informarle que su declaración ha sido aprobada:</p>
      <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <tr style="background-color: #f8fafc;">
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Tipo:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{declaration_type}}</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Referencia:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{declaration_reference}}</td>
        </tr>
        <tr style="background-color: #f8fafc;">
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Fecha de Aprobación:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{approval_date}}</td>
        </tr>
      </table>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{declaration_url}}" class="button">Ver Detalles</a>
      </p>
      <p>Gracias por cumplir con sus obligaciones fiscales.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'email_verification',
    name: 'Verificación de Email',
    description: 'Código de verificación para confirmar email',
    category: 'auth',
    preview: 'Verificación de correo electrónico',
    htmlContent: baseEmailWrapper(`
      <h2>Verifica tu correo electrónico</h2>
      <p>Hola {{user_name}},</p>
      <p>Para completar tu registro en Facil, utiliza el siguiente código de verificación:</p>
      <div style="background-color: #f8fafc; border: 2px dashed #e2e8f0; border-radius: 8px; padding: 30px; text-align: center; margin: 30px 0;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1e40af;">{{verification_code}}</span>
      </div>
      <p>Este código expira en <strong>15 minutos</strong>.</p>
      <p>Si no solicitaste este código, puedes ignorar este mensaje.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'password_reset',
    name: 'Restablecer Contraseña',
    description: 'Enlace para restablecer la contraseña',
    category: 'auth',
    preview: 'Recuperación de contraseña',
    htmlContent: baseEmailWrapper(`
      <h2>Restablecer Contraseña</h2>
      <p>Hola {{user_name}},</p>
      <p>Hemos recibido una solicitud para restablecer la contraseña de tu cuenta.</p>
      <p style="text-align: center; margin: 30px 0;">
        <a href="{{verification_url}}" class="button">Restablecer Contraseña</a>
      </p>
      <p>Este enlace expira en <strong>1 hora</strong>.</p>
      <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0;">
        <strong>⚠️ Importante:</strong> Si no solicitaste restablecer tu contraseña, ignora este mensaje. Tu contraseña actual seguirá siendo válida.
      </div>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'declaration_rejected',
    name: 'Declaración Rechazada',
    description: 'Notificar rechazo de declaración con motivos',
    category: 'declarations',
    preview: 'Notificación de rechazo',
    htmlContent: baseEmailWrapper(`
      <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; margin-bottom: 20px; text-align: center;">
        <span style="font-size: 48px;">❌</span>
        <h2 style="color: #dc2626; margin: 10px 0;">Declaración Rechazada</h2>
      </div>
      <p>Estimado/a {{user_name}},</p>
      <p>Lamentamos informarle que su declaración ha sido rechazada:</p>
      <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <tr style="background-color: #f8fafc;">
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Tipo:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{declaration_type}}</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Referencia:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{declaration_reference}}</td>
        </tr>
      </table>
      <div style="background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0;">
        <strong>Motivo del rechazo:</strong><br>
        {{alert_details}}
      </div>
      <p>Por favor, corrija los errores indicados y vuelva a enviar su declaración.</p>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{declaration_url}}" class="button">Corregir Declaración</a>
      </p>
      <p>Si tiene preguntas, contacte con nuestro equipo de soporte.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'two_factor_enabled',
    name: '2FA Activado',
    description: 'Confirmación de activación de autenticación de dos factores',
    category: 'auth',
    preview: 'Confirmación de seguridad 2FA',
    htmlContent: baseEmailWrapper(`
      <div style="background-color: #dcfce7; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 20px; text-align: center;">
        <span style="font-size: 48px;">🔐</span>
        <h2 style="color: #16a34a; margin: 10px 0;">2FA Activado Correctamente</h2>
      </div>
      <p>Hola {{user_name}},</p>
      <p>La autenticación de dos factores (2FA) ha sido activada en tu cuenta de Facil.</p>
      <p>A partir de ahora, necesitarás tu aplicación de autenticación para iniciar sesión.</p>
      <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin: 20px 0;">
        <strong>Consejos de seguridad:</strong>
        <ul style="margin: 10px 0 0 0; padding-left: 20px;">
          <li>Guarda tus códigos de respaldo en un lugar seguro</li>
          <li>No compartas tu código de verificación con nadie</li>
          <li>Si pierdes acceso a tu aplicación, usa los códigos de respaldo</li>
        </ul>
      </div>
      <p>Si no realizaste este cambio, contacta inmediatamente con soporte.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'payment_failed',
    name: 'Pago Fallido',
    description: 'Notificar fallo en el procesamiento del pago',
    category: 'payments',
    preview: 'Notificación de pago fallido',
    htmlContent: baseEmailWrapper(`
      <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; margin-bottom: 20px; text-align: center;">
        <span style="font-size: 48px;">💳</span>
        <h2 style="color: #dc2626; margin: 10px 0;">Pago No Procesado</h2>
      </div>
      <p>Estimado/a {{user_name}},</p>
      <p>No pudimos procesar su pago. Detalles del intento:</p>
      <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <tr style="background-color: #f8fafc;">
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Referencia:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{payment_reference}}</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Monto:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{payment_amount}} XAF</td>
        </tr>
        <tr style="background-color: #f8fafc;">
          <td style="padding: 10px; border: 1px solid #e2e8f0;"><strong>Fecha:</strong></td>
          <td style="padding: 10px; border: 1px solid #e2e8f0;">{{payment_date}}</td>
        </tr>
      </table>
      <p>Posibles causas:</p>
      <ul>
        <li>Saldo insuficiente</li>
        <li>Datos de pago incorrectos</li>
        <li>Límite de transacciones alcanzado</li>
      </ul>
      <p style="text-align: center; margin-top: 30px;">
        <a href="{{action_url}}" class="button">Reintentar Pago</a>
      </p>
      <p>Si necesita ayuda, contacte con soporte.</p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
  {
    id: 'account_suspended',
    name: 'Cuenta Suspendida',
    description: 'Notificar suspensión de cuenta',
    category: 'system',
    preview: 'Notificación de suspensión',
    htmlContent: baseEmailWrapper(`
      <div style="background-color: #fef3c7; border: 1px solid #fde68a; border-radius: 8px; padding: 20px; margin-bottom: 20px; text-align: center;">
        <span style="font-size: 48px;">⚠️</span>
        <h2 style="color: #b45309; margin: 10px 0;">Cuenta Suspendida</h2>
      </div>
      <p>Estimado/a {{user_name}},</p>
      <p>Le informamos que su cuenta de Facil ha sido suspendida temporalmente.</p>
      <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0;">
        <strong>Motivo:</strong><br>
        {{alert_details}}
      </div>
      <p>Para reactivar su cuenta, por favor contacte con nuestro equipo de soporte proporcionando la documentación necesaria.</p>
      <p style="text-align: center; margin-top: 30px;">
        <a href="mailto:{{support_email}}" class="button">Contactar Soporte</a>
      </p>
      <p>Saludos cordiales,<br><strong>Equipo Facil</strong></p>
    `),
  },
]

export default STARTER_TEMPLATES
