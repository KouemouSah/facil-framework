'use client';

/**
 * Badge component for verification status
 * Colors: pending=yellow, verified/verified_manually=green, rejected=red, fraud=dark red
 */

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { IdentifierStatus } from '../types';

interface VerificationStatusBadgeProps {
  status: IdentifierStatus | string;
  className?: string;
  showIcon?: boolean;
}

const statusConfig: Record<
  string,
  { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; className: string; icon: string }
> = {
  pending: {
    label: 'Pendiente',
    variant: 'outline',
    className: 'border-yellow-500 bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400',
    icon: '⏳',
  },
  verified: {
    label: 'Verificado',
    variant: 'default',
    className: 'bg-green-500 text-white hover:bg-green-600',
    icon: '✓',
  },
  verified_manually: {
    label: 'Verificado manualmente',
    variant: 'default',
    className: 'bg-green-600 text-white hover:bg-green-700',
    icon: '✓',
  },
  rejected: {
    label: 'Rechazado',
    variant: 'destructive',
    className: 'bg-red-500 text-white hover:bg-red-600',
    icon: '✗',
  },
  fraud: {
    label: 'Fraude',
    variant: 'destructive',
    className: 'bg-red-800 text-white hover:bg-red-900',
    icon: '⚠',
  },
};

export function VerificationStatusBadge({
  status,
  className,
  showIcon = true,
}: VerificationStatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.pending;

  return (
    <Badge
      variant={config.variant}
      className={cn(config.className, className)}
    >
      {showIcon && <span className="mr-1">{config.icon}</span>}
      {config.label}
    </Badge>
  );
}
