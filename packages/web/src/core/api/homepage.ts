/**
 * Homepage API Client
 * Provides functions to fetch dynamic homepage data from backend
 */

import apiClient from './client';

// ============================================================================
// COLD-START TOLERANCE — public homepage endpoints retry on timeout
// ============================================================================
// Cloud Run scales to zero on staging during low-traffic windows. The first
// hit after idle takes 5-15s to boot (Python imports + DB pool warmup +
// migrations check). With the default axios timeout of 30s, a single in-
// flight request that races the cold start can fail outright. Public
// homepage endpoints are read-only, idempotent, and safe to retry.
const PUBLIC_TIMEOUT_MS = 45_000; // 45s tolerates a typical cold start
const PUBLIC_RETRY_DELAYS = [2_000, 5_000]; // 2s, then 5s — total budget ~52s

function isTimeoutError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const e = error as { code?: string; message?: string };
  return e.code === 'ECONNABORTED' || (e.message?.includes('timeout') ?? false);
}

async function withRetryOnTimeout<T>(
  attempt: () => Promise<T>,
  delays: number[] = PUBLIC_RETRY_DELAYS
): Promise<T> {
  let lastError: unknown;
  // First try + retries: delays.length + 1 total attempts
  for (let i = 0; i <= delays.length; i++) {
    try {
      return await attempt();
    } catch (err) {
      lastError = err;
      if (i >= delays.length || !isTimeoutError(err)) {
        throw err; // non-timeout error or budget exhausted
      }
      await new Promise(resolve => setTimeout(resolve, delays[i]));
    }
  }
  throw lastError;
}

/**
 * Homepage statistics response
 */
export interface HomepageStats {
  total_services: number;
  total_ministries: number;
  total_categories: number;
  total_sectors: number;
  last_updated: string;
}

/**
 * Category with service count
 */
export interface CategoryWithServices {
  id: number;
  category_code: string;
  name_es: string;
  name_fr?: string;
  name_en?: string;
  description_es: string | null;
  description_fr?: string | null;
  description_en?: string | null;
  icon: string | null;
  color: string | null;
  service_count: number;
  ministry_name: string | null;
  sector_name: string | null;
}

/**
 * Category directory response
 */
export interface CategoryDirectory {
  total_categories: number;
  total_services: number;
  categories: CategoryWithServices[];
  last_updated: string;
}

/**
 * API Error response
 */
export interface ApiError {
  detail: string;
  status?: number;
}

/**
 * Fetch homepage statistics
 * Returns dynamic counts of services, ministries, categories, and sectors
 *
 * @throws {Error} If the API request fails
 */
export async function getHomepageStats(): Promise<HomepageStats> {
  try {
    const response = await withRetryOnTimeout(() =>
      apiClient.get<HomepageStats>('/homepage/stats', { timeout: PUBLIC_TIMEOUT_MS })
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching homepage stats:', error);

    // Type-safe error handling
    let errorMessage = 'Failed to fetch homepage statistics';
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      errorMessage = axiosError.response?.data?.detail || axiosError.message || errorMessage;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
}

/**
 * Fetch category directory with service counts
 * Returns categories sorted by service count (descending)
 *
 * @param language - Language code (es, fr, en). Default: 'es'
 * @throws {Error} If the API request fails
 */
export async function getCategoryDirectory(language: string = 'es'): Promise<CategoryDirectory> {
  try {
    const response = await apiClient.get<CategoryDirectory>('/homepage/categories', {
      params: { language },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching category directory:', error);

    // Type-safe error handling
    let errorMessage = 'Failed to fetch category directory';
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      errorMessage = axiosError.response?.data?.detail || axiosError.message || errorMessage;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
}

/**
 * Get default/fallback stats (used when API fails)
 */
export function getDefaultStats(): HomepageStats {
  return {
    total_services: 0,
    total_ministries: 0,
    total_categories: 0,
    total_sectors: 0,
    last_updated: new Date().toISOString(),
  };
}

/**
 * Get default/fallback category directory (used when API fails)
 */
export function getDefaultCategoryDirectory(): CategoryDirectory {
  return {
    total_categories: 0,
    total_services: 0,
    categories: [],
    last_updated: new Date().toISOString(),
  };
}

/**
 * Service type enum values
 */
export type ServiceType =
  | 'document_processing'
  | 'license_permit'
  | 'residence_permit'
  | 'registration_fee'
  | 'inspection_fee'
  | 'administrative_tax'
  | 'customs_duty'
  | 'declaration_tax';

/**
 * Service details for services-by-type endpoint
 */
export interface ServiceByType {
  id: number;
  service_code: string;
  name_es: string;
  name_fr?: string | null;
  name_en?: string | null;
  tasa_expedicion?: number | null;
}

/**
 * Response for services grouped by type and letter
 */
export interface ServicesByTypeResponse {
  type: string;
  letter?: string | null;
  services: ServiceByType[];
  total: number;
  has_more: boolean;
}

/**
 * Fetch services filtered by service type and optionally by first letter
 *
 * @param type - Service type filter
 * @param options - Optional query parameters
 * @throws {Error} If the API request fails
 */
export async function getServicesByType(
  type: ServiceType,
  options?: {
    letter?: string;
    language?: string;
    limit?: number;
  }
): Promise<ServicesByTypeResponse> {
  try {
    const response = await withRetryOnTimeout(() =>
      apiClient.get<ServicesByTypeResponse>('/homepage/services-by-type', {
        params: {
          type,
          letter: options?.letter,
          language: options?.language || 'es',
          limit: options?.limit || 10,
        },
        timeout: PUBLIC_TIMEOUT_MS,
      })
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching services by type:', error);

    // Type-safe error handling
    let errorMessage = 'Failed to fetch services by type';
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      errorMessage = axiosError.response?.data?.detail || axiosError.message || errorMessage;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
}

/**
 * Get default/fallback services by type response (used when API fails)
 */
export function getDefaultServicesByType(type: ServiceType): ServicesByTypeResponse {
  return {
    type,
    letter: null,
    services: [],
    total: 0,
    has_more: false,
  };
}

// ============================================================================
// MINISTRY TYPES AND FUNCTIONS
// ============================================================================

/**
 * Ministry item with service counts
 */
export interface MinistryItem {
  id: number;
  ministry_code: string;
  name: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  is_active: boolean;
  service_count: number;
  sector_count: number;
  category_count: number;
}

/**
 * Ministry directory response
 */
export interface MinistryDirectory {
  total_ministries: number;
  total_services: number;
  ministries: MinistryItem[];
}

/**
 * Ministry service item
 */
export interface MinistryServiceItem {
  id: number;
  service_code: string;
  name: string;
  description: string | null;
  expedition_price: number;
  renewal_price: number;
  category_name: string | null;
  sector_name: string | null;
  service_type: string;
}

/**
 * Ministry details response with paginated services
 */
export interface MinistryDetails {
  id: number;
  ministry_code: string;
  name: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  is_active: boolean;
  service_count: number;
  sector_count: number;
  category_count: number;
  services: MinistryServiceItem[];
  total_pages: number;
  current_page: number;
}

/**
 * Fetch ministry directory with service counts
 *
 * @param language - Language code (es, fr, en). Default: 'es'
 * @throws {Error} If the API request fails
 */
export async function getMinistryDirectory(language: string = 'es'): Promise<MinistryDirectory> {
  try {
    const response = await apiClient.get<MinistryDirectory>('/homepage/ministries', {
      params: { language },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching ministry directory:', error);

    let errorMessage = 'Failed to fetch ministry directory';
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      errorMessage = axiosError.response?.data?.detail || axiosError.message || errorMessage;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
}

/**
 * Fetch ministry details with paginated services
 *
 * @param ministryId - Ministry ID
 * @param options - Optional query parameters
 * @throws {Error} If the API request fails
 */
export async function getMinistryDetails(
  ministryId: number,
  options?: {
    language?: string;
    page?: number;
    limit?: number;
  }
): Promise<MinistryDetails> {
  try {
    const response = await apiClient.get<MinistryDetails>(`/homepage/ministry/${ministryId}`, {
      params: {
        language: options?.language || 'es',
        page: options?.page || 1,
        limit: options?.limit || 12,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching ministry details:', error);

    let errorMessage = 'Failed to fetch ministry details';
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      errorMessage = axiosError.response?.data?.detail || axiosError.message || errorMessage;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
}

/**
 * Get default/fallback ministry directory (used when API fails)
 */
export function getDefaultMinistryDirectory(): MinistryDirectory {
  return {
    total_ministries: 0,
    total_services: 0,
    ministries: [],
  };
}
