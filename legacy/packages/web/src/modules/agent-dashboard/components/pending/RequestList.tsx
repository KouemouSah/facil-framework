/**
 * RequestList - Left column list of pending requests
 * Supports dynamic column configuration from workflow_display_config
 *
 * @module agent-dashboard/components/pending
 * @date 2026-01-26
 * @updated 2026-02-01 - Added dynamic column support
 */

'use client';

import React from 'react';
import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, Inbox } from 'lucide-react';
import { RequestListItem } from './RequestListItem';
import type { ServiceRequestListItem } from '../../services/agent-requests-api';

// =============================================================================
// PROPS
// =============================================================================

interface RequestListProps {
  items: ServiceRequestListItem[];
  selectedId: string | null;
  onSelect: (id: string, index: number) => void;
  isLoading: boolean;
  isError: boolean;
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number) => void;
  /** Dynamic columns to display - if not provided, uses defaults */
  displayColumns?: string[];
}

// =============================================================================
// COMPONENT
// =============================================================================

export function RequestList({
  items,
  selectedId,
  onSelect,
  isLoading,
  isError,
  page,
  totalPages,
  total,
  onPageChange,
  displayColumns,
}: RequestListProps) {
  const t = useTranslations('agent.pending.list');

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col h-full border rounded-lg bg-card">
        <div className="flex-1 p-2 space-y-2 overflow-y-auto">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="flex flex-col h-full border rounded-lg bg-card">
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-muted-foreground">{t('loadError')}</p>
        </div>
      </div>
    );
  }

  // Empty state
  if (items.length === 0) {
    return (
      <div className="flex flex-col h-full border rounded-lg bg-card">
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <Inbox className="h-12 w-12 text-muted-foreground/50 mb-3" />
          <p className="text-sm text-muted-foreground">{t('empty')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border rounded-lg bg-card">
      {/* List items */}
      <div className="flex-1 overflow-y-auto">
        {items.map((item, index) => (
          <RequestListItem
            key={item.id}
            item={item}
            isSelected={item.id === selectedId}
            onClick={() => onSelect(item.id, index)}
            displayColumns={displayColumns}
          />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between p-2 border-t">
          <span className="text-xs text-muted-foreground">
            {page}/{totalPages} ({total})
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default RequestList;
