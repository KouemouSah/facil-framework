/**
 * Email Template Variables
 * Predefined variables grouped by context for email template creation
 */

import type { TemplateVariable } from '../types'

// =============================================================================
// VARIABLE CONTEXT GROUPS
// =============================================================================

export type VariableContext =
  | 'user'
  | 'payment'
  | 'declaration'
  | 'system'
  | 'notification'
  | 'alert'

export interface VariableGroup {
  context: VariableContext
  labelKey: string  // Translation key
  variables: TemplateVariable[]
}

// =============================================================================
// PREDEFINED VARIABLES
// =============================================================================

export const VARIABLE_GROUPS: VariableGroup[] = [
  {
    context: 'user',
    labelKey: 'variableGroups.user',
    variables: [
      {
        name: 'user_name',
        description: 'Nombre completo del usuario',
        example: 'Juan García López',
        required: true,
      },
      {
        name: 'user_email',
        description: 'Correo electrónico del usuario',
        example: 'usuario@ejemplo.com',
        required: false,
      },
      {
        name: 'user_phone',
        description: 'Número de teléfono del usuario',
        example: '+240 222 123 456',
        required: false,
      },
      {
        name: 'user_tax_id',
        description: 'NIF/NIE del usuario',
        example: 'GQ123456789',
        required: false,
      },
    ],
  },
  {
    context: 'payment',
    labelKey: 'variableGroups.payment',
    variables: [
      {
        name: 'payment_amount',
        description: 'Monto del pago',
        example: '150,000',
        required: true,
      },
      {
        name: 'payment_reference',
        description: 'Referencia del pago',
        example: 'PAY-2024-001234',
        required: true,
      },
      {
        name: 'payment_date',
        description: 'Fecha del pago',
        example: '20/12/2024',
        required: true,
      },
      {
        name: 'payment_concept',
        description: 'Concepto del pago',
        example: 'Impuesto sobre la Renta',
        required: false,
      },
      {
        name: 'receipt_url',
        description: 'URL para descargar el recibo',
        example: 'https://taxasge.emacsah.com/recibos/12345',
        required: false,
      },
    ],
  },
  {
    context: 'declaration',
    labelKey: 'variableGroups.declaration',
    variables: [
      {
        name: 'declaration_type',
        description: 'Tipo de declaración',
        example: 'Declaración de IVA',
        required: true,
      },
      {
        name: 'declaration_reference',
        description: 'Referencia de la declaración',
        example: 'DEC-2024-005678',
        required: true,
      },
      {
        name: 'deadline_date',
        description: 'Fecha límite de presentación',
        example: '31/12/2024',
        required: false,
      },
      {
        name: 'approval_date',
        description: 'Fecha de aprobación',
        example: '15/12/2024',
        required: false,
      },
      {
        name: 'declaration_url',
        description: 'URL para ver la declaración',
        example: 'https://taxasge.emacsah.com/declaraciones/12345',
        required: false,
      },
    ],
  },
  {
    context: 'system',
    labelKey: 'variableGroups.system',
    variables: [
      {
        name: 'platform_url',
        description: 'URL de la plataforma Facil',
        example: 'https://taxasge.emacsah.com',
        required: false,
      },
      {
        name: 'support_email',
        description: 'Email de soporte',
        example: 'soporte@emacsah.com',
        required: false,
      },
      {
        name: 'current_year',
        description: 'Año actual',
        example: '2024',
        required: false,
      },
      {
        name: 'verification_code',
        description: 'Código de verificación',
        example: '123456',
        required: false,
      },
      {
        name: 'verification_url',
        description: 'URL de verificación',
        example: 'https://taxasge.emacsah.com/verify/abc123',
        required: false,
      },
    ],
  },
  {
    context: 'notification',
    labelKey: 'variableGroups.notification',
    variables: [
      {
        name: 'notification_title',
        description: 'Título de la notificación',
        example: 'Actualización importante',
        required: true,
      },
      {
        name: 'notification_message',
        description: 'Mensaje de la notificación',
        example: 'Su declaración ha sido procesada.',
        required: true,
      },
      {
        name: 'action_url',
        description: 'URL de la acción principal',
        example: 'https://taxasge.emacsah.com/accion',
        required: false,
      },
      {
        name: 'action_text',
        description: 'Texto del botón de acción',
        example: 'Ver detalles',
        required: false,
      },
    ],
  },
  {
    context: 'alert',
    labelKey: 'variableGroups.alert',
    variables: [
      {
        name: 'alert_title',
        description: 'Título de la alerta',
        example: 'Acción requerida',
        required: true,
      },
      {
        name: 'alert_message',
        description: 'Mensaje corto de la alerta',
        example: 'Su cuenta requiere verificación',
        required: true,
      },
      {
        name: 'alert_details',
        description: 'Detalles adicionales de la alerta',
        example: 'Por favor complete la verificación antes del 31/12/2024',
        required: false,
      },
    ],
  },
]

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Get all predefined variables as a flat list
 */
export function getAllPredefinedVariables(): TemplateVariable[] {
  return VARIABLE_GROUPS.flatMap(group => group.variables)
}

/**
 * Get variable by name from predefined list
 */
export function getPredefinedVariable(name: string): TemplateVariable | undefined {
  return getAllPredefinedVariables().find(v => v.name === name)
}

/**
 * Check if a variable name is predefined
 */
export function isPredefinedVariable(name: string): boolean {
  return getAllPredefinedVariables().some(v => v.name === name)
}

export default VARIABLE_GROUPS
