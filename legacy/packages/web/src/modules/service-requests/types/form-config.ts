/**
 * Form Config Types for Dynamic Wizard
 *
 * These types match the backend FormConfigResponse from
 * GET /service-requests/{request_id}/form-config/{step_id}
 *
 * The form config enables dynamic form rendering without hardcoding
 * field definitions in the frontend.
 *
 * @module service-requests/types/form-config
 * @date 2026-02-05
 */

// =============================================================================
// FIELD TYPES
// =============================================================================

/**
 * Option for select/radio fields - can be a plain string or an object with value + label
 */
export interface FormFieldOption {
  value: string
  label_es: string
}

/**
 * Supported field types for dynamic forms
 */
export type FormFieldType =
  | 'text'
  | 'date'
  | 'select'
  | 'radio'
  | 'checkbox'
  | 'boolean'
  | 'textarea'
  | 'number'
  | 'email'
  | 'tel'

/**
 * Validation rules for a form field
 */
export interface FormFieldValidation {
  minLength?: number
  maxLength?: number
  pattern?: string
  min?: number
  max?: number
  message?: string
}

/**
 * FormField - A field in a form section
 *
 * Note: extraction_path is NOT included - the backend resolves values
 * via workflow.get_form_mapping() and sends them in currentValue.
 */
export interface FormFieldShowWhen {
  /** Field key to watch */
  field: string
  /** Value that triggers visibility */
  value: string
}

export interface FormField {
  /** Unique field identifier (e.g., 'numero_dip', 'apellidos') */
  key: string
  /** Spanish label for display */
  label_es: string
  /** Field type for rendering */
  type: FormFieldType
  /** Whether field is mandatory */
  required: boolean
  /** Options for select/radio fields (string or {value, label_es}) */
  options?: (string | FormFieldOption)[]
  /** Whether field is read-only */
  readonly?: boolean
  /** Placeholder text in Spanish */
  placeholder_es?: string
  /** Validation rules */
  validation?: FormFieldValidation
  /** Helper text displayed below the field */
  help_text_es?: string
  /** Pre-filled value from extraction (already resolved by backend) */
  current_value?: unknown
  /** Conditional visibility: show field only when another field has a specific value */
  show_when?: FormFieldShowWhen
}

// =============================================================================
// SECTION TYPES
// =============================================================================

/**
 * FormSection - A section in a form containing multiple fields
 *
 * Note: condition is NOT included in API response - sections are already
 * filtered by the backend based on context evaluation.
 */
export interface FormSection {
  /** Unique section identifier (e.g., 'personal', 'filiacion') */
  id: string
  /** Spanish title for display */
  title_es: string
  /** Fields in this section */
  fields: FormField[]
  /** Document source for this section (e.g., 'dip', 'certificado_nacimiento') */
  source_document?: string
  /** Optional description in Spanish */
  description_es?: string
}

// =============================================================================
// CONFIG TYPES
// =============================================================================

/**
 * FormConfig - Complete form configuration for a workflow step
 *
 * Only contains sections that passed condition evaluation based on
 * the current request context (solicitud_type, motivo, is_minor, etc.).
 */
export interface FormConfig {
  /** ID of the workflow step (e.g., 'form_review_1', 'form_review_2') */
  step_id: string
  /** Spanish title for the step */
  title_es: string
  /** Optional description in Spanish */
  description_es?: string
  /** Sections to display (already filtered by conditions) */
  sections: FormSection[]
}

// =============================================================================
// API RESPONSE TYPES (matches backend Pydantic models)
// =============================================================================

/**
 * FormFieldResponse - API response format for a field
 */
export interface FormFieldResponse {
  key: string
  label_es: string
  type: string
  required: boolean
  options?: (string | FormFieldOption)[]
  readonly?: boolean
  placeholder_es?: string
  validation?: Record<string, unknown>
  help_text_es?: string
  current_value?: unknown
  show_when?: { field: string; value: string }
}

/**
 * FormSectionResponse - API response format for a section
 */
export interface FormSectionResponse {
  id: string
  title_es: string
  fields: FormFieldResponse[]
  source_document?: string
  description_es?: string
}

/**
 * FormConfigResponse - API response format
 */
export interface FormConfigResponse {
  step_id: string
  title_es: string
  description_es?: string
  sections: FormSectionResponse[]
}

// =============================================================================
// COMPONENT PROPS TYPES
// =============================================================================

/**
 * Props for DynamicField component
 */
export interface DynamicFieldProps {
  field: FormField
  value: unknown
  onChange: (value: unknown) => void
  locale?: 'es' | 'fr' | 'en'
  disabled?: boolean
  error?: string
}

/**
 * Props for DynamicFormRenderer component
 */
export interface DynamicFormRendererProps {
  config: FormConfig
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
  locale?: 'es' | 'fr' | 'en'
  disabled?: boolean
  errors?: Record<string, string>
  /** Optional class name for the container */
  className?: string
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Convert API response to internal FormConfig type
 */
export function parseFormConfigResponse(response: FormConfigResponse): FormConfig {
  return {
    step_id: response.step_id,
    title_es: response.title_es,
    description_es: response.description_es,
    sections: response.sections.map((section) => ({
      id: section.id,
      title_es: section.title_es,
      source_document: section.source_document,
      description_es: section.description_es,
      fields: section.fields.map((field) => ({
        key: field.key,
        label_es: field.label_es,
        type: field.type as FormFieldType,
        required: field.required,
        options: field.options,
        readonly: field.readonly,
        placeholder_es: field.placeholder_es,
        validation: field.validation as FormFieldValidation | undefined,
        help_text_es: field.help_text_es,
        current_value: field.current_value,
        show_when: field.show_when,
      })),
    })),
  }
}

/**
 * Get all field keys from a form config
 */
export function getAllFieldKeys(config: FormConfig): string[] {
  const keys: string[] = []
  for (const section of config.sections) {
    for (const field of section.fields) {
      keys.push(field.key)
    }
  }
  return keys
}

/**
 * Initialize values object from form config
 * Uses current_value from each field if available
 */
export function initializeValuesFromConfig(
  config: FormConfig
): Record<string, unknown> {
  const values: Record<string, unknown> = {}
  for (const section of config.sections) {
    for (const field of section.fields) {
      if (field.current_value !== undefined && field.current_value !== null) {
        values[field.key] = field.current_value
      }
    }
  }
  return values
}

/**
 * Validation messages with i18n support
 */
const VALIDATION_MESSAGES = {
  required: {
    es: 'Este campo es obligatorio',
    fr: 'Ce champ est obligatoire',
    en: 'This field is required',
  },
  minLength: {
    es: (n: number) => `Mínimo ${n} caracteres`,
    fr: (n: number) => `Minimum ${n} caractères`,
    en: (n: number) => `Minimum ${n} characters`,
  },
  maxLength: {
    es: (n: number) => `Máximo ${n} caracteres`,
    fr: (n: number) => `Maximum ${n} caractères`,
    en: (n: number) => `Maximum ${n} characters`,
  },
  pattern: {
    es: 'Formato inválido',
    fr: 'Format invalide',
    en: 'Invalid format',
  },
  min: {
    es: (n: number) => `Valor mínimo: ${n}`,
    fr: (n: number) => `Valeur minimale: ${n}`,
    en: (n: number) => `Minimum value: ${n}`,
  },
  max: {
    es: (n: number) => `Valor máximo: ${n}`,
    fr: (n: number) => `Valeur maximale: ${n}`,
    en: (n: number) => `Maximum value: ${n}`,
  },
}

/**
 * Validate a form config against its validation rules
 * Returns object with field keys mapped to error messages
 *
 * @param config - Form configuration
 * @param values - Current form values
 * @param locale - Locale for error messages (default: 'es')
 */
export function validateFormConfig(
  config: FormConfig,
  values: Record<string, unknown>,
  locale: 'es' | 'fr' | 'en' = 'es'
): Record<string, string> {
  const errors: Record<string, string> = {}

  for (const section of config.sections) {
    for (const field of section.fields) {
      // Skip validation for conditionally hidden fields
      if (field.show_when) {
        const watchValue = values[field.show_when.field]
        if (String(watchValue ?? '') !== field.show_when.value) {
          continue
        }
      }

      const value = values[field.key]

      // Required validation
      if (field.required && (value === undefined || value === null || value === '')) {
        errors[field.key] = VALIDATION_MESSAGES.required[locale]
        continue
      }

      // Skip other validations if value is empty and not required
      if (value === undefined || value === null || value === '') {
        continue
      }

      const validation = field.validation
      if (!validation) continue

      const strValue = String(value)

      // MinLength validation
      if (validation.minLength && strValue.length < validation.minLength) {
        errors[field.key] = validation.message || VALIDATION_MESSAGES.minLength[locale](validation.minLength)
        continue
      }

      // MaxLength validation
      if (validation.maxLength && strValue.length > validation.maxLength) {
        errors[field.key] = validation.message || VALIDATION_MESSAGES.maxLength[locale](validation.maxLength)
        continue
      }

      // Pattern validation
      if (validation.pattern) {
        const regex = new RegExp(validation.pattern)
        if (!regex.test(strValue)) {
          errors[field.key] = validation.message || VALIDATION_MESSAGES.pattern[locale]
          continue
        }
      }

      // Number min/max validation
      if (field.type === 'number') {
        const numValue = Number(value)
        if (validation.min !== undefined && numValue < validation.min) {
          errors[field.key] = validation.message || VALIDATION_MESSAGES.min[locale](validation.min)
          continue
        }
        if (validation.max !== undefined && numValue > validation.max) {
          errors[field.key] = validation.message || VALIDATION_MESSAGES.max[locale](validation.max)
          continue
        }
      }
    }
  }

  return errors
}
