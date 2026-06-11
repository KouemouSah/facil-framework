/**
 * Treasury Audit Page (Phase 1A)
 * Displays audit trail for all payment actions
 * Allows filtering by agent, action type, date range
 */

'use client';

import { useState, useMemo } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Search,
  Loader2,
  AlertCircle,
  RefreshCw,
  History,
  FileText,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ArrowUpRight,
} from 'lucide-react';
import { useAuditEntries } from '@/modules/treasury/hooks';
import type { AuditEntry, AgentActionType, AuditParams } from '@/modules/treasury/types';

// Action type styling configuration (colors/icons only)
// Note: lock_for_review, unlock_release, assign_to_colleague removed (not implemented)
const actionStyles: Record<
  AgentActionType,
  { color: string; Icon: typeof CheckCircle }
> = {
  approve: {
    color: 'bg-green-100 text-green-800 border-green-200',
    Icon: CheckCircle,
  },
  reject: {
    color: 'bg-red-100 text-red-800 border-red-200',
    Icon: XCircle,
  },
  request_documents: {
    color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    Icon: FileText,
  },
  escalate: {
    color: 'bg-purple-100 text-purple-800 border-purple-200',
    Icon: ArrowUpRight,
  },
};

// Action types for filter dropdown
const actionTypes: AgentActionType[] = [
  'approve',
  'reject',
  'request_documents',
  'escalate',
];

function ActionBadge({ action, label }: { action: AgentActionType; label: string }) {
  const style = actionStyles[action] || {
    color: 'bg-gray-100 text-gray-800 border-gray-200',
    Icon: AlertTriangle,
  };
  const { Icon } = style;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${style.color}`}
    >
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

export default function TreasuryAuditPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Build query params
  const queryParams: AuditParams = useMemo(() => {
    const params: AuditParams = { page, pageSize };
    if (actionFilter !== 'all') params.action = actionFilter as AgentActionType;
    if (dateFrom) params.dateFrom = dateFrom;
    if (dateTo) params.dateTo = dateTo;
    return params;
  }, [page, pageSize, actionFilter, dateFrom, dateTo]);

  // Data fetching
  const { data: auditData, isLoading, error, refetch } = useAuditEntries(queryParams);

  const total = auditData?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  // Filter by search term (client-side)
  const filteredEntries = useMemo(() => {
    // Extract entries array inside useMemo to avoid dependency issues
    const entries = auditData?.entries || [];
    if (!searchTerm) return entries;

    const term = searchTerm.toLowerCase();
    return entries.filter((e: AuditEntry) =>
      e.paymentReference.toLowerCase().includes(term) ||
      e.agentName?.toLowerCase().includes(term) ||
      e.serviceRequestReference?.toLowerCase().includes(term)
    );
  }, [auditData?.entries, searchTerm]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <History className="h-8 w-8" />
            {t('audit.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('audit.description')}
          </p>
        </div>
        <Button onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </Button>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('audit.loadError')}</p>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('audit.filters')}</CardTitle>
          <CardDescription>{t('audit.filtersDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('audit.searchPlaceholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Action Filter */}
            <Select value={actionFilter} onValueChange={setActionFilter}>
              <SelectTrigger>
                <SelectValue placeholder={t('audit.actionFilter.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('audit.actionFilter.all')}</SelectItem>
                {actionTypes.map((action) => (
                  <SelectItem key={action} value={action}>
                    {t(`audit.actionFilter.${action}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Date From */}
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />

            {/* Date To */}
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Audit Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            {t('audit.history')}
            {total > 0 && (
              <Badge variant="secondary" className="ml-2">
                {t('audit.records', { count: total })}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredEntries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <History className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">{t('audit.noRecords')}</h3>
              <p className="text-muted-foreground">
                {t('audit.noRecordsDescription')}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('audit.table.dateTime')}</TableHead>
                      <TableHead>{t('audit.table.paymentRef')}</TableHead>
                      <TableHead>{t('audit.table.serviceRequest')}</TableHead>
                      <TableHead>{t('audit.table.action')}</TableHead>
                      <TableHead>{t('audit.table.agent')}</TableHead>
                      <TableHead>{t('audit.table.transition')}</TableHead>
                      <TableHead>{t('audit.table.duration')}</TableHead>
                      <TableHead>{t('audit.table.comment')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredEntries.map((entry: AuditEntry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {formatDate(entry.createdAt)}
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {entry.paymentReference}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {entry.serviceRequestReference || '-'}
                        </TableCell>
                        <TableCell>
                          <ActionBadge
                            action={entry.action}
                            label={t(`audit.actions.${entry.action}`)}
                          />
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium text-sm">
                              {entry.agentName || t('audit.table.system')}
                            </p>
                            {entry.agentEmail && (
                              <p className="text-xs text-muted-foreground">{entry.agentEmail}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-xs">
                          {entry.fromStatus && entry.toStatus ? (
                            <span className="flex items-center gap-1">
                              <span className="text-muted-foreground">{entry.fromStatus}</span>
                              <span>→</span>
                              <span className="font-medium">{entry.toStatus}</span>
                            </span>
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell className="text-sm tabular-nums">
                          {formatDuration(entry.actionDurationSeconds)}
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">
                          {entry.comment || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <p className="text-sm text-muted-foreground">
                    {t('common.pagination.page', { page, totalPages })}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      {t('common.pagination.previous')}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                    >
                      {t('common.pagination.next')}
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
