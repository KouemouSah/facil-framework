/**
 * ExpiryBadge - Color-coded expiry indicator
 *
 * Colors:
 * - Green: valid (>30 days)
 * - Orange: expiring_soon (<=30 days)
 * - Red: expired
 * - Muted: no expiry date set
 *
 * @module user-documents/components
 */

'use client';

import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import { Clock, AlertTriangle, XCircle, Infinity } from 'lucide-react';
import type { ExpiryStatus } from '../types';

interface ExpiryBadgeProps {
  expiryDate?: string | null;
  expiryStatus?: ExpiryStatus | null;
  daysUntilExpiry?: number | null;
  compact?: boolean;
}

export function ExpiryBadge({
  expiryDate,
  expiryStatus,
  daysUntilExpiry,
  compact = false,
}: ExpiryBadgeProps) {
  const t = useTranslations('userDocuments');

  // No expiry date = permanent document
  if (!expiryDate) {
    if (compact) return null;
    return (
      <Badge variant="outline" className="text-muted-foreground border-muted gap-1">
        <Infinity className="h-3 w-3" />
        {t('expiry.permanent')}
      </Badge>
    );
  }

  // Determine visual state
  const status = expiryStatus ?? computeExpiryStatus(expiryDate);
  const days = daysUntilExpiry ?? computeDaysUntilExpiry(expiryDate);

  switch (status) {
    case 'expired':
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          {compact ? t('expiry.expiredShort') : t('expiry.expired')}
        </Badge>
      );

    case 'expiring_soon':
      return (
        <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300 border-orange-200 dark:border-orange-800 gap-1">
          <AlertTriangle className="h-3 w-3" />
          {compact
            ? `${days}d`
            : t('expiry.expiringSoon', { days: days ?? '?' })}
        </Badge>
      );

    case 'valid':
    default:
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-green-200 dark:border-green-800 gap-1">
          <Clock className="h-3 w-3" />
          {compact
            ? `${days}d`
            : t('expiry.valid', { days: days ?? '>' })}
        </Badge>
      );
  }
}

// ---------------------------------------------------------------------------
// Helpers (fallback when backend doesn't provide computed fields)
// ---------------------------------------------------------------------------

function computeExpiryStatus(expiryDate: string): ExpiryStatus {
  const now = new Date();
  const expiry = new Date(expiryDate);
  const diffMs = expiry.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return 'expired';
  if (diffDays <= 30) return 'expiring_soon';
  return 'valid';
}

function computeDaysUntilExpiry(expiryDate: string): number {
  const now = new Date();
  const expiry = new Date(expiryDate);
  const diffMs = expiry.getTime() - now.getTime();
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}
