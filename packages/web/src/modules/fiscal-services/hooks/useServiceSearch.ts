/**
 * Hook for searching fiscal services
 */

import { useState, useCallback } from 'react';
import {
  searchServices,
  getDefaultSearchResponse,
  type SearchFilters,
  type SearchResponse,
} from '@/core/api/services';

export function useServiceSearch() {
  const [results, setResults] = useState<SearchResponse>(getDefaultSearchResponse());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (filters: SearchFilters = {}) => {
    try {
      setLoading(true);
      setError(null);
      const data = await searchServices(filters);
      setResults(data);
    } catch (err) {
      console.error('Failed to search services:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to search services';
      setError(errorMessage);
      // Use default/fallback response on error
      setResults(getDefaultSearchResponse());
    } finally {
      setLoading(false);
    }
  }, []);

  return { results, loading, error, search };
}
