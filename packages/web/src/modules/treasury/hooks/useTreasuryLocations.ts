/**
 * Hook for treasury entity locations (for site filter dropdowns)
 *
 * @module treasury/hooks
 */

import { useQuery } from '@tanstack/react-query';
import apiClient from '@/core/api/client';

export interface TreasuryLocation {
  id: string;
  location_name: string;
  city: string;
}

export function useTreasuryLocations() {
  return useQuery<TreasuryLocation[]>({
    queryKey: ['treasury', 'locations'],
    queryFn: async () => {
      const res = await apiClient.get<TreasuryLocation[]>(
        '/admin/service-requests/treasury/locations'
      );
      return res.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export default useTreasuryLocations;
