/**
 * Service Details API Client
 * Fetches complete service information with documents, procedures, and related data
 */

import { appConfig } from '@/core/config/app';

// Use homepage endpoint as workaround while fiscal-services router is being fixed
const API_URL = `${appConfig.api.baseUrl}/api/${appConfig.api.version}/homepage`;

// ===================================================================================================
// TYPES
// ===================================================================================================

export interface DocumentDetailItem {
  id: number;
  template_code: string;
  name: string;
  description: string | null;
  category: string | null;
  validity_duration_months: number | null;
  validity_notes: string | null;
  is_required_expedition: boolean;
  is_required_renewal: boolean;
  display_order: number;
  custom_notes: string | null;
}

export interface ProcedureStepDetailItem {
  id: number;
  step_number: number;
  description: string;
  instructions: string | null;
  estimated_duration_minutes: number | null;
  location_address: string | null;
  office_hours: string | null;
  requires_appointment: boolean;
  is_optional: boolean;
}

export interface ProcedureDetailItem {
  id: number;
  template_code: string;
  name: string;
  description: string | null;
  category: string | null;
  applies_to: string | null;
  display_order: number;
  custom_notes: string | null;
  steps: ProcedureStepDetailItem[];
  total_estimated_minutes: number;
}

export interface CategoryDetailItem {
  id: number;
  category_code: string;
  name: string;
  description: string | null;
  icon: string | null;
  color: string | null;
}

export interface SectorDetailItem {
  id: number;
  code: string;
  name: string;
  description: string | null;
}

export interface MinistryDetailItem {
  id: number;
  code: string;
  name: string;
  description: string | null;
}

// Variable configuration for formula-based calculations
export interface VariableConfig {
  type: 'number' | 'currency';
  label_es?: string;
  label_fr?: string;
  label_en?: string;
  description_es?: string;
  description_fr?: string;
  description_en?: string;
  default_value?: number;
  min?: number;
  max?: number;
}

// Calculation config for complex formulas
export interface CalculationConfig {
  variables?: Record<string, VariableConfig>;
  formula?: string;
  formula_description_es?: string;
  formula_description_fr?: string;
  formula_description_en?: string;
}

export interface PricingInfo {
  expedition_price: number;
  renewal_price: number;
  calculation_method: string;
  percentage_rate: number | null;
  unit_price: number | null;
  validity_period_months: number | null;
  renewal_frequency_months: number | null;
  calculation_config?: CalculationConfig | null;
  currency: string;
}

export interface RelatedServiceItem {
  id: number;
  service_code: string;
  name: string;
  expedition_price: number;
  processing_time_days: number | null;
}

export interface KeywordItem {
  keyword: string;
  language_code: string;
  weight: number;
}

export interface ServiceDetailsResponse {
  // Basic identification
  id: number;
  service_code: string;

  // Core information
  name: string;
  description: string | null;

  // Classification
  service_type: string;
  status: string;

  // Pricing
  pricing: PricingInfo;

  // Processing
  processing_time_days: number | null;
  legal_reference: string | null;
  notes: string | null;

  // Hierarchy
  category: CategoryDetailItem | null;
  sector: SectorDetailItem | null;
  ministry: MinistryDetailItem | null;

  // Required Documents
  documents: DocumentDetailItem[];
  documents_count: number;

  // Procedures
  procedures: ProcedureDetailItem[];
  procedures_count: number;
  total_procedure_steps: number;

  // Related Services
  related_services: RelatedServiceItem[];
  parent_service: RelatedServiceItem | null;
  child_services: RelatedServiceItem[];

  // Keywords
  keywords: KeywordItem[];

  // Metadata
  view_count: number;
  calculation_count: number;
  last_updated: string | null;

  // Computed fields
  has_documents: boolean;
  has_procedures: boolean;
  is_free: boolean;
  requires_renewal: boolean;
}

// ===================================================================================================
// API FUNCTIONS
// ===================================================================================================

/**
 * Get complete service details
 */
export async function getServiceDetails(
  serviceId: number,
  language: string = 'es',
  _includeRelated: boolean = true,
  _includeKeywords: boolean = false
): Promise<ServiceDetailsResponse> {
  try {
    const params = new URLSearchParams({
      language,
    });

    // Using homepage/service/{id} endpoint as workaround
    const response = await fetch(`${API_URL}/service/${serviceId}?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to fetch service details: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching service details:', error);
    throw error;
  }
}

/**
 * Format price for display
 */
export function formatPrice(price: number, currency: string = 'XAF', locale: string = 'es'): string {
  if (price === 0) {
    const freeLabels: Record<string, string> = { es: 'Gratuito', fr: 'Gratuit', en: 'Free' }
    return freeLabels[locale] || freeLabels['es']
  }

  const intlLocale = locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ'
  return new Intl.NumberFormat(intlLocale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price);
}

/**
 * Format duration in minutes to human readable
 */
export function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (remainingMinutes === 0) {
    return `${hours}h`;
  }

  return `${hours}h ${remainingMinutes}min`;
}

/**
 * Get service type label
 */
export function getServiceTypeLabel(type: string, locale: string = 'es'): string {
  const labels: Record<string, Record<string, string>> = {
    es: {
      document_processing: 'Tramitación de documentos',
      license_permit: 'Licencia/Permiso',
      residence_permit: 'Permiso de residencia',
      registration_fee: 'Tasa de registro',
      inspection_fee: 'Tasa de inspección',
      administrative_tax: 'Impuesto administrativo',
      customs_duty: 'Arancel aduanero',
      declaration_tax: 'Impuesto declarativo',
    },
    fr: {
      document_processing: 'Traitement de documents',
      license_permit: 'Licence/Permis',
      residence_permit: 'Permis de séjour',
      registration_fee: 'Frais d\'inscription',
      inspection_fee: 'Frais d\'inspection',
      administrative_tax: 'Taxe administrative',
      customs_duty: 'Droit de douane',
      declaration_tax: 'Taxe déclarative',
    },
    en: {
      document_processing: 'Document Processing',
      license_permit: 'License/Permit',
      residence_permit: 'Residence Permit',
      registration_fee: 'Registration Fee',
      inspection_fee: 'Inspection Fee',
      administrative_tax: 'Administrative Tax',
      customs_duty: 'Customs Duty',
      declaration_tax: 'Declaration Tax',
    },
  };

  return labels[locale]?.[type] || labels['es'][type] || type;
}

/**
 * Get calculation method label
 */
export function getCalculationMethodLabel(method: string, locale: string = 'es'): string {
  const labels: Record<string, Record<string, string>> = {
    es: {
      fixed_expedition: 'Tarifa fija (expedición)',
      fixed_renewal: 'Tarifa fija (renovación)',
      fixed_both: 'Tarifa fija',
      percentage_based: 'Basado en porcentaje',
      unit_based: 'Por unidad',
      tiered_rates: 'Tarifas progresivas',
      formula_based: 'Fórmula personalizada',
      fixed_plus_unit: 'Base + por unidad',
    },
    fr: {
      fixed_expedition: 'Tarif fixe (expédition)',
      fixed_renewal: 'Tarif fixe (renouvellement)',
      fixed_both: 'Tarif fixe',
      percentage_based: 'Basé sur pourcentage',
      unit_based: 'Par unité',
      tiered_rates: 'Tarifs progressifs',
      formula_based: 'Formule personnalisée',
      fixed_plus_unit: 'Base + par unité',
    },
    en: {
      fixed_expedition: 'Fixed rate (expedition)',
      fixed_renewal: 'Fixed rate (renewal)',
      fixed_both: 'Fixed rate',
      percentage_based: 'Percentage based',
      unit_based: 'Unit based',
      tiered_rates: 'Tiered rates',
      formula_based: 'Custom formula',
      fixed_plus_unit: 'Base + per unit',
    },
  };

  return labels[locale]?.[method] || labels['es'][method] || method;
}
