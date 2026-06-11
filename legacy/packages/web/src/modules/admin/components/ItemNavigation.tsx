/**
 * Item Navigation Component
 * Provides Previous/Next navigation between items in a list
 *
 * @module admin/components
 * @date 2026-01-25
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useLocale } from 'next-intl';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ItemNavigationProps {
  /** Current item ID */
  currentId: number | string;
  /** All IDs in the list (in order) */
  allIds: (number | string)[];
  /** Base URL path (without locale, without ID) - e.g., "/dashboard/admin/workflow-mappings" */
  basePath: string;
  /** Optional labels */
  labels?: {
    previous?: string;
    next?: string;
  };
}

export function ItemNavigation({
  currentId,
  allIds,
  basePath,
  labels = { previous: 'Précédent', next: 'Suivant' },
}: ItemNavigationProps) {
  const locale = useLocale();

  const currentIndex = allIds.findIndex((id) => String(id) === String(currentId));
  const prevId = currentIndex > 0 ? allIds[currentIndex - 1] : null;
  const nextId = currentIndex < allIds.length - 1 ? allIds[currentIndex + 1] : null;

  if (allIds.length <= 1) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={!prevId}
        asChild={!!prevId}
      >
        {prevId ? (
          <Link href={`/${locale}${basePath}/${prevId}`}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            {labels.previous}
          </Link>
        ) : (
          <>
            <ChevronLeft className="h-4 w-4 mr-1" />
            {labels.previous}
          </>
        )}
      </Button>
      <span className="text-sm text-muted-foreground px-2">
        {currentIndex + 1} / {allIds.length}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={!nextId}
        asChild={!!nextId}
      >
        {nextId ? (
          <Link href={`/${locale}${basePath}/${nextId}`}>
            {labels.next}
            <ChevronRight className="h-4 w-4 ml-1" />
          </Link>
        ) : (
          <>
            {labels.next}
            <ChevronRight className="h-4 w-4 ml-1" />
          </>
        )}
      </Button>
    </div>
  );
}

export default ItemNavigation;
