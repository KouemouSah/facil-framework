/**
 * RequestListItem - Individual item in the request list
 * Supports dynamic column rendering based on workflow_display_config
 *
 * @module agent-dashboard/components/pending
 * @date 2026-01-26
 * @updated 2026-02-01 - Added dynamic column rendering support
 */

'use client';

import React from 'react';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { Clock, AlertTriangle, AlertCircle, FileStack, ShieldAlert, ShieldCheck, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations';
import type { ServiceRequestListItem, SlaStatus, Priority } from '../../services/agent-requests-api';

// =============================================================================
// DEFAULT COLUMNS
// =============================================================================

/**
 * Default columns to display when no configuration is provided
 * These match the original hardcoded layout
 */
export const DEFAULT_LIST_COLUMNS = [
  'reference',
  'slaDeadline',
  'priority',
  'solicitudType',
  'fullName',
] as const;

// =============================================================================
// PROPS
// =============================================================================

interface RequestListItemProps {
  item: ServiceRequestListItem;
  isSelected: boolean;
  onClick: () => void;
  /** Dynamic columns to display - if not provided, uses DEFAULT_LIST_COLUMNS */
  displayColumns?: string[];
}

// =============================================================================
// HELPERS
// =============================================================================

const PRIORITY_STYLES: Record<Priority, { bg: string; text: string; key: string }> = {
  URGENT: { bg: 'bg-red-100', text: 'text-red-700', key: 'priorityUrgent' },
  HIGH: { bg: 'bg-orange-100', text: 'text-orange-700', key: 'priorityHigh' },
  NORMAL: { bg: 'bg-blue-100', text: 'text-blue-700', key: 'priorityNormal' },
  LOW: { bg: 'bg-gray-100', text: 'text-gray-600', key: 'priorityLow' },
};

const SLA_STYLES: Record<SlaStatus, { icon: React.ReactNode; text: string }> = {
  on_track: { icon: <Clock className="h-3 w-3" />, text: 'text-green-600' },
  at_risk: { icon: <AlertTriangle className="h-3 w-3" />, text: 'text-orange-600' },
  violated: { icon: <AlertCircle className="h-3 w-3" />, text: 'text-red-600' },
};

function formatSlaTime(deadline: string | null, t: (key: string, values?: Record<string, string | number>) => string): string {
  if (!deadline) return '';
  const now = new Date();
  const sla = new Date(deadline);
  const diffMs = sla.getTime() - now.getTime();
  const diffHours = Math.round(diffMs / (1000 * 60 * 60));

  if (diffHours < 0) return t('slaHoursDelayed', { hours: Math.abs(diffHours) });
  if (diffHours < 24) return t('slaHours', { hours: diffHours });
  return t('slaDays', { days: Math.floor(diffHours / 24) });
}

function formatWorkflowLabel(workflowCode: string, _solicitudType: string, _motivo: string | null): string {
  // Universal: workflow_code is now resolved (e.g. PASAPORTE_DETERIORO, not PASAPORTE_NUEVO)
  // Strip family prefix and title-case the suffix for compact display
  const parts = workflowCode.split('_');
  if (parts.length > 1) {
    return parts
      .slice(1)
      .map((p) => p.charAt(0) + p.slice(1).toLowerCase())
      .join(' ');
  }
  return workflowCode;
}

// =============================================================================
// DATE FORMATTING
// =============================================================================

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  });
}

const STATUS_KEYS: Record<string, string> = {
  submitted: 'statusSubmitted',
  pending_review: 'statusPendingReview',
  approved: 'statusApproved',
  rejected: 'statusRejected',
  pending_documents: 'statusPendingDocuments',
  pending_payment: 'statusPendingPayment',
  completed: 'statusCompleted',
};

function formatStatus(status: string, t: (key: string) => string): string {
  const key = STATUS_KEYS[status];
  return key ? t(key) : status;
}

function formatTimeAgo(dateString: string, locale: string = 'es'): string {
  try {
    const now = Date.now();
    const date = new Date(dateString).getTime();
    const diffSec = Math.floor((now - date) / 1000);
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto', style: 'short' });
    if (diffSec < 60) return rtf.format(-diffSec, 'second');
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return rtf.format(-diffMin, 'minute');
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return rtf.format(-diffHours, 'hour');
    const diffDays = Math.floor(diffHours / 24);
    return rtf.format(-diffDays, 'day');
  } catch {
    return dateString;
  }
}

// =============================================================================
// COMPONENT
// =============================================================================

export function RequestListItem({
  item,
  isSelected,
  onClick,
  displayColumns = [...DEFAULT_LIST_COLUMNS],
}: RequestListItemProps) {
  const locale = useLocale();
  const t = useTranslations('agent.pending');
  const { tw } = useWorkflowTranslations();
  const priorityStyle = PRIORITY_STYLES[item.priority] || PRIORITY_STYLES.NORMAL;
  const slaStyle = SLA_STYLES[item.slaStatus] || SLA_STYLES.on_track;

  // Helper to check if column should be displayed
  const showColumn = (columnId: string) => displayColumns.includes(columnId);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      className={cn(
        'p-2.5 border-b cursor-pointer transition-colors',
        'hover:bg-blue-50/60',
        isSelected && 'bg-blue-100 border-l-4 border-l-blue-600'
      )}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-0.5">
        {/* Reference - left side */}
        {showColumn('reference') && (
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-sm font-medium">{item.reference}</span>
            {item.batchReference && item.batchId && (
              <Link
                href={`/${locale}/dashboard/batch-requests/${item.batchId}`}
                onClick={(e) => e.stopPropagation()}
                title={item.batchReference}
              >
                <Badge className="text-[10px] px-1 py-0 bg-indigo-100 text-indigo-700 hover:bg-indigo-200 cursor-pointer">
                  <FileStack className="h-2.5 w-2.5 mr-0.5" />
                  LOT
                </Badge>
              </Link>
            )}
            {item.supervisorAssigned && (
              <Badge className="text-[10px] px-1 py-0 bg-purple-100 text-purple-700">
                <ShieldCheck className="h-2.5 w-2.5 mr-0.5" />
                {t('supervisorBadge')}
              </Badge>
            )}
          </div>
        )}
        {!showColumn('reference') && <span />}

        {/* Right side indicators */}
        <div className="flex items-center gap-2">
          {/* SLA indicator */}
          {showColumn('slaDeadline') && item.slaDeadline && (
            <span className={cn('flex items-center gap-1 text-xs', slaStyle.text)}>
              {slaStyle.icon}
              {formatSlaTime(item.slaDeadline, t)}
            </span>
          )}
          {/* Priority badge */}
          {showColumn('priority') && (
            <Badge className={cn('text-[10px] px-1.5 py-0', priorityStyle.bg, priorityStyle.text)}>
              {t(priorityStyle.key)}
            </Badge>
          )}
          {/* Status badge (new) */}
          {showColumn('status') && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
              {formatStatus(item.status, t)}
            </Badge>
          )}
        </div>
      </div>

      {/* Compact line: workflow type + citizen name */}
      {(showColumn('solicitudType') || showColumn('fullName')) && (
        <p className="text-xs text-muted-foreground truncate">
          {showColumn('solicitudType') && tw(workflowNameKey(item.workflowCode), formatWorkflowLabel(item.workflowCode, item.solicitudType, item.motivo))}
          {showColumn('solicitudType') && showColumn('fullName') && ' · '}
          {showColumn('fullName') && item.citizenName}
        </p>
      )}

      {/* Created date (shown only when solicitudType is hidden) */}
      {showColumn('createdAt') && !showColumn('solicitudType') && (
        <p className="text-xs text-muted-foreground">
          {formatDate(item.createdAt)}
        </p>
      )}

      {/* Assigned agent (supervisor team view) */}
      {showColumn('assignedAgent') && (
        <div className="flex items-center gap-1 mt-1">
          <User className="h-3 w-3 text-blue-500 flex-shrink-0" />
          <span className="text-xs text-blue-600 truncate">
            {item.assignedAgentName || t('teamView.unassigned')}
          </span>
        </div>
      )}

      {/* Escalation info (only shown when escalation data present) */}
      {item.escalationReason && (
        <div className="flex items-center gap-1.5 mt-1">
          <ShieldAlert className="h-3 w-3 text-orange-500 flex-shrink-0" />
          <span className="text-xs text-orange-600 truncate">{item.escalationReason}</span>
          {item.escalatedAt && (
            <span className="text-[10px] text-muted-foreground flex-shrink-0">
              {formatTimeAgo(item.escalatedAt, locale)}
            </span>
          )}
        </div>
      )}

      {/* Additional info row for createdAt when solicitudType is also shown */}
      {showColumn('createdAt') && showColumn('solicitudType') && (
        <p className="text-xs text-muted-foreground mt-1">
          {formatDate(item.createdAt)}
        </p>
      )}
    </div>
  );
}

export default RequestListItem;
