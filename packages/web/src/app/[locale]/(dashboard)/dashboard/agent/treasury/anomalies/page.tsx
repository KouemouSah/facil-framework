/**
 * Treasury Anomalies Page (Phase 2A)
 * Displays payment anomalies for investigation
 * Uses tabs instead of dialogs for better UX
 */

'use client';

import { useState, useMemo } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Search,
  Loader2,
  AlertCircle,
  RefreshCw,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  ArrowUpRight,
  ShieldAlert,
  FileWarning,
  ArrowLeft,
  History,
} from 'lucide-react';
import {
  useAnomalies,
  useUpdateAnomalyStatus,
  useAnomalyActions,
} from '@/modules/treasury/hooks';
import type {
  Anomaly,
  AnomalyParams,
  AnomalyStatus,
  AnomalySeverity,
  AnomalyType,
} from '@/modules/treasury/types';
import { useToast } from '@/hooks/use-toast';

// Styling configs (labels come from translations)
const severityStyles: Record<AnomalySeverity, string> = {
  low: 'bg-gray-100 text-gray-800 border-gray-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  critical: 'bg-red-100 text-red-800 border-red-200',
};

const statusStyles: Record<AnomalyStatus, { color: string; Icon: typeof Clock }> = {
  open: { color: 'bg-blue-100 text-blue-800 border-blue-200', Icon: Clock },
  investigating: { color: 'bg-yellow-100 text-yellow-800 border-yellow-200', Icon: Search },
  resolved: { color: 'bg-green-100 text-green-800 border-green-200', Icon: CheckCircle },
  false_positive: { color: 'bg-gray-100 text-gray-800 border-gray-200', Icon: XCircle },
  escalated: { color: 'bg-purple-100 text-purple-800 border-purple-200', Icon: ArrowUpRight },
};

// Lists for iteration
const anomalyStatuses: AnomalyStatus[] = ['open', 'investigating', 'resolved', 'false_positive', 'escalated'];
const anomalySeverities: AnomalySeverity[] = ['low', 'medium', 'high', 'critical'];
const anomalyTypes: AnomalyType[] = ['duplicate_payment', 'amount_mismatch', 'reference_missing', 'orphan_transaction', 'late_validation', 'suspicious_pattern', 'high_amount', 'other'];

function SeverityBadge({ severity, label }: { severity: AnomalySeverity; label: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${severityStyles[severity]}`}>
      {label}
    </span>
  );
}

function StatusBadge({ status, label }: { status: AnomalyStatus; label: string }) {
  const config = statusStyles[status];
  const { Icon } = config;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${config.color}`}>
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

export default function TreasuryAnomaliesPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();
  const { toast } = useToast();

  // View state: 'list' or 'detail'
  const [view, setView] = useState<'list' | 'detail'>('list');
  const [activeTab, setActiveTab] = useState<'info' | 'actions'>('info');

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, _setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Selected anomaly for detail view
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);

  // Status change form
  const [newStatus, setNewStatus] = useState<AnomalyStatus | ''>('');
  const [statusComment, setStatusComment] = useState('');
  const [resolution, setResolution] = useState('');

  // Build query params
  const queryParams: AnomalyParams = useMemo(() => {
    const params: AnomalyParams = { page, pageSize };
    if (statusFilter !== 'all') params.status = statusFilter as AnomalyStatus;
    if (severityFilter !== 'all') params.severity = severityFilter as AnomalySeverity;
    if (typeFilter !== 'all') params.anomalyType = typeFilter as AnomalyType;
    if (dateFrom) params.dateFrom = dateFrom;
    if (dateTo) params.dateTo = dateTo;
    return params;
  }, [page, pageSize, statusFilter, severityFilter, typeFilter, dateFrom, dateTo]);

  // Data fetching
  const { data: anomalyData, isLoading, error, refetch } = useAnomalies(queryParams);
  const { data: actions, isLoading: actionsLoading } = useAnomalyActions(selectedAnomaly?.id);
  const updateStatus = useUpdateAnomalyStatus();

  const total = anomalyData?.total || 0;
  const summary = anomalyData?.summary;
  const totalPages = Math.ceil(total / pageSize);

  // Filter by search term (client-side)
  const filteredAnomalies = useMemo(() => {
    // Extract anomalies array inside useMemo to avoid dependency issues
    const anomalies = anomalyData?.anomalies || [];
    if (!searchTerm) return anomalies;
    const term = searchTerm.toLowerCase();
    return anomalies.filter((a: Anomaly) =>
      a.title.toLowerCase().includes(term) ||
      a.paymentReference?.toLowerCase().includes(term) ||
      a.serviceRequestReference?.toLowerCase().includes(term) ||
      a.entityId.toLowerCase().includes(term)
    );
  }, [anomalyData?.anomalies, searchTerm]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatCurrency = (amount?: number) => {
    if (!amount) return '-';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const handleOpenDetail = (anomaly: Anomaly) => {
    setSelectedAnomaly(anomaly);
    setNewStatus('');
    setStatusComment('');
    setResolution('');
    setActiveTab('info');
    setView('detail');
  };

  const handleBackToList = () => {
    setView('list');
    setSelectedAnomaly(null);
  };

  const handleUpdateStatus = async () => {
    if (!selectedAnomaly || !newStatus) return;

    try {
      await updateStatus.mutateAsync({
        anomalyId: selectedAnomaly.id,
        request: {
          newStatus: newStatus as AnomalyStatus,
          comment: statusComment || undefined,
          resolution: resolution || undefined,
        },
      });
      toast({
        title: t('common.success'),
        description: t('anomalies.changeStatusDescription'),
      });
      // Update local state
      setSelectedAnomaly({ ...selectedAnomaly, status: newStatus as AnomalyStatus });
      setNewStatus('');
      setStatusComment('');
      setResolution('');
      refetch();
    } catch {
      toast({
        title: t('common.error'),
        description: t('anomalies.changeStatusDescription'),
        variant: 'destructive',
      });
    }
  };

  // Get valid next statuses based on current status
  const getValidNextStatuses = (currentStatus: AnomalyStatus): AnomalyStatus[] => {
    const transitions: Record<AnomalyStatus, AnomalyStatus[]> = {
      open: ['investigating', 'resolved', 'false_positive', 'escalated'],
      investigating: ['resolved', 'false_positive', 'escalated'],
      resolved: [],
      false_positive: [],
      escalated: ['investigating', 'resolved'],
    };
    return transitions[currentStatus] || [];
  };

  // Detail View
  if (view === 'detail' && selectedAnomaly) {
    const validNextStatuses = getValidNextStatuses(selectedAnomaly.status);

    return (
      <div className="space-y-6">
        {/* Header with back button */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleBackToList}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <ShieldAlert className="h-6 w-6" />
              {t('anomalies.detail')}
            </h1>
            <p className="text-muted-foreground">{selectedAnomaly.title}</p>
          </div>
        </div>

        {/* Status badges */}
        <div className="flex items-center gap-4">
          <div>
            <span className="text-sm text-muted-foreground mr-2">{t('anomalies.severity.label')}:</span>
            <SeverityBadge severity={selectedAnomaly.severity} label={t(`anomalies.severity.${selectedAnomaly.severity}`)} />
          </div>
          <div>
            <span className="text-sm text-muted-foreground mr-2">{t('anomalies.status.label')}:</span>
            <StatusBadge status={selectedAnomaly.status} label={t(`anomalies.status.${selectedAnomaly.status}`)} />
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'info' | 'actions')}>
          <TabsList>
            <TabsTrigger value="info" className="flex items-center gap-2">
              <Eye className="h-4 w-4" />
              {t('common.viewDetails')}
            </TabsTrigger>
            <TabsTrigger value="actions" className="flex items-center gap-2">
              <History className="h-4 w-4" />
              {t('anomalies.actionHistory')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="info" className="space-y-6">
            {/* Info Card */}
            <Card>
              <CardHeader>
                <CardTitle>{t('anomalies.detail')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('anomalies.types.label')}</p>
                    <p className="font-medium">{t(`anomalies.types.${selectedAnomaly.anomalyType}`)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">{t('anomalies.fields.detectedAt')}</p>
                    <p className="font-medium">{formatDate(selectedAnomaly.detectedAt)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">{t('anomalies.fields.affectedAmount')}</p>
                    <p className="font-medium">{formatCurrency(selectedAnomaly.affectedAmount)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">{t('anomalies.fields.paymentReference')}</p>
                    <p className="font-mono text-sm">{selectedAnomaly.paymentReference || '-'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">{t('anomalies.fields.serviceRequestReference')}</p>
                    <p className="font-mono text-sm">{selectedAnomaly.serviceRequestReference || '-'}</p>
                  </div>
                </div>

                {selectedAnomaly.description && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">{t('anomaliesPage.description')}</p>
                    <p className="text-sm bg-muted p-3 rounded-lg">{selectedAnomaly.description}</p>
                  </div>
                )}

                {selectedAnomaly.resolution && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">{t('anomalies.resolution')}</p>
                    <p className="text-sm bg-green-50 p-3 rounded-lg border border-green-200">{selectedAnomaly.resolution}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Status Change Card */}
            {validNextStatuses.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>{t('anomalies.changeStatus')}</CardTitle>
                  <CardDescription>{t('anomalies.changeStatusDescription')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label>{t('anomalies.newStatus')}</Label>
                    <Select value={newStatus} onValueChange={(v) => setNewStatus(v as AnomalyStatus)}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder={t('anomalies.status.label')} />
                      </SelectTrigger>
                      <SelectContent>
                        {validNextStatuses.map((status) => (
                          <SelectItem key={status} value={status}>
                            {t(`anomalies.status.${status}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label>{t('anomalies.comment')}</Label>
                    <Textarea
                      className="mt-1"
                      placeholder={t('anomalies.comment')}
                      value={statusComment}
                      onChange={(e) => setStatusComment(e.target.value)}
                    />
                  </div>

                  {(newStatus === 'resolved' || newStatus === 'false_positive') && (
                    <div>
                      <Label>{t('anomalies.resolution')}</Label>
                      <Textarea
                        className="mt-1"
                        placeholder={t('anomalies.resolutionPlaceholder')}
                        value={resolution}
                        onChange={(e) => setResolution(e.target.value)}
                      />
                    </div>
                  )}

                  <Button
                    onClick={handleUpdateStatus}
                    disabled={!newStatus || updateStatus.isPending}
                  >
                    {updateStatus.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {t('common.save')}
                  </Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="actions">
            <Card>
              <CardHeader>
                <CardTitle>{t('anomalies.actionHistory')}</CardTitle>
              </CardHeader>
              <CardContent>
                {actionsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : !actions || actions.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    {t('common.noResults')}
                  </div>
                ) : (
                  <div className="border rounded-lg divide-y">
                    {actions.map((action) => (
                      <div key={action.id} className="p-4">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{action.action}</span>
                          <span className="text-sm text-muted-foreground">
                            {formatDate(action.performedAt)}
                          </span>
                        </div>
                        {action.fromStatus && action.toStatus && (
                          <p className="text-sm text-muted-foreground mt-1">
                            {t(`anomalies.status.${action.fromStatus}`)} → {t(`anomalies.status.${action.toStatus}`)}
                          </p>
                        )}
                        {action.comment && (
                          <p className="text-sm mt-2 bg-muted p-2 rounded">{action.comment}</p>
                        )}
                        {action.performedByName && (
                          <p className="text-xs text-muted-foreground mt-2">
                            {t('exports.fields.requestedBy')}: {action.performedByName}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    );
  }

  // List View
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <ShieldAlert className="h-8 w-8" />
            {t('anomalies.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('anomalies.description')}
          </p>
        </div>
        <Button onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </Button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid gap-4 md:grid-cols-5">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('anomalies.status.open')}</p>
                  <p className="text-2xl font-bold text-blue-600">{summary.open}</p>
                </div>
                <Clock className="h-8 w-8 text-blue-200" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('anomalies.status.investigating')}</p>
                  <p className="text-2xl font-bold text-yellow-600">{summary.investigating}</p>
                </div>
                <Search className="h-8 w-8 text-yellow-200" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('anomalies.status.resolved')}</p>
                  <p className="text-2xl font-bold text-green-600">{summary.resolved}</p>
                </div>
                <CheckCircle className="h-8 w-8 text-green-200" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('anomalies.status.false_positive')}</p>
                  <p className="text-2xl font-bold text-gray-600">{summary.falsePositive}</p>
                </div>
                <XCircle className="h-8 w-8 text-gray-200" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('anomalies.status.escalated')}</p>
                  <p className="text-2xl font-bold text-purple-600">{summary.escalated}</p>
                </div>
                <ArrowUpRight className="h-8 w-8 text-purple-200" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('common.error')}</p>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('anomalies.filters')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
            {/* Search */}
            <div className="relative lg:col-span-2">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('common.searchPlaceholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder={t('anomalies.status.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('anomalies.status.all')}</SelectItem>
                {anomalyStatuses.map((status) => (
                  <SelectItem key={status} value={status}>{t(`anomalies.status.${status}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Severity Filter */}
            <Select value={severityFilter} onValueChange={setSeverityFilter}>
              <SelectTrigger>
                <SelectValue placeholder={t('anomalies.severity.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('anomalies.severity.all')}</SelectItem>
                {anomalySeverities.map((severity) => (
                  <SelectItem key={severity} value={severity}>{t(`anomalies.severity.${severity}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Type Filter */}
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger>
                <SelectValue placeholder={t('anomalies.types.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('anomalies.types.all')}</SelectItem>
                {anomalyTypes.map((type) => (
                  <SelectItem key={type} value={type}>{t(`anomalies.types.${type}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Date From */}
            <Input
              type="date"
              placeholder={t('common.dateFrom')}
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Anomalies Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileWarning className="h-5 w-5" />
            {t('anomalies.history')}
            {total > 0 && (
              <Badge variant="secondary" className="ml-2">
                {total} {t('exports.records')}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredAnomalies.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertTriangle className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">{t('anomalies.noRecords')}</h3>
              <p className="text-muted-foreground">{t('common.noResults')}</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('anomalies.table.date')}</TableHead>
                      <TableHead>{t('anomalies.table.title')}</TableHead>
                      <TableHead>{t('anomalies.table.type')}</TableHead>
                      <TableHead>{t('anomalies.table.severity')}</TableHead>
                      <TableHead>{t('anomalies.table.status')}</TableHead>
                      <TableHead>{t('anomalies.table.reference')}</TableHead>
                      <TableHead>{t('anomalies.table.amount')}</TableHead>
                      <TableHead>{t('anomalies.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAnomalies.map((anomaly: Anomaly) => (
                      <TableRow
                        key={anomaly.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => handleOpenDetail(anomaly)}
                      >
                        <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {formatDate(anomaly.detectedAt)}
                        </TableCell>
                        <TableCell>
                          <div className="max-w-[200px]">
                            <p className="font-medium truncate">{anomaly.title}</p>
                            {anomaly.description && (
                              <p className="text-xs text-muted-foreground truncate">
                                {anomaly.description}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          {t(`anomalies.types.${anomaly.anomalyType}`)}
                        </TableCell>
                        <TableCell>
                          <SeverityBadge severity={anomaly.severity} label={t(`anomalies.severity.${anomaly.severity}`)} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={anomaly.status} label={t(`anomalies.status.${anomaly.status}`)} />
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {anomaly.paymentReference || anomaly.serviceRequestReference || '-'}
                        </TableCell>
                        <TableCell className="text-sm tabular-nums">
                          {formatCurrency(anomaly.affectedAmount)}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenDetail(anomaly);
                            }}
                            title={t('common.viewDetails')}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
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
