/**
 * Services API Client - PostgreSQL-based search
 * Connects to /api/v1/homepage/search endpoint
 */

import { appConfig } from '@/core/config/app';

// Use homepage endpoint which is always available (fiscal-services router has issues)
const SERVICES_API_URL = `${appConfig.api.baseUrl}/api/${appConfig.api.version}/homepage`;

// ===================================================================================================
// TYPES
// ===================================================================================================

export interface SearchFilters {
  // Search
  q?: string;

  // Filters
  category_id?: number;
  category_code?: string;
  ministry_id?: number;
  service_type?: string;
  min_price?: number;
  max_price?: number;
  min_expedition_price?: number;
  max_expedition_price?: number;
  min_renewal_price?: number;
  max_renewal_price?: number;
  calculation_methods?: string[];

  // Sorting
  sort_by?: 'relevance' | 'name' | 'price' | 'popular';
  sort_order?: 'asc' | 'desc';

  // Pagination
  page?: number;
  limit?: number;

  // Options
  include_facets?: boolean;
  language?: string;
}

export interface ServiceResult {
  id: number;
  name: string;
  description: string | null;
  category_name: string;
  ministry_name: string | null;
  sector_name: string | null;
  service_type: string;
  expedition_price: number;
  renewal_price: number;
  processing_time_days: number;
  status: string;
  calculation_method: string;
  // Note: service_code is NOT included (as per requirements)
}

export interface FacetItem {
  id?: number;
  code?: string;
  name?: string;
  type?: string;
  range?: string;
  count: number;
  min?: number;
  max?: number;
}

export interface SearchFacets {
  categories: FacetItem[];
  ministries: FacetItem[];
  service_types: FacetItem[];
  price_ranges: FacetItem[];
}

export interface BundleResult {
  id: string;
  name: string;
  description: string | null;
  bundle_code: string;
  commerce_type: string;
  item_count: number;
}

export interface AutocompleteItem {
  id: number;
  name: string;
  category_name: string;
  service_type: string;
  expedition_price: number;
}

export interface SearchResponse {
  success: boolean;
  query: string;
  total_results: number;
  page: number;
  limit: number;
  total_pages: number;
  results: ServiceResult[];
  bundles: BundleResult[];
  facets: SearchFacets | null;
  suggestions: string[];
  execution_time_ms: number;
  cached: boolean;
}

export interface SemanticResult {
  id: number;
  name: string;
  description: string | null;
  category_name: string;
  ministry_name: string | null;
  service_type: string;
  expedition_price: number;
  renewal_price: number;
  similarity: number;
}

export interface SemanticSearchResponse {
  success: boolean;
  query: string;
  results: SemanticResult[];
  total_results: number;
  execution_time_ms: number;
  embedding_model: string;
  cached: boolean;
}

// ===================================================================================================
// API FUNCTIONS
// ===================================================================================================

/**
 * Search fiscal services with filters
 */
export async function searchServices(filters: SearchFilters = {}): Promise<SearchResponse> {
  try {
    // Default values
    const payload = {
      q: filters.q || null,
      category_id: filters.category_id || null,
      category_code: filters.category_code || null,
      ministry_id: filters.ministry_id || null,
      service_type: filters.service_type || null,
      min_price: filters.min_price !== undefined ? filters.min_price : null,
      max_price: filters.max_price !== undefined ? filters.max_price : null,
      min_expedition_price:
        filters.min_expedition_price !== undefined ? filters.min_expedition_price : null,
      max_expedition_price:
        filters.max_expedition_price !== undefined ? filters.max_expedition_price : null,
      min_renewal_price: filters.min_renewal_price !== undefined ? filters.min_renewal_price : null,
      max_renewal_price: filters.max_renewal_price !== undefined ? filters.max_renewal_price : null,
      calculation_methods: filters.calculation_methods || null,
      sort_by: filters.sort_by || 'relevance',
      sort_order: filters.sort_order || 'asc',
      page: filters.page || 1,
      limit: filters.limit || 20,
      include_facets: filters.include_facets !== false, // true by default
      language: filters.language || 'es',
    };

    const response = await fetch(`${SERVICES_API_URL}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Search failed: ${response.statusText}`);
    }

    const data: SearchResponse = await response.json();
    return data;
  } catch (error) {
    console.error('Search services error:', error);

    // Return fallback response
    return getDefaultSearchResponse();
  }
}

/**
 * Autocomplete suggestions (type-ahead, debounce 200-300ms)
 */
export async function autocompleteServices(
  q: string,
  language: string = 'es',
  limit: number = 7
): Promise<AutocompleteItem[]> {
  if (!q || q.trim().length < 2) return [];

  try {
    const params = new URLSearchParams({ q: q.trim(), language, limit: String(limit) });
    const response = await fetch(`${SERVICES_API_URL}/autocomplete?${params}`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.suggestions || [];
  } catch {
    return [];
  }
}

/**
 * Semantic search — understands meaning, not just keywords
 */
export async function semanticSearchServices(
  q: string,
  language: string = 'es',
  limit: number = 10
): Promise<SemanticSearchResponse> {
  if (!q || q.trim().length < 2) {
    return { success: false, query: q, results: [], total_results: 0, execution_time_ms: 0, embedding_model: '', cached: false };
  }

  try {
    const params = new URLSearchParams({ q: q.trim(), language, limit: String(limit) });
    const response = await fetch(`${SERVICES_API_URL}/search/semantic?${params}`);
    if (!response.ok) {
      return { success: false, query: q, results: [], total_results: 0, execution_time_ms: 0, embedding_model: '', cached: false };
    }
    return await response.json();
  } catch {
    return { success: false, query: q, results: [], total_results: 0, execution_time_ms: 0, embedding_model: '', cached: false };
  }
}

/**
 * Get default/fallback search response for error cases
 */
export function getDefaultSearchResponse(): SearchResponse {
  return {
    success: false,
    query: '',
    total_results: 0,
    page: 1,
    limit: 20,
    total_pages: 0,
    results: [],
    bundles: [],
    facets: {
      categories: [],
      ministries: [],
      service_types: [],
      price_ranges: [],
    },
    suggestions: [
      'permiso de construcción',
      'licencia comercial',
      'registro de empresa',
    ],
    execution_time_ms: 0,
    cached: false,
  };
}

/**
 * Format price for display (XAF currency)
 */
export function formatPrice(price: number, freeLabel: string = 'Gratuito', locale: string = 'es'): string {
  if (price === 0) {
    return freeLabel;
  }

  return new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'es-ES', {
    style: 'currency',
    currency: 'XAF',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price);
}

/**
 * Get price range label
 */
export function getPriceRangeLabel(range: string, translations?: Record<string, string>): string {
  if (translations && translations[range]) {
    return translations[range];
  }

  const labels: Record<string, string> = {
    free: 'Gratuito',
    low: '< 50.000 XAF',
    medium: '50.000 - 200.000 XAF',
    high: '200.000 - 500.000 XAF',
    very_high: '> 500.000 XAF',
  };

  return labels[range] || range;
}

/**
 * Get service type label (Spanish)
 */
export function getServiceTypeLabel(type: string, translations?: Record<string, string>): string {
  if (translations && translations[type]) {
    return translations[type];
  }

  const labels: Record<string, string> = {
    administrative: 'Administrativo',
    fiscal: 'Fiscal',
    legal: 'Legal',
    customs: 'Aduanas',
    mining: 'Minería',
    commercial: 'Comercial',
    social: 'Social',
    transport: 'Transporte',
    agriculture: 'Agricultura',
    health: 'Salud',
    education: 'Educación',
    other: 'Otro',
  };

  return labels[type] || type;
}
