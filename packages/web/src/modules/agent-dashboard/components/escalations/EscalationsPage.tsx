/**
 * EscalationsPage - Agent view of escalations (sent + received)
 * Two tabs: "Enviadas" (sent to supervisor) and "Recibidas" (assigned by supervisor)
 *
 * @module agent-dashboard/components/escalations
 * @date 2026-03-07
 */

'use client';

import React, { useState, useMemo } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  ArrowUpRight,
  ArrowDownLeft,
  AlertTriangle,
  ChevronDown,
  Clock,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  Hourglass,
  Eye,
  User,
  Calendar,
  FileText,
  XCircle,
  UserCheck,
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import { agentRequestsApi } from '../../services/agent-requests-api';
import type { EscalationListItem, EscalationHistoryEntry, PaginatedEscalationResponse } from '../../services/agent-requests-api';
import type { EntityCode } from '../../types';

const PAGE_SIZE = 20;

// =============================================================================
// PROPS
// =============================================================================

interface EscalationsPageProps {
  entityCode: EntityCode;
  basePath?: string;
}

// =============================================================================
// HELPERS
// =============================================================================

function formatDate(dateStr: string, locale: string): string {
  try {
    return new Date(dateStr).toLocaleDateString(locale, {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

function getTimeSince(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return '< 1h';
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function getEscalationStatusStyle(s: string) {
  switch (s) {
    case 'pending':
      return { bg: 'bg-orange-50 border-orange-200', text: 'text-orange-700', icon: Hourglass };
    case 'in_review':
      return { bg: 'bg-blue-50 border-blue-200', text: 'text-blue-700', icon: Eye };
    case 'resolved':
      return { bg: 'bg-green-50 border-green-200', text: 'text-green-700', icon: CheckCircle2 };
    default:
      return { bg: 'bg-gray-50 border-gray-200', text: 'text-gray-700', icon: Hourglass };
  }
}

function formatWorkflowType(code: string): string {
  const parts = code.split('_');
  if (parts.length > 1) {
    return parts.map((p) => p.charAt(0) + p.slice(1).toLowerCase()).join(' ');
  }
  return code;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function EscalationsPage({ entityCode, basePath }: EscalationsPageProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const tCommon = useTranslations('common');

  const [activeTab, setActiveTab] = useState<'sent' | 'received'>('sent');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [includeResolved, setIncludeResolved] = useState(false);
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, refetch } = useQuery<PaginatedEscalationResponse>({
    queryKey: ['my-escalations', activeTab, includeResolved, page],
    queryFn: () => agentRequestsApi.getMyEscalations({ includeResolved, direction: activeTab, page, pageSize: PAGE_SIZE }),
    staleTime: 30_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Reset page when filters change
  const handleTabChange = (v: string) => {
    setActiveTab(v as 'sent' | 'received');
    setStatusFilter('all');
    setPage(1);
  };
  const handleIncludeResolvedToggle = () => {
    setIncludeResolved(!includeResolved);
    setPage(1);
  };

  // Counts (from server-filtered items on current page)
  const pendingCount = useMemo(() => items.filter((i) => i.escalationStatus === 'pending').length, [items]);

  // Filter (client-side search + status on server-filtered items)
  const filtered = useMemo(() => {
    let result = items;
    if (statusFilter !== 'all') {
      result = result.filter((i) => i.escalationStatus === statusFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (i) =>
          i.caseReference.toLowerCase().includes(q) ||
          i.reason.toLowerCase().includes(q) ||
          i.caseType.toLowerCase().includes(q) ||
          (i.citizenName && i.citizenName.toLowerCase().includes(q))
      );
    }
    return result;
  }, [items, statusFilter, search]);

  const backHref = basePath
    ? `/${locale}${basePath}`
    : `/${locale}/dashboard/agent/${entityCode}`;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 pb-3 border-b shrink-0">
        <Link href={backHref}>
          <Button variant="ghost" size="sm" className="gap-1 px-2">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-orange-600" />
          <h1 className="text-lg font-semibold">{t('escalations.title')}</h1>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="h-8">
            <TabsTrigger value="sent" className="text-xs gap-1.5 px-3">
              <ArrowUpRight className="h-3.5 w-3.5" />
              {t('escalations.tabSent')}
              {activeTab === 'sent' && pendingCount > 0 && (
                <Badge className="bg-orange-100 text-orange-800 text-[10px] px-1 py-0 ml-1">{pendingCount}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="received" className="text-xs gap-1.5 px-3">
              <ArrowDownLeft className="h-3.5 w-3.5" />
              {t('escalations.tabReceived')}
              {activeTab === 'received' && total > 0 && (
                <Badge className="bg-blue-100 text-blue-800 text-[10px] px-1 py-0 ml-1">{total}</Badge>
              )}
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Filters */}
        <div className="flex items-center gap-2 ml-auto">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder={t('escalations.searchPlaceholder')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-8 w-[200px] text-sm"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-8 w-[140px] text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{tCommon('all')}</SelectItem>
              <SelectItem value="pending">{t('escalations.status.pending')}</SelectItem>
              <SelectItem value="in_review">{t('escalations.status.in_review')}</SelectItem>
              <SelectItem value="resolved">{t('escalations.status.resolved')}</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant={includeResolved ? 'secondary' : 'ghost'}
            size="sm"
            className="h-8 text-xs"
            onClick={handleIncludeResolvedToggle}
          >
            <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
            {t('escalations.showResolved')}
          </Button>
          <Button variant="ghost" size="sm" className="h-8 px-2" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </div>

      {/* Subtitle for active tab */}
      <p className="text-xs text-muted-foreground pt-2 pb-1">
        {activeTab === 'sent' ? t('escalations.subtitleSent') : t('escalations.subtitleReceived')}
      </p>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-[80px] w-full rounded-lg" />)}
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="h-8 w-8 text-destructive mb-2" />
            <p className="text-sm text-destructive">{t('escalations.loadError')}</p>
            <Button variant="outline" size="sm" className="mt-3" onClick={() => refetch()}>
              {tCommon('retry')}
            </Button>
          </div>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16">
            <ShieldAlert className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">
              {items.length === 0
                ? (activeTab === 'sent' ? t('escalations.emptySent') : t('escalations.emptyReceived'))
                : t('escalations.noResults')}
            </p>
          </div>
        )}

        {!isLoading && !isError && filtered.length > 0 && (
          <div className="space-y-2">
            {filtered.map((item) => (
              <EscalationCard
                key={item.id}
                item={item}
                locale={locale}
                entityCode={entityCode}
                t={t}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t pt-3 pb-1 shrink-0">
          <p className="text-xs text-muted-foreground">
            {tCommon('page')} {page} / {totalPages} &middot; {total} {t('escalations.totalLabel')}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              {tCommon('previous')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              disabled={page >= totalPages || isLoading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              {tCommon('next')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// ESCALATION CARD
// =============================================================================

function EscalationCard({
  item,
  locale,
  entityCode,
  t,
}: {
  item: EscalationListItem;
  locale: string;
  entityCode: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const style = getEscalationStatusStyle(item.escalationStatus);
  const StatusIcon = style.icon;
  const isSent = item.direction === 'sent';
  const hasHistory = item.history.length > 0;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          'rounded-lg border transition-colors hover:shadow-sm',
          style.bg
        )}
      >
        {/* Main card content */}
        <div className="flex items-start gap-3 p-3">
          {/* Status icon */}
          <div className={cn('shrink-0 flex items-center justify-center h-9 w-9 rounded-full mt-0.5', style.bg)}>
            <StatusIcon className={cn('h-4 w-4', style.text)} />
          </div>

          {/* Main content */}
          <div className="flex-1 min-w-0 space-y-1">
            {/* Top row */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-sm font-semibold">{item.caseReference}</span>
              <Badge variant="outline" className="text-[10px]">
                {formatWorkflowType(item.caseType)}
              </Badge>
              <Badge className={cn('text-[10px] gap-0.5', style.text, style.bg)}>
                {t(`escalations.status.${item.escalationStatus}`)}
              </Badge>
              {isSent ? (
                <Badge className="text-[10px] bg-orange-100 text-orange-700 gap-0.5">
                  <ArrowUpRight className="h-2.5 w-2.5" />
                  {t('escalations.directionSent')}
                </Badge>
              ) : (
                <Badge className="text-[10px] bg-blue-100 text-blue-700 gap-0.5">
                  <ArrowDownLeft className="h-2.5 w-2.5" />
                  {t('escalations.directionReceived')}
                </Badge>
              )}
            </div>

            {/* Reason */}
            <p className="text-xs text-muted-foreground line-clamp-2" title={item.reason}>
              <ShieldAlert className="h-3 w-3 inline mr-1 text-orange-500" />
              {item.reason}
            </p>

            {/* Meta row */}
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {formatDate(item.escalatedAt, locale)}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {getTimeSince(item.escalatedAt)}
              </span>
              {item.citizenName && (
                <span className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  {item.citizenName}
                </span>
              )}
              {!isSent && item.escalatedByName && (
                <span className="flex items-center gap-1 text-blue-600">
                  <User className="h-3 w-3" />
                  {t('escalations.escalatedBy', { name: item.escalatedByName })}
                </span>
              )}
            </div>
          </div>

          {/* Right actions */}
          <div className="shrink-0 flex items-center gap-1 mt-1">
            {!isSent && (
              <Link href={`/${locale}/dashboard/agent/${entityCode}?view=${item.id}`}>
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
                  <FileText className="h-3 w-3" />
                  {t('escalations.viewRequest')}
                </Button>
              </Link>
            )}
            {hasHistory && (
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                  <ChevronDown className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
                </Button>
              </CollapsibleTrigger>
            )}
          </div>
        </div>

        {/* Collapsible history timeline */}
        <CollapsibleContent>
          {hasHistory && (
            <div className="px-3 pb-3 pt-0">
              <div className="ml-[52px] border-t pt-2">
                <p className="text-[11px] font-medium text-muted-foreground mb-1.5">
                  {t('escalations.historyTitle')}
                </p>
                <div className="space-y-1.5">
                  {item.history.map((entry, idx) => (
                    <HistoryEntry key={idx} entry={entry} locale={locale} t={t} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

// =============================================================================
// HISTORY ENTRY
// =============================================================================

const ACTION_CONFIG: Record<string, { icon: React.ElementType; color: string; labelKey: string }> = {
  escalated: { icon: ArrowUpRight, color: 'text-orange-600', labelKey: 'escalations.history.escalated' },
  escalation_assigned: { icon: UserCheck, color: 'text-blue-600', labelKey: 'escalations.history.assigned' },
  escalation_resolved: { icon: ShieldCheck, color: 'text-green-600', labelKey: 'escalations.history.resolved' },
  supervisor_approve: { icon: CheckCircle2, color: 'text-green-600', labelKey: 'escalations.history.approved' },
  supervisor_reject: { icon: XCircle, color: 'text-red-600', labelKey: 'escalations.history.rejected' },
};

function HistoryEntry({
  entry,
  locale,
  t,
}: {
  entry: EscalationHistoryEntry;
  locale: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const config = ACTION_CONFIG[entry.action] || ACTION_CONFIG.escalated;
  const Icon = config.icon;

  return (
    <div className="flex items-start gap-2">
      <Icon className={cn('h-3.5 w-3.5 mt-0.5 shrink-0', config.color)} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('text-xs font-medium', config.color)}>
            {t(config.labelKey)}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {formatDate(entry.performedAt, locale)}
          </span>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
          {entry.performedByName && (
            <span>{entry.performedByName}</span>
          )}
          {entry.comment && (
            <span className="italic">— {entry.comment}</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default EscalationsPage;

