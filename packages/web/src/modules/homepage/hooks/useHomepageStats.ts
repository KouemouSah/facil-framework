/**
 * Hook for fetching homepage statistics
 */

import { useEffect, useState } from 'react';
import {
  getHomepageStats,
  getDefaultStats,
  type HomepageStats,
} from '@/core/api/homepage';

export function useHomepageStats() {
  const [stats, setStats] = useState<HomepageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStats() {
      try {
        setLoading(true);
        setError(null);
        const data = await getHomepageStats();
        setStats(data);
      } catch (err) {
        console.error('Failed to fetch homepage stats:', err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to load statistics';
        setError(errorMessage);
        // Use default/fallback stats on error
        setStats(getDefaultStats());
      } finally {
        setLoading(false);
      }
    }

    fetchStats();
  }, []);

  return { stats, loading, error };
}
