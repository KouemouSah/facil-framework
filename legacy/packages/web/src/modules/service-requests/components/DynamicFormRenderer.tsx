/**
 * DynamicFormRenderer Component
 *
 * Renders a complete form with sections and fields based on
 * configuration fetched from the backend API.
 *
 * This component replaces hardcoded field definitions with dynamic
 * configuration, enabling a single component for all workflow forms.
 *
 * @module service-requests/components/DynamicFormRenderer
 * @date 2026-02-05
 */

'use client'

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getLocalizedField } from '@/core/utils/i18n-helpers'
import { DynamicField } from './DynamicField'
import type {
  DynamicFormRendererProps,
  FormSection,
} from '../types/form-config'

/**
 * Document labels with i18n support
 */
const DOCUMENT_LABELS: Record<string, Record<string, string>> = {
  dip: { es: 'DIP', fr: 'DIP', en: 'DIP' },
  certificado_nacimiento: { es: 'Certificado de Nacimiento', fr: 'Acte de naissance', en: 'Birth Certificate' },
  pasaporte_antiguo: { es: 'Pasaporte Anterior', fr: 'Ancien Passeport', en: 'Previous Passport' },
  denuncia_policial: { es: 'Denuncia Policial', fr: 'Déclaration de police', en: 'Police Report' },
  libro_familia: { es: 'Libro de Familia', fr: 'Livret de famille', en: 'Family Book' },
  foto_pasaporte: { es: 'Foto de Pasaporte', fr: 'Photo de Passeport', en: 'Passport Photo' },
}

/**
 * Get document icon/badge for a section with locale support
 */
function getDocumentBadge(documentCode: string | undefined, locale: 'es' | 'fr' | 'en' = 'es') {
  if (!documentCode) return null

  const labelMap = DOCUMENT_LABELS[documentCode]
  const label = labelMap?.[locale] || labelMap?.es || documentCode

  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
      <FileText className="h-3 w-3" />
      {label}
    </span>
  )
}

/**
 * Render a single form section with its fields
 */
function FormSectionCard({
  section,
  values,
  onChange,
  locale,
  disabled,
  errors,
}: {
  section: FormSection
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
  locale: 'es' | 'fr' | 'en'
  disabled: boolean
  errors?: Record<string, string>
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{getLocalizedField(section as unknown as Record<string, unknown>, 'title', locale)}</CardTitle>
          {getDocumentBadge(section.source_document, locale)}
        </div>
        {getLocalizedField(section as unknown as Record<string, unknown>, 'description', locale) && (
          <CardDescription>{getLocalizedField(section as unknown as Record<string, unknown>, 'description', locale)}</CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2">
          {section.fields.map((field) => {
            // Conditional visibility: hide field when show_when condition is not met
            if (field.show_when) {
              const watchValue = String(values[field.show_when.field] ?? '')
              if (watchValue !== field.show_when.value) {
                return null
              }
            }

            return (
              <div
                key={field.key}
                className={cn(
                  // Full width for textarea
                  field.type === 'textarea' && 'sm:col-span-2'
                )}
              >
                <DynamicField
                  field={field}
                  value={values[field.key] ?? field.current_value}
                  onChange={(value) => onChange(field.key, value)}
                  locale={locale}
                  disabled={disabled}
                  error={errors?.[field.key]}
                />
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Loading skeleton for form sections
 */
function FormSkeleton() {
  return (
    <div className="space-y-6">
      {[1, 2].map((i) => (
        <Card key={i}>
          <CardHeader className="pb-3">
            <Skeleton className="h-6 w-48" />
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2">
              {[1, 2, 3, 4].map((j) => (
                <div key={j} className="space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

/**
 * Empty state messages with i18n support
 */
const EMPTY_STATE_MESSAGES: Record<string, string> = {
  es: 'No hay campos para mostrar en este paso.',
  fr: 'Aucun champ à afficher pour cette étape.',
  en: 'No fields to display for this step.',
}

/**
 * Empty state when no sections are returned
 */
function EmptyState({ message, locale = 'es' }: { message?: string; locale?: 'es' | 'fr' | 'en' }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
        <p className="text-muted-foreground">
          {message || EMPTY_STATE_MESSAGES[locale] || EMPTY_STATE_MESSAGES.es}
        </p>
      </CardContent>
    </Card>
  )
}

/**
 * DynamicFormRenderer - Main component for rendering dynamic forms
 *
 * @example
 * ```tsx
 * const { data: formConfig, isLoading } = useFormConfig(requestId, 'form_review_2');
 * const [values, setValues] = useState<Record<string, unknown>>({});
 *
 * if (isLoading) return <DynamicFormRenderer.Skeleton />;
 *
 * return (
 *   <DynamicFormRenderer
 *     config={formConfig}
 *     values={values}
 *     onChange={(key, value) => setValues(prev => ({ ...prev, [key]: value }))}
 *     locale="es"
 *   />
 * );
 * ```
 */
export function DynamicFormRenderer({
  config,
  values,
  onChange,
  locale = 'es',
  disabled = false,
  errors,
  className,
}: DynamicFormRendererProps) {
  // Handle empty config
  if (!config || !config.sections || config.sections.length === 0) {
    return <EmptyState locale={locale} />
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Optional form title */}
      {getLocalizedField(config as unknown as Record<string, unknown>, 'title', locale) && (
        <div className="mb-4">
          <h2 className="text-xl font-semibold">{getLocalizedField(config as unknown as Record<string, unknown>, 'title', locale)}</h2>
          {getLocalizedField(config as unknown as Record<string, unknown>, 'description', locale) && (
            <p className="text-muted-foreground mt-1">{getLocalizedField(config as unknown as Record<string, unknown>, 'description', locale)}</p>
          )}
        </div>
      )}

      {/* Render sections */}
      {config.sections.map((section) => (
        <FormSectionCard
          key={section.id}
          section={section}
          values={values}
          onChange={onChange}
          locale={locale}
          disabled={disabled}
          errors={errors}
        />
      ))}
    </div>
  )
}

// Attach sub-components for convenient access
DynamicFormRenderer.Skeleton = FormSkeleton
DynamicFormRenderer.Empty = EmptyState

export default DynamicFormRenderer
