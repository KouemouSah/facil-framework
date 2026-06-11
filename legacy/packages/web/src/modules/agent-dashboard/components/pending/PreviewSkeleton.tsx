/**
 * PreviewSkeleton - Loading state for request preview
 *
 * @module agent-dashboard/components/pending
 * @date 2026-01-26
 */

'use client';

import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';

export function PreviewSkeleton() {
  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-32" />
      </div>

      {/* Request Info Section */}
      <div className="border rounded-lg p-4 space-y-3">
        <Skeleton className="h-5 w-40" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>

      {/* Extracted Data Section */}
      <div className="border rounded-lg p-4 space-y-3">
        <Skeleton className="h-5 w-36" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>

      {/* Documents Section */}
      <div className="border rounded-lg p-4 space-y-3">
        <Skeleton className="h-5 w-28" />
        <div className="flex gap-2">
          <Skeleton className="h-16 w-16" />
          <Skeleton className="h-16 w-16" />
          <Skeleton className="h-16 w-16" />
        </div>
      </div>

      {/* Contact Section */}
      <div className="border rounded-lg p-4 space-y-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-4 w-36" />
      </div>

      {/* Actions Section */}
      <div className="border rounded-lg p-4">
        <div className="flex gap-3">
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-32" />
        </div>
      </div>
    </div>
  );
}

export default PreviewSkeleton;
