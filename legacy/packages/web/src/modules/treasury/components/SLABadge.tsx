/**
 * SLA Status Badge Component (Phase 1B)
 * Displays colored badge for SLA status with optional countdown
 */

'use client';

import { useMemo } from 'react';
import { useTranslations } from 'next-intl';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Clock, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import type { SLAStatus, PaymentWorkflowStatus } from '../types';
import { calculateSLAStatus } from '../types';

interface SLABadgeProps {
  slaTargetDate?: string | null;
  workflowStatus?: PaymentWorkflowStatus | string;
  status?: SLAStatus | 'completed';
  showCountdown?: boolean;
  className?: string;
}

const slaStyleConfig: Record<
  SLAStatus | 'completed',
  { color: string; bgColor: string; Icon: typeof Clock }
> = {
  on_time: {
    color: 'text-green-700',
    bgColor: 'bg-green-100 border-green-200',
    Icon: CheckCircle,
  },
  warning: {
    color: 'text-yellow-700',
    bgColor: 'bg-yellow-100 border-yellow-200',
    Icon: Clock,
  },
  critical: {
    color: 'text-orange-700',
    bgColor: 'bg-orange-100 border-orange-200',
    Icon: AlertTriangle,
  },
  breached: {
    color: 'text-red-700',
    bgColor: 'bg-red-100 border-red-200',
    Icon: XCircle,
  },
  completed: {
    color: 'text-gray-600',
    bgColor: 'bg-gray-100 border-gray-200',
    Icon: CheckCircle,
  },
};

function formatTimeRemaining(targetDate: string): string {
  const now = new Date();
  const target = new Date(targetDate);
  const diffMs = target.getTime() - now.getTime();

  if (diffMs < 0) {
    const hours = Math.floor(Math.abs(diffMs) / (1000 * 60 * 60));
    const minutes = Math.floor((Math.abs(diffMs) % (1000 * 60 * 60)) / (1000 * 60));
    if (hours > 24) {
      const days = Math.floor(hours / 24);
      return `-${days}d ${hours % 24}h`;
    }
    return `-${hours}h ${minutes}m`;
  }

  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  return `${hours}h ${minutes}m`;
}

export function SLABadge({
  slaTargetDate,
  workflowStatus,
  status: providedStatus,
  showCountdown = true,
  className,
}: SLABadgeProps) {
  const t = useTranslations('treasury');

  const status = useMemo(() => {
    if (providedStatus) return providedStatus;
    if (workflowStatus) {
      return calculateSLAStatus(slaTargetDate, workflowStatus);
    }
    return 'on_time' as SLAStatus;
  }, [providedStatus, slaTargetDate, workflowStatus]);

  const config = slaStyleConfig[status] || slaStyleConfig.on_time;
  const { Icon } = config;
  const label = t(`slaLabels.${status}`);

  const timeRemaining = useMemo(() => {
    if (!slaTargetDate || status === 'completed') return null;
    return formatTimeRemaining(slaTargetDate);
  }, [slaTargetDate, status]);

  const tooltipContent = useMemo(() => {
    if (!slaTargetDate) return t('slaLabels.noSla');
    const target = new Date(slaTargetDate);
    return `${t('slaLabels.deadline')} ${target.toLocaleString(undefined, {
      dateStyle: 'short',
      timeStyle: 'short',
    })}`;
  }, [slaTargetDate, t]);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${config.bgColor} ${config.color} ${className || ''}`}
          >
            <Icon className="h-3 w-3" />
            <span>{label}</span>
            {showCountdown && timeRemaining && (
              <span className="font-mono text-[10px] ml-1 opacity-80">
                ({timeRemaining})
              </span>
            )}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p>{tooltipContent}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * Compact SLA indicator for lists
 */
interface SLAIndicatorProps {
  status: SLAStatus | 'completed';
  className?: string;
}

export function SLAIndicator({ status, className }: SLAIndicatorProps) {
  const t = useTranslations('treasury');
  const dotColors: Record<SLAStatus | 'completed', string> = {
    on_time: 'bg-green-500',
    warning: 'bg-yellow-500',
    critical: 'bg-orange-500',
    breached: 'bg-red-500',
    completed: 'bg-gray-400',
  };

  const color = dotColors[status] || dotColors.on_time;
  const label = status in slaStyleConfig ? t(`slaLabels.${status}`) : status;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={`inline-block w-2 h-2 rounded-full ${color} ${className || ''}`}
          />
        </TooltipTrigger>
        <TooltipContent>
          <p>{label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default SLABadge;
