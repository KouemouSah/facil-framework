/**
 * Hook for fetching category directory
 */

import { useEffect, useState } from 'react';
import {
  getCategoryDirectory,
  getDefaultCategoryDirectory,
  type CategoryDirectory,
} from '@/core/api/homepage';

export function useCategoryDirectory(language: string = 'es') {
  const [directory, setDirectory] = useState<CategoryDirectory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDirectory() {
      try {
        setLoading(true);
        setError(null);
        const data = await getCategoryDirectory(language);
        setDirectory(data);
      } catch (err) {
        console.error('Failed to fetch category directory:', err);
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load category directory';
        setError(errorMessage);
        // Use default/fallback directory on error
        setDirectory(getDefaultCategoryDirectory());
      } finally {
        setLoading(false);
      }
    }

    fetchDirectory();
  }, [language]);

  return { directory, loading, error };
}
