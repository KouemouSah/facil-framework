/**
 * DynamicField Component
 *
 * Renders a form field based on its type configuration.
 * Supports: text, date, select, radio, checkbox, textarea, number, email, tel
 *
 * @module service-requests/components/DynamicField
 * @date 2026-02-05
 */

'use client'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { DynamicFieldProps, FormField, FormFieldOption } from '../types/form-config'

/**
 * Get the appropriate label for the current locale
 * TODO: Backend currently only sends Spanish labels
 * When backend adds label_fr/label_en, update this function
 */
function getLabel(field: FormField, locale: string = 'es'): string {
  // NOTE: Backend only sends label_es currently
  // This is a placeholder for future i18n support
  // When backend adds label_fr/label_en to FormField, use:
  // return field[`label_${locale}`] || field.label_es
  void locale // Suppress unused warning, will be used when i18n is added
  return field.label_es
}

/**
 * Get placeholder for the current locale
 * TODO: Backend currently only sends Spanish placeholders
 */
function getPlaceholder(field: FormField, locale: string = 'es'): string | undefined {
  void locale // Suppress unused warning
  return field.placeholder_es
}

/**
 * Warning messages for unknown field types - i18n
 */
const UNKNOWN_TYPE_WARNINGS: Record<string, string> = {
  es: 'Tipo de campo desconocido, usando texto por defecto',
  fr: 'Type de champ inconnu, utilisation du texte par défaut',
  en: 'Unknown field type, falling back to text',
}

/**
 * Normalize option to extract value and display label.
 * Handles both string options ("M") and object options ({value: "TURISMO", label_es: "Turismo"}).
 */
function getOptionValue(option: string | FormFieldOption): string {
  return typeof option === 'string' ? option : option.value
}

function getOptionLabel(option: string | FormFieldOption): string {
  return typeof option === 'string' ? option : option.label_es
}

/**
 * DynamicField - Renders a single form field based on its type
 */
export function DynamicField({
  field,
  value,
  onChange,
  locale = 'es',
  disabled = false,
  error,
}: DynamicFieldProps) {
  const label = getLabel(field, locale)
  const placeholder = getPlaceholder(field, locale)
  const isReadonly = field.readonly || disabled
  const fieldId = `field-${field.key}`

  // Highlight required empty fields with amber border (before validation)
  const isRequiredEmpty = field.required && !isReadonly && !value && value !== 0 && !error

  // Common label component
  const FieldLabel = () => (
    <Label
      htmlFor={fieldId}
      className={cn(
        'text-sm font-medium',
        field.required && "after:content-['*'] after:ml-0.5 after:text-red-500"
      )}
    >
      {label}
    </Label>
  )

  // Error message component
  const ErrorMessage = () =>
    error ? (
      <p className="text-sm text-red-500 mt-1">{error}</p>
    ) : null

  // Help text component
  const HelpText = () =>
    field.help_text_es && !error ? (
      <p className="text-xs text-muted-foreground mt-1">{field.help_text_es}</p>
    ) : null

  // Render based on field type
  switch (field.type) {
    case 'text':
    case 'email':
    case 'tel':
    case 'number':
      return (
        <div className="space-y-2">
          <FieldLabel />
          <Input
            id={fieldId}
            type={field.type}
            value={(value as string) ?? ''}
            onChange={(e) => onChange(e.target.value)}
            readOnly={isReadonly}
            disabled={disabled}
            placeholder={placeholder}
            className={cn(
              isReadonly && 'bg-muted cursor-not-allowed',
              error && 'border-red-500 focus-visible:ring-red-500',
              isRequiredEmpty && 'border-amber-400 bg-amber-50/50'
            )}
            aria-invalid={!!error}
            aria-describedby={error ? `${fieldId}-error` : undefined}
          />
          <ErrorMessage />
          <HelpText />
        </div>
      )

    case 'date':
      return (
        <div className="space-y-2">
          <FieldLabel />
          <Input
            id={fieldId}
            type="date"
            value={(value as string) ?? ''}
            onChange={(e) => onChange(e.target.value)}
            readOnly={isReadonly}
            disabled={disabled}
            className={cn(
              isReadonly && 'bg-muted cursor-not-allowed',
              error && 'border-red-500 focus-visible:ring-red-500',
              isRequiredEmpty && 'border-amber-400 bg-amber-50/50'
            )}
            aria-invalid={!!error}
          />
          <ErrorMessage />
          <HelpText />
        </div>
      )

    case 'textarea':
      return (
        <div className="space-y-2">
          <FieldLabel />
          <Textarea
            id={fieldId}
            value={(value as string) ?? ''}
            onChange={(e) => onChange(e.target.value)}
            readOnly={isReadonly}
            disabled={disabled}
            placeholder={placeholder}
            rows={3}
            className={cn(
              isReadonly && 'bg-muted cursor-not-allowed',
              error && 'border-red-500 focus-visible:ring-red-500',
              isRequiredEmpty && 'border-amber-400 bg-amber-50/50'
            )}
            aria-invalid={!!error}
          />
          <ErrorMessage />
          <HelpText />
        </div>
      )

    case 'select':
      return (
        <div className="space-y-2">
          <FieldLabel />
          <Select
            value={(value as string) ?? ''}
            onValueChange={onChange}
            disabled={isReadonly}
          >
            <SelectTrigger
              id={fieldId}
              className={cn(
                isReadonly && 'bg-muted cursor-not-allowed',
                error && 'border-red-500 focus-visible:ring-red-500',
                isRequiredEmpty && 'border-amber-400 bg-amber-50/50'
              )}
              aria-invalid={!!error}
            >
              <SelectValue placeholder={placeholder || 'Seleccione...'} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => {
                const val = getOptionValue(option)
                const label = getOptionLabel(option)
                return (
                  <SelectItem key={val} value={val}>
                    {label}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
          <ErrorMessage />
          <HelpText />
        </div>
      )

    case 'radio':
      return (
        <div className="space-y-2">
          <FieldLabel />
          <RadioGroup
            value={(value as string) ?? ''}
            onValueChange={onChange}
            disabled={isReadonly}
            className="flex flex-col space-y-2"
          >
            {field.options?.map((option) => {
              const val = getOptionValue(option)
              const label = getOptionLabel(option)
              return (
                <div key={val} className="flex items-center space-x-2">
                  <RadioGroupItem
                    value={val}
                    id={`${fieldId}-${val}`}
                    disabled={isReadonly}
                  />
                  <Label
                    htmlFor={`${fieldId}-${val}`}
                    className={cn(
                      'text-sm font-normal',
                      isReadonly && 'cursor-not-allowed text-muted-foreground'
                    )}
                  >
                    {label}
                  </Label>
                </div>
              )
            })}
          </RadioGroup>
          <ErrorMessage />
          <HelpText />
        </div>
      )

    case 'checkbox':
      return (
        <div className="flex items-start space-x-2">
          <Checkbox
            id={fieldId}
            checked={(value as boolean) ?? false}
            onCheckedChange={onChange}
            disabled={isReadonly}
            className={cn(error && 'border-red-500')}
            aria-invalid={!!error}
          />
          <div className="space-y-1">
            <Label
              htmlFor={fieldId}
              className={cn(
                'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
                field.required && "after:content-['*'] after:ml-0.5 after:text-red-500"
              )}
            >
              {label}
            </Label>
            <ErrorMessage />
            <HelpText />
          </div>
        </div>
      )

    default:
      // Fallback to text input for unknown types
      console.warn(`[DynamicField] ${UNKNOWN_TYPE_WARNINGS[locale] || UNKNOWN_TYPE_WARNINGS.en}: ${field.type}`)
      return (
        <div className="space-y-2">
          <FieldLabel />
          <Input
            id={fieldId}
            type="text"
            value={(value as string) ?? ''}
            onChange={(e) => onChange(e.target.value)}
            readOnly={isReadonly}
            disabled={disabled}
            placeholder={placeholder}
            className={cn(
              isReadonly && 'bg-muted cursor-not-allowed',
              error && 'border-red-500 focus-visible:ring-red-500',
              isRequiredEmpty && 'border-amber-400 bg-amber-50/50'
            )}
          />
          <ErrorMessage />
          <HelpText />
        </div>
      )
  }
}

export default DynamicField
