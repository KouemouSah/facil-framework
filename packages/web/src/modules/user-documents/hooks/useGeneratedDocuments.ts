/**
 * useGeneratedDocuments - Hook for listing platform-generated documents
 *
 * Handles certificates, receipts, and other platform-generated files
 * with cursor-based infinite scrolling.
 *
 * @module user-documents/hooks
 * @date 2026-04-05
 */

'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import { userDocumentsApi } from '../services/api';
import { userDocumentKeys } from './useUserDocuments';
import type { GeneratedDocument } from '../types';

// =============================================================================
// TYPES
// =============================================================================

interface GeneratedDocumentsPage {
  items: GeneratedDocument[];
  next_cursor?: string;
}

// =============================================================================
// HOOK
// =============================================================================

/**
 * Infinite-scroll list of platform-generated documents.
 *
 * @param generationType - Optional filter: e.g. "certificate", "receipt", "summary_pdf"
 * @param limit - Page size (default 20)
 */
export function useGeneratedDocuments(
  generationType?: string,
  limit: number = 20
) {
  const query = useInfiniteQuery<GeneratedDocumentsPage, Error>({
    queryKey: userDocumentKeys.generated(generationType),
    queryFn: ({ pageParam }) => {
      return userDocumentsApi.listGenerated(
        generationType,
        pageParam as string | undefined,
        limit
      );
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: 60_000, // 1 minute - generated docs change less frequently
    refetchOnWindowFocus: false,
  });

  // Flatten pages into a single array
  const documents: GeneratedDocument[] =
    query.data?.pages.flatMap((page) => page.items) ?? [];

  return {
    ...query,
    documents,
    totalCount: documents.length,
  };
}
