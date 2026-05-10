/**
 * Homepage Module - Hooks
 *
 * React Query hooks for cached data fetching:
 * - Homepage statistics
 * - Category/ministry directories
 * - Service search
 * - Service details
 *
 * All hooks use staleTime/gcTime for optimal caching performance.
 *
 * @module homepage/hooks
 * @date 2026-01-25
 */

// Legacy hooks (for backwards compatibility)
export { useHomepageStats } from './useHomepageStats';
export { useCategoryDirectory } from './useCategoryDirectory';

// New React Query hooks with caching
export {
  useHomepageStats as useHomepageStatsQuery,
  useCategoryDirectory as useCategoryDirectoryQuery,
  useMinistryDirectory,
  useMinistryDetails,
  useServicesByType,
  usePrefetchHomepageData,
  usePrefetchMinistryDetails,
  useInvalidateHomepageCache,
  homepageQueryKeys,
} from './useHomepageData';

export {
  useServiceSearch,
  useDebouncedSearch,
  usePrefetchSearch,
  useInvalidateSearchCache,
  searchQueryKeys,
} from './useServiceSearch';

export {
  useServiceDetails,
  usePrefetchServiceDetails,
  useInvalidateServiceDetails,
  serviceDetailsQueryKeys,
} from './useServiceDetails';
