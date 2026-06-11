/**
 * useUserDeclarations Hook
 * Fetches and manages user declarations from API
 *
 * @module declarations/hooks
 * @author Claude Code
 * @date 2025-12-21
 */

import { useState, useEffect, useCallback } from 'react';
import { declarationsApi } from '../services/api';
import type { DeclarationResponse, DeclarationStatus } from '@/types/declaration';

interface UseUserDeclarationsOptions {
  status?: DeclarationStatus;
  page?: number;
  pageSize?: number;
  autoFetch?: boolean;
}

interface UseUserDeclarationsReturn {
  declarations: DeclarationResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useUserDeclarations(
  options: UseUserDeclarationsOptions = {}
): UseUserDeclarationsReturn {
  const { status, page = 1, pageSize = 20, autoFetch = true } = options;

  const [declarations, setDeclarations] = useState<DeclarationResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(page);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDeclarations = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await declarationsApi.listDeclarations({
        status,
        page: currentPage,
        pageSize,
      });

      setDeclarations(response.declarations);
      setTotal(response.total);
      setCurrentPage(response.page);
      setTotalPages(response.totalPages);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch declarations';
      setError(errorMessage);
      setDeclarations([]);
    } finally {
      setIsLoading(false);
    }
  }, [status, currentPage, pageSize]);

  useEffect(() => {
    if (autoFetch) {
      fetchDeclarations();
    }
  }, [fetchDeclarations, autoFetch]);

  return {
    declarations,
    total,
    page: currentPage,
    pageSize,
    totalPages,
    isLoading,
    error,
    refetch: fetchDeclarations,
  };
}

export default useUserDeclarations;
