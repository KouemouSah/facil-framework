/**
 * Fiscal Services Types — aligned with backend FiscalServiceResponse + ServiceDetailsResponse
 */

export interface FiscalServiceItem {
  id: number;
  service_code: string;
  name: string;
  name_es: string;
  description?: string;
  description_es?: string;
  service_type: string;
  calculation_method: string;
  category_name?: string;
  ministry_name?: string;
  sector_name?: string;
  tasa_expedicion?: number;
  expedition_price?: number;
  tasa_renovacion?: number;
  renewal_price?: number;
  view_count: number;
  calculation_count: number;
  status: string;
  processing_time_days?: number;
  workflow_code?: string;
}

export interface FiscalServiceListResponse {
  services: FiscalServiceItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ServiceSearchFilters {
  q?: string;
  category_id?: number;
  ministry_id?: number;
  service_type?: string;
  min_price?: number;
  max_price?: number;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  limit?: number;
  language?: string;
  include_facets?: boolean;
}

export interface FacetItem {
  value: string;
  label: string;
  count: number;
}

export interface SearchFacets {
  categories: FacetItem[];
  ministries: FacetItem[];
  service_types: FacetItem[];
  price_ranges: FacetItem[];
}

export interface ServiceSearchResult {
  id: number;
  service_code: string;
  name: string;
  description?: string;
  service_type: string;
  category?: string;
  ministry?: string;
  calculation_method: string;
  expedition_price: number;
  renewal_price: number;
  view_count: number;
  calculation_count: number;
  relevance_score?: number;
}

/**
 * Search response — from POST /homepage/search (public, translated).
 * Uses 'results' (not 'services') and 'total_results' (not 'total').
 */
export interface ServiceSearchResponse {
  results: FiscalServiceItem[];
  services?: FiscalServiceItem[];
  total_results: number;
  total: number;
  page: number;
  limit: number;
  page_size?: number;
  total_pages: number;
  facets?: SearchFacets;
}

export interface MinistryItem {
  id: number;
  ministry_code: string;
  name_es: string;
  description_es?: string;
  icon?: string;
  color?: string;
  is_active?: boolean;
  service_count?: number;
}

export interface CategoryItem {
  id: number;
  category_code: string;
  name_es: string;
  description_es?: string;
  icon?: string;
  color?: string;
}

export interface PricingInfo {
  expedition_price: number;
  renewal_price: number;
  calculation_method: string;
  percentage_rate?: number;
  unit_price?: number;
  validity_period_months?: number;
  renewal_frequency_months?: number;
  currency: string;
}

export interface DocumentDetailItem {
  id: number;
  template_code: string;
  name: string;
  description?: string;
  document_type: string;
  max_size_mb: number;
  accepted_formats: string[];
}

export interface ProcedureStepItem {
  id: number;
  step_number: number;
  title: string;
  description?: string;
  estimated_minutes: number;
}

export interface ProcedureDetailItem {
  id: number;
  template_code: string;
  name: string;
  description?: string;
  category?: string;
  applies_to?: string;
  display_order: number;
  steps: ProcedureStepItem[];
  total_estimated_minutes: number;
}

export interface RelatedServiceItem {
  id: number;
  service_code: string;
  name: string;
  expedition_price?: number;
  renewal_price?: number;
}

export interface ServiceDetail {
  id: number;
  service_code: string;
  name: string;
  description?: string;
  service_type: string;
  status: string;
  pricing: PricingInfo;
  processing_time_days?: number;
  legal_reference?: string;
  notes?: string;
  category?: { id: number; category_code: string; name: string; description?: string; icon?: string; color?: string };
  sector?: { id: number; code: string; name: string; description?: string };
  ministry?: { id: number; code: string; name: string; description?: string };
  documents: DocumentDetailItem[];
  documents_count: number;
  procedures: ProcedureDetailItem[];
  procedures_count: number;
  total_procedure_steps: number;
  related_services: RelatedServiceItem[];
  parent_service?: RelatedServiceItem;
  child_services: RelatedServiceItem[];
  view_count: number;
  calculation_count: number;
  last_updated?: string;
  has_documents: boolean;
  has_procedures: boolean;
  is_free: boolean;
  requires_renewal: boolean;
}
