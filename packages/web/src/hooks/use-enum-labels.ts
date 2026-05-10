/**
 * useEnumLabels Hook
 *
 * Hybrid hook for ENUM translations that:
 * 1. Uses existing JSON translations (from "Traducciones Sistema", fast & offline)
 * 2. Falls back to API for NEW values added via "Sistema ENUMs" admin interface
 * 3. Auto-formats as last resort if no translation found
 *
 * Priority: JSON (existing) -> API (new values) -> Auto-format
 *
 * This enables support for new ENUM values added via admin interface
 * while using fast, offline JSON translations for existing values.
 *
 * @module hooks
 * @author Claude Code
 * @date 2025-12-11
 */

'use client'

import { useCallback, useMemo } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import { enumManagementApi } from '@/modules/translations/services/api'
import type {
  ModifiableEnumType,
  EnumValuesResponse,
  LanguageCode,
} from '@/modules/translations/types'

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Convert snake_case to camelCase for JSON key lookup
 * Example: "dgi_agent" -> "dgiAgent"
 */
function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

/**
 * Mapping from ENUM names to their JSON translation namespace paths
 */
const ENUM_TO_JSON_NAMESPACE: Record<string, { namespace: string; prefix: string }> = {
  user_role_enum: { namespace: 'admin', prefix: 'userRoles' },
  declaration_status_enum: { namespace: 'admin', prefix: 'declarationStatuses' },
  payment_status_enum: { namespace: 'admin', prefix: 'paymentStatuses' },
  document_status_enum: { namespace: 'admin', prefix: 'documentStatuses' },
  service_type_enum: { namespace: 'admin', prefix: 'serviceTypes' },
  calculation_method_enum: { namespace: 'admin', prefix: 'calculationMethods' },
}

/**
 * Static list of known ENUM values (used when API is unavailable)
 * These are the default values that exist in the database
 * Source: DATABASE_SCHEMA_REFERENCE.md
 */
const KNOWN_ENUM_VALUES: Record<string, string[]> = {
  // Updated per migration 048 (unified agent roles)
  user_role_enum: [
    'citizen',
    'business',
    'accountant',
    'admin',
    'agent',
    'funcionario',
  ],
  // From DATABASE_SCHEMA_REFERENCE.md lines 142-148
  declaration_status_enum: [
    'draft',
    'submitted',
    'processing',
    'accepted',
    'rejected',
    'amended',
  ],
  // From DATABASE_SCHEMA_REFERENCE.md lines 203-209
  payment_status_enum: [
    'pending',
    'processing',
    'completed',
    'failed',
    'refunded',
    'cancelled',
  ],
  // Document status (common values used in the system)
  document_status_enum: [
    'pending',
    'uploaded',
    'verified',
    'rejected',
  ],
  // From DATABASE_SCHEMA_REFERENCE.md lines 257-265
  service_type_enum: [
    'document_processing',
    'license_permit',
    'residence_permit',
    'registration_fee',
    'inspection_fee',
    'administrative_tax',
    'customs_duty',
    'declaration_tax',
  ],
  // From DATABASE_SCHEMA_REFERENCE.md lines 126-134
  calculation_method_enum: [
    'fixed_expedition',
    'fixed_renewal',
    'fixed_both',
    'percentage_based',
    'unit_based',
    'tiered_rates',
    'formula_based',
    'fixed_plus_unit',
  ],
}

// =============================================================================
// Types
// =============================================================================

interface EnumLabelMap {
  [value: string]: string
}

interface UseEnumLabelsOptions {
  /**
   * Enable API loading (default: true)
   * Set to false to use only static JSON translations
   */
  enableApi?: boolean
  /**
   * Stale time in milliseconds (default: 5 minutes)
   */
  staleTime?: number
}

interface UseEnumLabelsReturn {
  /**
   * Get translated label for an ENUM value
   */
  getLabel: (enumName: ModifiableEnumType | string, value: string) => string
  /**
   * Get all values for an ENUM as options array
   */
  getOptions: (
    enumName: ModifiableEnumType | string,
    includeAll?: boolean
  ) => Array<{ value: string; label: string }>
  /**
   * Check if API data is loading
   */
  isLoading: boolean
  /**
   * Check if API data is available
   */
  hasApiData: boolean
}

// =============================================================================
// Query Keys
// =============================================================================

const ENUM_LABELS_KEY = ['enum-labels-cache'] as const

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook to get ENUM labels with API + JSON fallback
 *
 * Usage:
 * ```tsx
 * const { getLabel, getOptions } = useEnumLabels()
 *
 * // Get single label
 * const roleLabel = getLabel('user_role_enum', 'admin')
 *
 * // Get options for select/dropdown
 * const roleOptions = getOptions('user_role_enum')
 * ```
 */
export function useEnumLabels(options: UseEnumLabelsOptions = {}): UseEnumLabelsReturn {
  const { enableApi = true, staleTime = 5 * 60 * 1000 } = options // 5 min default

  const locale = useLocale() as LanguageCode

  // Load JSON translations as fallback
  const tAdmin = useTranslations('admin')

  // ==========================================================================
  // API Query - Load all modifiable ENUMs with translations
  // ==========================================================================

  const enumsToLoad: ModifiableEnumType[] = [
    'user_role_enum',
    'declaration_status_enum',
    'payment_status_enum',
    'document_status_enum',
    'service_type_enum',
    'calculation_method_enum',
  ]

  // Load all ENUM values from API
  const { data: apiEnumData, isLoading } = useQuery({
    queryKey: [...ENUM_LABELS_KEY, locale],
    queryFn: async () => {
      const results: Record<string, EnumValuesResponse> = {}

      // Load all ENUMs in parallel
      const promises = enumsToLoad.map(async (enumName) => {
        try {
          const data = await enumManagementApi.getEnumValues(enumName, locale)
          results[enumName] = data
        } catch (error) {
          console.warn(`Failed to load ENUM ${enumName}:`, error)
        }
      })

      await Promise.all(promises)
      return results
    },
    enabled: enableApi,
    staleTime,
    gcTime: 30 * 60 * 1000, // 30 min cache
    retry: 1,
    refetchOnWindowFocus: false,
  })

  const hasApiData = !!apiEnumData && Object.keys(apiEnumData).length > 0

  // ==========================================================================
  // Build Label Maps
  // ==========================================================================

  const apiLabelMaps = useMemo(() => {
    if (!apiEnumData) return {}

    const maps: Record<string, EnumLabelMap> = {}

    for (const [enumName, response] of Object.entries(apiEnumData)) {
      maps[enumName] = {}
      for (const valueInfo of response.values) {
        // Use translation based on locale, fallback to display_value
        const translation = valueInfo[locale] || valueInfo.display_value
        maps[enumName][valueInfo.value] = translation
        // Also map display_value for convenience
        maps[enumName][valueInfo.display_value] = translation
      }
    }

    return maps
  }, [apiEnumData, locale])

  // ==========================================================================
  // JSON Fallback Function (uses existing translations from messages/*.json)
  // ==========================================================================

  /**
   * Get label from JSON translations as fallback
   * Uses the mapping ENUM_TO_JSON_NAMESPACE to find the correct translation key
   */
  const getJsonFallbackLabel = useCallback(
    (enumName: string, value: string): string | null => {
      const mapping = ENUM_TO_JSON_NAMESPACE[enumName]
      if (!mapping) return null

      // Convert snake_case value to camelCase for JSON key lookup
      const camelCaseValue = snakeToCamel(value)

      // Build the translation key: e.g., "userRoles.citizen" or "userRoles.dgiAgent"
      const translationKey = `${mapping.prefix}.${camelCaseValue}`

      try {
        // Use tAdmin since all ENUMs are currently in the 'admin' namespace
        const translation = tAdmin(translationKey as Parameters<typeof tAdmin>[0])
        // If translation returns the key itself, it means it wasn't found
        if (translation === translationKey || translation.includes('.')) {
          return null
        }
        return translation
      } catch {
        return null
      }
    },
    [tAdmin]
  )

  // ==========================================================================
  // Label Getter
  // ==========================================================================

  const getLabel = useCallback(
    (enumName: ModifiableEnumType | string, value: string): string => {
      // 1. Try JSON translations first (existing translations in messages/*.json - fast & offline)
      const jsonLabel = getJsonFallbackLabel(enumName, value)
      if (jsonLabel) return jsonLabel

      // 2. Try API data for NEW values (added via "Sistema ENUMs" admin interface)
      if (hasApiData && apiLabelMaps[enumName]) {
        const apiLabel = apiLabelMaps[enumName][value]
        if (apiLabel) return apiLabel
      }

      // 3. Return formatted value as last resort
      return value.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
    },
    [getJsonFallbackLabel, hasApiData, apiLabelMaps]
  )

  // ==========================================================================
  // Options Getter
  // ==========================================================================

  // "All" label by locale
  const allLabel = useMemo(() => {
    const labels: Record<LanguageCode, string> = {
      es: 'Todos',
      fr: 'Tous',
      en: 'All',
    }
    return labels[locale] || labels.es
  }, [locale])

  const getOptions = useCallback(
    (
      enumName: ModifiableEnumType | string,
      includeAll = false
    ): Array<{ value: string; label: string }> => {
      const options: Array<{ value: string; label: string }> = []

      if (includeAll) {
        options.push({ value: 'all', label: allLabel })
      }

      // 1. Use API data if available (includes new values from admin)
      if (hasApiData && apiEnumData?.[enumName]) {
        for (const valueInfo of apiEnumData[enumName].values) {
          // Skip archived values
          if (valueInfo.is_archived) continue

          const label = valueInfo[locale] || valueInfo.display_value
          options.push({
            value: valueInfo.value,
            label,
          })
        }
        return options
      }

      // 2. Fallback to known values list + JSON translations
      const knownValues = KNOWN_ENUM_VALUES[enumName]
      if (knownValues) {
        for (const value of knownValues) {
          options.push({
            value,
            label: getLabel(enumName, value),
          })
        }
      }

      return options
    },
    [hasApiData, apiEnumData, locale, allLabel, getLabel]
  )

  return {
    getLabel,
    getOptions,
    isLoading,
    hasApiData,
  }
}

// =============================================================================
// Specialized Hooks (Convenience Wrappers)
// =============================================================================

/**
 * Hook specifically for user role labels
 */
export function useUserRoleLabels() {
  const { getLabel, getOptions, isLoading } = useEnumLabels()

  return {
    getRoleLabel: (role: string) => getLabel('user_role_enum', role),
    getRoleOptions: (includeAll = false) => getOptions('user_role_enum', includeAll),
    isLoading,
  }
}

/**
 * Hook specifically for declaration status labels
 */
export function useDeclarationStatusLabels() {
  const { getLabel, getOptions, isLoading } = useEnumLabels()

  return {
    getStatusLabel: (status: string) => getLabel('declaration_status_enum', status),
    getStatusOptions: (includeAll = false) => getOptions('declaration_status_enum', includeAll),
    isLoading,
  }
}

/**
 * Hook specifically for payment status labels
 */
export function usePaymentStatusLabels() {
  const { getLabel, getOptions, isLoading } = useEnumLabels()

  return {
    getStatusLabel: (status: string) => getLabel('payment_status_enum', status),
    getStatusOptions: (includeAll = false) => getOptions('payment_status_enum', includeAll),
    isLoading,
  }
}

/**
 * Hook specifically for document status labels
 */
export function useDocumentStatusLabels() {
  const { getLabel, getOptions, isLoading } = useEnumLabels()

  return {
    getStatusLabel: (status: string) => getLabel('document_status_enum', status),
    getStatusOptions: (includeAll = false) => getOptions('document_status_enum', includeAll),
    isLoading,
  }
}

/**
 * Hook specifically for service type labels
 */
export function useServiceTypeLabels() {
  const { getLabel, getOptions, isLoading } = useEnumLabels()

  return {
    getTypeLabel: (type: string) => getLabel('service_type_enum', type),
    getTypeOptions: (includeAll = false) => getOptions('service_type_enum', includeAll),
    isLoading,
  }
}

/**
 * Hook specifically for calculation method labels
 */
export function useCalculationMethodLabels() {
  const { getLabel, getOptions, isLoading } = useEnumLabels()

  return {
    getMethodLabel: (method: string) => getLabel('calculation_method_enum', method),
    getMethodOptions: (includeAll = false) => getOptions('calculation_method_enum', includeAll),
    isLoading,
  }
}

export default useEnumLabels
