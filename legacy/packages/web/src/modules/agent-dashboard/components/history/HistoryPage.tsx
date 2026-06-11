'use client';

/**
 * HistoryPage - Generic history/timeline page for all entities
 * Displays chronological history of actions on service requests
 *
 * @module agent-dashboard/components/history
 * @date 2026-01-31
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import {
  RefreshCw,
  ChevronLeft,
  Search,
  Filter,
  Clock,
  ArrowRightCircle,
  FileText,
  FileMinus,
  UserPlus,
  Users,
  UserMinus,
  Calendar,
  CalendarClock,
  CalendarX,
  ShieldCheck,
  MessageSquare,
  CreditCard,
  Wallet,
  AlertTriangle,
  RotateCcw,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Scan,
  ScanLine,
  UserCog,
  Edit3,
  Database,
  Download,
  FileSpreadsheet,
  Loader2,
  X,
  SlidersHorizontal,
  BarChart3,
  TrendingUp,
  Activity,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { serviceRequestsApi } from '@/modules/service-requests/services/api';
import {
  HistoryActionType,
  HistoryEntrySource,
  getHistoryActionLabel,
  getHistoryActionColor,
  getStatusLabel,
  getStatusColor,
} from '@/modules/service-requests/types';
import type {
  HistorySummaryItem,
  HistoryEntry,
} from '@/modules/service-requests/types';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface HistoryPageProps {
  entityCode: EntityCode;
  workflowCodes?: string[];
  /** Base path for navigation (e.g., '/dashboard/agent/dgt') */
  basePath?: string;
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

// Icon mapping for history action types
const ActionIcon: React.FC<{ action: HistoryActionType | string; className?: string }> = ({
  action,
  className = 'h-4 w-4',
}) => {
  switch (action) {
    // Status changes
    case HistoryActionType.STATUS_CHANGE:
      return <ArrowRightCircle className={className} />;
    case HistoryActionType.STATUS_CORRECTION:
      return <Edit3 className={className} />;
    // Document actions
    case HistoryActionType.DOCUMENT_ADDED:
    case HistoryActionType.DOCUMENT_VALIDATED:
      return <FileText className={className} />;
    case HistoryActionType.DOCUMENT_REMOVED:
      return <FileMinus className={className} />;
    // OCR actions
    case HistoryActionType.OCR_COMPLETED:
      return <Scan className={className} />;
    case HistoryActionType.OCR_FAILED:
      return <ScanLine className={className} />;
    // Assignment actions
    case HistoryActionType.ASSIGNED:
      return <UserPlus className={className} />;
    case HistoryActionType.REASSIGNED:
      return <Users className={className} />;
    case HistoryActionType.UNASSIGNED:
      return <UserMinus className={className} />;
    // Appointment actions
    case HistoryActionType.CITA_SCHEDULED:
      return <Calendar className={className} />;
    case HistoryActionType.CITA_RESCHEDULED:
      return <CalendarClock className={className} />;
    case HistoryActionType.CITA_CANCELLED:
      return <CalendarX className={className} />;
    // Verification
    case HistoryActionType.VERIFICATION_UPDATED:
      return <ShieldCheck className={className} />;
    // Agent actions
    case HistoryActionType.AGENT_ACTION:
      return <UserCog className={className} />;
    // Payment actions
    case HistoryActionType.PAYMENT_INITIATED:
      return <Wallet className={className} />;
    case HistoryActionType.PAYMENT_RECEIVED:
      return <CreditCard className={className} />;
    case HistoryActionType.PAYMENT_FAILED:
      return <CreditCard className={className} />;
    // Communication
    case HistoryActionType.COMMENT_ADDED:
    case HistoryActionType.NOTE_ADDED:
      return <MessageSquare className={className} />;
    // Other
    case HistoryActionType.ESCALATED:
      return <AlertTriangle className={className} />;
    case HistoryActionType.REOPENED:
      return <RotateCcw className={className} />;
    default:
      return <Clock className={className} />;
  }
};

// Source badge labels
const getSourceLabel = (source: HistoryEntrySource | undefined, locale: 'es' | 'fr' | 'en'): string => {
  if (!source) return '';
  const labels: Record<string, Record<string, string>> = {
    [HistoryEntrySource.HISTORY]: { es: 'Historial', fr: 'Historique', en: 'History' },
    [HistoryEntrySource.OCR]: { es: 'OCR', fr: 'OCR', en: 'OCR' },
    [HistoryEntrySource.ASSIGNMENT]: { es: 'Asignación', fr: 'Assignation', en: 'Assignment' },
  };
  return labels[source]?.[locale] || source;
};

// Get confidence color
const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.9) return 'text-green-600 bg-green-100';
  if (confidence >= 0.7) return 'text-yellow-600 bg-yellow-100';
  return 'text-red-600 bg-red-100';
};

// Get risk level color
const getRiskLevelColor = (level: string): string => {
  const colors: Record<string, string> = {
    low: 'text-green-600 bg-green-100',
    medium: 'text-yellow-600 bg-yellow-100',
    high: 'text-orange-600 bg-orange-100',
    critical: 'text-red-600 bg-red-100',
  };
  return colors[level?.toLowerCase()] || 'text-gray-600 bg-gray-100';
};

// Timeline entry component
const TimelineEntry: React.FC<{
  entry: HistoryEntry;
  locale: 'es' | 'fr' | 'en';
  isLast: boolean;
}> = ({ entry, locale, isLast }) => {
  const t = useTranslations();
  const colorClass = getHistoryActionColor(entry.action);
  const date = new Date(entry.performedAt);
  const details = entry.details || {};

  // Check if this is an OCR entry
  const isOcrEntry = entry.action === HistoryActionType.OCR_COMPLETED ||
                     entry.action === HistoryActionType.OCR_FAILED ||
                     entry.source === HistoryEntrySource.OCR;

  // Check if this is an assignment entry
  const isAssignmentEntry = entry.action === HistoryActionType.ASSIGNED ||
                            entry.action === HistoryActionType.REASSIGNED ||
                            entry.source === HistoryEntrySource.ASSIGNMENT;

  return (
    <div className="flex gap-4">
      {/* Timeline line and dot */}
      <div className="flex flex-col items-center">
        <div className={`p-2 rounded-full ${colorClass}`}>
          <ActionIcon action={entry.action} className="h-4 w-4" />
        </div>
        {!isLast && <div className="w-0.5 flex-1 bg-gray-200 my-1" />}
      </div>

      {/* Content */}
      <div className="flex-1 pb-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <p className="font-medium text-sm">
                {getHistoryActionLabel(entry.action, locale)}
              </p>
              {/* Source badge for OCR/Assignment entries */}
              {entry.source && entry.source !== HistoryEntrySource.HISTORY && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  <Database className="h-2.5 w-2.5 mr-1" />
                  {getSourceLabel(entry.source, locale)}
                </Badge>
              )}
            </div>

            {/* Status change display */}
            {entry.action === HistoryActionType.STATUS_CHANGE && (
              <div className="flex items-center gap-2 mt-1">
                {entry.previousStatus && (
                  <Badge variant="outline" className="text-xs">
                    {getStatusLabel(entry.previousStatus, locale)}
                  </Badge>
                )}
                <ChevronRight className="h-3 w-3 text-muted-foreground" />
                {entry.newStatus && (
                  <Badge className={`text-xs ${getStatusColor(entry.newStatus)}`}>
                    {getStatusLabel(entry.newStatus, locale)}
                  </Badge>
                )}
              </div>
            )}

            {/* OCR-specific details */}
            {isOcrEntry && (
              <div className="mt-2 p-2 bg-muted/50 rounded-md text-xs space-y-1">
                {!!details.document_code && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.documentLabel', { defaultValue: 'Documento:' })}</span>
                    <span className="font-medium">{String(details.document_name || details.document_code)}</span>
                  </div>
                )}
                {details.extraction_confidence !== undefined && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.confidenceLabel', { defaultValue: 'Confianza:' })}</span>
                    <Badge className={`text-[10px] px-1.5 ${getConfidenceColor(Number(details.extraction_confidence))}`}>
                      {Math.round(Number(details.extraction_confidence) * 100)}%
                    </Badge>
                  </div>
                )}
                {!!details.risk_level && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.riskLabel', { defaultValue: 'Riesgo:' })}</span>
                    <Badge className={`text-[10px] px-1.5 ${getRiskLevelColor(String(details.risk_level))}`}>
                      {String(details.risk_level)}
                    </Badge>
                  </div>
                )}
                {!!details.processor && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.processorLabel', { defaultValue: 'Procesador:' })}</span>
                    <span>{String(details.processor)}</span>
                  </div>
                )}
                {!!details.has_error && !!details.error_message && (
                  <div className="text-red-600 mt-1">
                    {t('history.errorPrefix', { defaultValue: 'Error:' })} {String(details.error_message)}
                  </div>
                )}
              </div>
            )}

            {/* Assignment-specific details */}
            {isAssignmentEntry && (
              <div className="mt-2 p-2 bg-muted/50 rounded-md text-xs space-y-1">
                {!!details.agent_name && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.agentLabel', { defaultValue: 'Agente:' })}</span>
                    <span className="font-medium">{String(details.agent_name)}</span>
                  </div>
                )}
                {!!details.reassigned_to_name && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.reassignedToLabel', { defaultValue: 'Reasignado a:' })}</span>
                    <span className="font-medium">{String(details.reassigned_to_name)}</span>
                  </div>
                )}
                {!!details.assignment_method && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.methodLabel', { defaultValue: 'Método:' })}</span>
                    <Badge variant="outline" className="text-[10px] px-1.5">
                      {String(details.assignment_method)}
                    </Badge>
                  </div>
                )}
                {!!details.reassignment_reason && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t('history.reasonLabel', { defaultValue: 'Motivo:' })}</span>
                    <span>{String(details.reassignment_reason)}</span>
                  </div>
                )}
              </div>
            )}

            {/* Generic details for other entry types */}
            {!isOcrEntry && !isAssignmentEntry && entry.details && Object.keys(entry.details).length > 0 && (
              <div className="text-xs text-muted-foreground mt-1">
                {!!details.document_code && (
                  <span>{t('history.docPrefix', { defaultValue: 'Doc:' })} {String(details.document_code)}</span>
                )}
                {!!details.agent_name && (
                  <span>{t('history.agentLabel', { defaultValue: 'Agente:' })} {String(details.agent_name)}</span>
                )}
              </div>
            )}

            {entry.comment && (
              <p className="text-sm text-muted-foreground mt-1">{entry.comment}</p>
            )}
          </div>
          <div className="text-right text-xs text-muted-foreground ml-2">
            <p>{date.toLocaleDateString(locale === 'es' ? 'es-ES' : locale === 'fr' ? 'fr-FR' : 'en-US')}</p>
            <p>{date.toLocaleTimeString(locale === 'es' ? 'es-ES' : locale === 'fr' ? 'fr-FR' : 'en-US', { hour: '2-digit', minute: '2-digit' })}</p>
          </div>
        </div>
        {entry.performedBy && (
          <p className="text-xs text-muted-foreground mt-1">
            {entry.performedBy.isSystem ? (
              <span className="italic">{t('history.system', { defaultValue: 'Sistema' })}</span>
            ) : (
              entry.performedBy.fullName
            )}
          </p>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function HistoryPage({
  entityCode,
  workflowCodes = [],
  basePath,
}: HistoryPageProps) {
  const router = useRouter();
  const currentLocale = useLocale() as 'es' | 'fr' | 'en';
  const t = useTranslations();

  // Derive entity path from entityCode if basePath not provided
  const entityPath = basePath || `/dashboard/agent/${entityCode.toLowerCase().replace('_', '-')}`;

  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRequest, setSelectedRequest] = useState<HistorySummaryItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Advanced filters
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [actionTypeFilter, setActionTypeFilter] = useState<string>('all');
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');

  // Statistics
  const [showStatistics, setShowStatistics] = useState(false);

  // Query for list of requests with history summary
  const {
    data: listData,
    isLoading: isListLoading,
    isError: isListError,
    refetch: refetchList,
    isFetching: isListFetching,
  } = useQuery({
    queryKey: ['history-list', entityCode, statusFilter, page, pageSize],
    queryFn: () =>
      serviceRequestsApi.listRequestsWithHistory(
        entityCode,
        workflowCodes,
        statusFilter === 'all' ? undefined : statusFilter,
        page,
        pageSize
      ),
  });

  // Query for detailed history when a request is selected
  const {
    data: detailData,
    isLoading: isDetailLoading,
  } = useQuery({
    queryKey: ['history-detail', selectedRequest?.requestId],
    queryFn: () =>
      selectedRequest
        ? serviceRequestsApi.getRequestHistory(selectedRequest.requestId)
        : Promise.reject('No request selected'),
    enabled: !!selectedRequest,
  });

  // Query for statistics
  const {
    data: statsData,
    isLoading: isStatsLoading,
  } = useQuery({
    queryKey: ['history-stats', entityCode, workflowCodes],
    queryFn: () =>
      serviceRequestsApi.getHistoryStatistics(entityCode, 30, workflowCodes),
    enabled: showStatistics,
  });

  const handleRowClick = (item: HistorySummaryItem) => {
    setSelectedRequest(item);
    setIsDetailOpen(true);
  };

  const handleBack = () => {
    router.push(`/${currentLocale}${entityPath}`);
  };

  // Export state
  const [isExporting, setIsExporting] = useState<'csv' | 'pdf' | null>(null);

  // Export handler
  const handleExport = async (format: 'csv' | 'pdf') => {
    if (!selectedRequest) return;

    setIsExporting(format);
    try {
      const blob = await serviceRequestsApi.exportHistory(
        selectedRequest.requestId,
        format,
        true,  // includeOcr
        true   // includeAssignments
      );

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `historial_${selectedRequest.reference}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export error:', error);
    } finally {
      setIsExporting(null);
    }
  };

  // Filter items by search query and advanced filters (client-side)
  const filteredItems =
    listData?.items.filter((item) => {
      // Text search (reference or citizen name)
      const matchesSearch =
        !searchQuery ||
        item.reference.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (item.citizenName?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false);

      // Action type filter
      const matchesActionType =
        actionTypeFilter === 'all' || item.lastAction === actionTypeFilter;

      // Date range filter (based on last action date)
      let matchesDateRange = true;
      if (item.lastActionAt) {
        const actionDate = new Date(item.lastActionAt);
        if (fromDate) {
          const from = new Date(fromDate);
          matchesDateRange = matchesDateRange && actionDate >= from;
        }
        if (toDate) {
          const to = new Date(toDate);
          to.setHours(23, 59, 59, 999);
          matchesDateRange = matchesDateRange && actionDate <= to;
        }
      }

      return matchesSearch && matchesActionType && matchesDateRange;
    }) || [];

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleBack}>
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {t('history.title', { defaultValue: 'Historial de Solicitudes' })}
            </h1>
            <p className="text-muted-foreground">
              {t('history.subtitle', {
                defaultValue: 'Timeline de acciones en solicitudes',
              })}
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          onClick={() => refetchList()}
          disabled={isListFetching}
        >
          <RefreshCw
            className={`h-4 w-4 mr-2 ${isListFetching ? 'animate-spin' : ''}`}
          />
          {t('common.refresh', { defaultValue: 'Actualizar' })}
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          {/* Basic filters row */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('common.search', {
                  defaultValue: 'Buscar por referencia o nombre...',
                })}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-[200px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder={t('history.statusPlaceholder', { defaultValue: 'Estado' })} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {t('common.all', { defaultValue: 'Todos' })}
                </SelectItem>
                <SelectItem value="SUBMITTED">
                  {t('status.submitted', { defaultValue: 'Enviada' })}
                </SelectItem>
                <SelectItem value="UNDER_REVIEW">
                  {t('status.under_review', { defaultValue: 'En Revisión' })}
                </SelectItem>
                <SelectItem value="DOSSIER_VALIDE">
                  {t('status.dossier_valide', { defaultValue: 'Dossier Validado' })}
                </SelectItem>
                <SelectItem value="APPROVED">
                  {t('status.approved', { defaultValue: 'Aprobada' })}
                </SelectItem>
                <SelectItem value="COMPLETED">
                  {t('status.completed', { defaultValue: 'Completada' })}
                </SelectItem>
                <SelectItem value="REJECTED">
                  {t('status.rejected', { defaultValue: 'Rechazada' })}
                </SelectItem>
                <SelectItem value="CANCELLED">
                  {t('status.cancelled', { defaultValue: 'Cancelada' })}
                </SelectItem>
                <SelectItem value="EXPIRED">
                  {t('status.expired', { defaultValue: 'Expirada' })}
                </SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
              className={showAdvancedFilters ? 'bg-muted' : ''}
            >
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
          </div>

          {/* Advanced filters */}
          <Collapsible open={showAdvancedFilters}>
            <CollapsibleContent className="pt-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-4 bg-muted/50 rounded-lg">
                {/* Action type filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">
                    {t('history.filterByAction', { defaultValue: 'Tipo de Acción' })}
                  </label>
                  <Select value={actionTypeFilter} onValueChange={setActionTypeFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('history.allPlaceholder', { defaultValue: 'Todos' })} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        {t('common.all', { defaultValue: 'Todos' })}
                      </SelectItem>
                      <SelectItem value="status_change">
                        {t('history.action.statusChange', { defaultValue: 'Cambio de Estado' })}
                      </SelectItem>
                      <SelectItem value="document_added">
                        {t('history.action.documentAdded', { defaultValue: 'Documento Agregado' })}
                      </SelectItem>
                      <SelectItem value="ocr_completed">
                        {t('history.action.ocrCompleted', { defaultValue: 'OCR Completado' })}
                      </SelectItem>
                      <SelectItem value="assigned">
                        {t('history.action.assigned', { defaultValue: 'Asignado' })}
                      </SelectItem>
                      <SelectItem value="cita_scheduled">
                        {t('history.action.citaScheduled', { defaultValue: 'Cita Programada' })}
                      </SelectItem>
                      <SelectItem value="payment_received">
                        {t('history.action.paymentReceived', { defaultValue: 'Pago Recibido' })}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* From date */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">
                    {t('history.fromDate', { defaultValue: 'Desde' })}
                  </label>
                  <Input
                    type="date"
                    value={fromDate}
                    onChange={(e) => setFromDate(e.target.value)}
                    className="w-full"
                  />
                </div>

                {/* To date */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">
                    {t('history.toDate', { defaultValue: 'Hasta' })}
                  </label>
                  <Input
                    type="date"
                    value={toDate}
                    onChange={(e) => setToDate(e.target.value)}
                    className="w-full"
                  />
                </div>

                {/* Clear filters button */}
                <div className="flex items-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setActionTypeFilter('all');
                      setFromDate('');
                      setToDate('');
                      setSearchQuery('');
                      setStatusFilter('all');
                    }}
                    className="w-full"
                  >
                    <X className="h-4 w-4 mr-2" />
                    {t('common.clearFilters', { defaultValue: 'Limpiar Filtros' })}
                  </Button>
                </div>
              </div>

              {/* Active filters badges */}
              {(actionTypeFilter !== 'all' || fromDate || toDate) && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {actionTypeFilter !== 'all' && (
                    <Badge variant="secondary" className="gap-1">
                      {t('history.action.' + actionTypeFilter, { defaultValue: actionTypeFilter })}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => setActionTypeFilter('all')}
                      />
                    </Badge>
                  )}
                  {fromDate && (
                    <Badge variant="secondary" className="gap-1">
                      {t('history.from', { defaultValue: 'Desde' })}: {fromDate}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => setFromDate('')}
                      />
                    </Badge>
                  )}
                  {toDate && (
                    <Badge variant="secondary" className="gap-1">
                      {t('history.to', { defaultValue: 'Hasta' })}: {toDate}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => setToDate('')}
                      />
                    </Badge>
                  )}
                </div>
              )}
            </CollapsibleContent>
          </Collapsible>
        </CardContent>
      </Card>

      {/* Stats summary */}
      {listData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('history.totalRequests', { defaultValue: 'Total solicitudes' })}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-3xl font-bold">{listData.total}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('common.page', { defaultValue: 'Página' })}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-3xl font-bold">
                {listData.page} / {Math.ceil(listData.total / listData.pageSize) || 1}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('common.showing', { defaultValue: 'Mostrando' })}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-3xl font-bold">
                {filteredItems.length} {t('common.of', { defaultValue: 'de' })}{' '}
                {listData.items.length}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Statistics Panel */}
      <Collapsible open={showStatistics} onOpenChange={setShowStatistics}>
        <Card>
          <CollapsibleTrigger asChild>
            <CardHeader className="py-4 cursor-pointer hover:bg-muted/50 transition-colors">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  {t('history.statistics', { defaultValue: 'Estadísticas (últimos 30 días)' })}
                </CardTitle>
                {showStatistics ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="pt-0">
              {isStatsLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[...Array(4)].map((_, i) => (
                    <Skeleton key={i} className="h-24" />
                  ))}
                </div>
              ) : statsData ? (
                <div className="space-y-6">
                  {/* Key metrics */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 bg-blue-50 rounded-lg">
                      <p className="text-2xl font-bold text-blue-700">{statsData.totalActions}</p>
                      <p className="text-xs text-blue-600">
                        {t('history.totalActions', { defaultValue: 'Total Acciones' })}
                      </p>
                    </div>
                    <div className="p-4 bg-green-50 rounded-lg">
                      <p className="text-2xl font-bold text-green-700">{statsData.totalRequests}</p>
                      <p className="text-xs text-green-600">
                        {t('history.activeRequests', { defaultValue: 'Solicitudes Activas' })}
                      </p>
                    </div>
                    <div className="p-4 bg-purple-50 rounded-lg">
                      <p className="text-2xl font-bold text-purple-700">
                        {statsData.busiestDay
                          ? new Date(statsData.busiestDay).toLocaleDateString(
                              currentLocale === 'es' ? 'es-ES' : currentLocale === 'fr' ? 'fr-FR' : 'en-US',
                              { day: 'numeric', month: 'short' }
                            )
                          : '-'}
                      </p>
                      <p className="text-xs text-purple-600">
                        {t('history.busiestDay', { defaultValue: 'Día más Activo' })}
                      </p>
                    </div>
                    <div className="p-4 bg-amber-50 rounded-lg">
                      <p className="text-2xl font-bold text-amber-700 truncate">
                        {statsData.mostCommonAction
                          ? getHistoryActionLabel(statsData.mostCommonAction, currentLocale)
                          : '-'}
                      </p>
                      <p className="text-xs text-amber-600">
                        {t('history.mostCommonAction', { defaultValue: 'Acción más Común' })}
                      </p>
                    </div>
                  </div>

                  {/* Action distribution */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                        <Activity className="h-4 w-4" />
                        {t('history.actionDistribution', { defaultValue: 'Distribución de Acciones' })}
                      </h4>
                      <div className="space-y-2">
                        {statsData.actionDistribution.slice(0, 6).map((item) => {
                          const maxCount = Math.max(...statsData.actionDistribution.map((d) => d.count));
                          const percentage = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
                          return (
                            <div key={item.action} className="flex items-center gap-2">
                              <span className={`p-1 rounded ${getHistoryActionColor(item.action)}`}>
                                <ActionIcon action={item.action} className="h-3 w-3" />
                              </span>
                              <span className="text-xs text-muted-foreground flex-1 truncate">
                                {getHistoryActionLabel(item.action, currentLocale)}
                              </span>
                              <div className="w-24 bg-gray-200 rounded-full h-2 overflow-hidden">
                                <div
                                  className="bg-blue-600 h-full rounded-full"
                                  style={{ width: `${percentage}%` }}
                                />
                              </div>
                              <span className="text-xs font-medium w-8 text-right">{item.count}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Average time by status */}
                    <div>
                      <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        {t('history.avgTimeByStatus', { defaultValue: 'Tiempo Promedio por Estado' })}
                      </h4>
                      <div className="space-y-2">
                        {statsData.avgTimeByStatus.slice(0, 6).map((item) => (
                          <div key={item.status} className="flex items-center justify-between">
                            <Badge variant="outline" className="text-xs">
                              {getStatusLabel(item.status, currentLocale)}
                            </Badge>
                            <span className="text-sm">
                              {item.avgHours < 24
                                ? `${item.avgHours.toFixed(1)}h`
                                : `${(item.avgHours / 24).toFixed(1)}d`}
                            </span>
                          </div>
                        ))}
                        {statsData.avgTimeByStatus.length === 0 && (
                          <p className="text-xs text-muted-foreground text-center py-4">
                            {t('history.noTimeData', { defaultValue: 'Sin datos de tiempo' })}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Daily activity */}
                  <div>
                    <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                      <TrendingUp className="h-4 w-4" />
                      {t('history.dailyActivity', { defaultValue: 'Actividad Diaria (últimos 14 días)' })}
                    </h4>
                    <div className="flex items-end gap-1 h-16">
                      {statsData.dailyActivity.slice(0, 14).reverse().map((day, idx) => {
                        const maxActions = Math.max(...statsData.dailyActivity.map((d) => d.actions));
                        const height = maxActions > 0 ? (day.actions / maxActions) * 100 : 0;
                        return (
                          <div
                            key={day.date || idx}
                            className="flex-1 bg-blue-500 rounded-t hover:bg-blue-600 transition-colors"
                            style={{ height: `${Math.max(height, 5)}%` }}
                            title={t('history.actionsTooltip', { defaultValue: '{date}: {count} acciones', date: day.date, count: day.actions })}
                          />
                        );
                      })}
                    </div>
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>
                        {statsData.dailyActivity.length > 0
                          ? new Date(statsData.dailyActivity[statsData.dailyActivity.length - 1]?.date).toLocaleDateString(
                              currentLocale === 'es' ? 'es-ES' : currentLocale === 'fr' ? 'fr-FR' : 'en-US',
                              { day: 'numeric', month: 'short' }
                            )
                          : ''}
                      </span>
                      <span>
                        {statsData.dailyActivity.length > 0
                          ? new Date(statsData.dailyActivity[0]?.date).toLocaleDateString(
                              currentLocale === 'es' ? 'es-ES' : currentLocale === 'fr' ? 'fr-FR' : 'en-US',
                              { day: 'numeric', month: 'short' }
                            )
                          : ''}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-4">
                  {t('common.noData', { defaultValue: 'Sin datos disponibles' })}
                </p>
              )}
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Table */}
      <Card>
        <CardContent className="pt-6">
          {isListLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : isListError ? (
            <div className="text-center py-12 text-red-500">
              {t('common.error', { defaultValue: 'Error al cargar los datos' })}
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              {t('history.noHistory', {
                defaultValue: 'No hay historial disponible',
              })}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    {t('common.reference', { defaultValue: 'Referencia' })}
                  </TableHead>
                  <TableHead>
                    {t('common.citizen', { defaultValue: 'Ciudadano' })}
                  </TableHead>
                  <TableHead>
                    {t('common.status', { defaultValue: 'Estado' })}
                  </TableHead>
                  <TableHead>
                    {t('history.lastAction', { defaultValue: 'Última Acción' })}
                  </TableHead>
                  <TableHead>
                    {t('history.totalActions', { defaultValue: 'Acciones' })}
                  </TableHead>
                  <TableHead>
                    {t('common.date', { defaultValue: 'Fecha' })}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((item) => (
                  <TableRow
                    key={item.requestId}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleRowClick(item)}
                  >
                    <TableCell className="font-medium">{item.reference}</TableCell>
                    <TableCell>{item.citizenName || '-'}</TableCell>
                    <TableCell>
                      <Badge className={getStatusColor(item.currentStatus)}>
                        {getStatusLabel(item.currentStatus, currentLocale)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span
                          className={`p-1 rounded ${getHistoryActionColor(
                            item.lastAction
                          )}`}
                        >
                          <ActionIcon action={item.lastAction} className="h-3 w-3" />
                        </span>
                        <span className="text-sm">
                          {getHistoryActionLabel(item.lastAction, currentLocale)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{item.totalActions}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.lastActionAt
                        ? new Date(item.lastActionAt).toLocaleDateString(
                            currentLocale === 'es' ? 'es-ES' : currentLocale === 'fr' ? 'fr-FR' : 'en-US'
                          )
                        : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {listData && listData.total > pageSize && (
            <div className="flex items-center justify-between pt-4 border-t mt-4">
              <p className="text-sm text-muted-foreground">
                {t('common.showingOf', {
                  defaultValue: `Mostrando ${(page - 1) * pageSize + 1}-${Math.min(
                    page * pageSize,
                    listData.total
                  )} de ${listData.total}`,
                })}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  {t('common.previous', { defaultValue: 'Anterior' })}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page * pageSize >= listData.total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t('common.next', { defaultValue: 'Siguiente' })}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Sheet */}
      <Sheet open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <SheetContent className="w-[500px] sm:max-w-[540px]">
          <SheetHeader>
            <SheetTitle>
              {t('history.detailTitle', { defaultValue: 'Timeline de Solicitud' })}
            </SheetTitle>
            <SheetDescription>
              {selectedRequest?.reference} - {selectedRequest?.citizenName}
            </SheetDescription>
          </SheetHeader>

          <div className="mt-6">
            {isDetailLoading ? (
              <div className="space-y-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="flex gap-4">
                    <Skeleton className="h-10 w-10 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : detailData ? (
              <>
                {/* Stats */}
                <div className="grid grid-cols-3 gap-2 mb-4">
                  <div className="text-center p-2 bg-muted rounded">
                    <p className="text-lg font-bold">{detailData.totalStatusChanges || 0}</p>
                    <p className="text-xs text-muted-foreground">Estados</p>
                  </div>
                  <div className="text-center p-2 bg-muted rounded">
                    <p className="text-lg font-bold">{detailData.totalDocuments || 0}</p>
                    <p className="text-xs text-muted-foreground">Docs</p>
                  </div>
                  <div className="text-center p-2 bg-muted rounded">
                    <p className="text-lg font-bold">{detailData.totalAssignments || 0}</p>
                    <p className="text-xs text-muted-foreground">Asign.</p>
                  </div>
                </div>

                {/* Export Buttons */}
                <div className="flex gap-2 mb-6">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('csv')}
                    disabled={isExporting !== null}
                    className="flex-1"
                  >
                    {isExporting === 'csv' ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <FileSpreadsheet className="h-4 w-4 mr-2" />
                    )}
                    {t('history.exportCsv', { defaultValue: 'Exportar CSV' })}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('pdf')}
                    disabled={isExporting !== null}
                    className="flex-1"
                  >
                    {isExporting === 'pdf' ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Download className="h-4 w-4 mr-2" />
                    )}
                    {t('history.exportPdf', { defaultValue: 'Exportar PDF' })}
                  </Button>
                </div>

                {/* Timeline */}
                <ScrollArea className="h-[calc(100vh-300px)]">
                  <div className="pr-4">
                    {detailData.entries.length === 0 ? (
                      <p className="text-center text-muted-foreground py-8">
                        {t('history.noEntries', { defaultValue: 'Sin entradas de historial' })}
                      </p>
                    ) : (
                      detailData.entries.map((entry, index) => (
                        <TimelineEntry
                          key={entry.id}
                          entry={entry}
                          locale={currentLocale}
                          isLast={index === detailData.entries.length - 1}
                        />
                      ))
                    )}
                  </div>
                </ScrollArea>
              </>
            ) : (
              <p className="text-center text-muted-foreground">
                {t('common.noData', { defaultValue: 'Sin datos' })}
              </p>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default HistoryPage;
