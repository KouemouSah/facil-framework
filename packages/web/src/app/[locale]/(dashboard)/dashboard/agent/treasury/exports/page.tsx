/**
 * Treasury Exports Page (Phase 2B)
 * Generate and download accounting exports
 * SAGE X3, Ministry reports, reconciliation exports
 */

'use client';

import { useState, useMemo } from 'react';
import { useTranslations, useLocale } from 'next-intl';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  Download,
  FileSpreadsheet,
  FileText,
  ChevronLeft,
  ChevronRight,
  Plus,
  Clock,
  CheckCircle,
  XCircle,
  Eye,
} from 'lucide-react';
import {
  useExports,
  useExportTemplates,
  useGenerateExport,
  useDownloadExport,
} from '@/modules/treasury/hooks';
import type {
  TreasuryExport,
  ExportParams,
  ExportStatus,
  ExportType,
  ExportFormat,
  ExportCreateRequest,
} from '@/modules/treasury/types';
import { useToast } from '@/hooks/use-toast';

// Status styling (labels come from translations)
const statusStyles: Record<ExportStatus, { color: string; Icon: typeof Clock }> = {
  pending: { color: 'bg-yellow-100 text-yellow-800 border-yellow-200', Icon: Clock },
  processing: { color: 'bg-blue-100 text-blue-800 border-blue-200', Icon: Loader2 },
  completed: { color: 'bg-green-100 text-green-800 border-green-200', Icon: CheckCircle },
  failed: { color: 'bg-red-100 text-red-800 border-red-200', Icon: XCircle },
};

// Format icons (prefixed to indicate intentional non-use for future expansion)
const _formatIcons: Record<ExportFormat, typeof FileSpreadsheet> = {
  csv: FileSpreadsheet,
  xlsx: FileSpreadsheet,
  pdf: FileText,
  xml: FileText,
  json: FileText,
};

// Export types list for iteration
const exportTypes: ExportType[] = ['sage_x3', 'ministry_report', 'bank_central', 'audit_report', 'reconciliation', 'custom'];
const exportStatuses: ExportStatus[] = ['pending', 'processing', 'completed', 'failed'];

// Supported formats per export type — only show formats that produce real output
const SUPPORTED_FORMATS: Record<ExportType, { formats: ExportFormat[]; default: ExportFormat }> = {
  sage_x3:         { formats: ['csv', 'xlsx'],        default: 'csv'  },
  ministry_report: { formats: ['pdf', 'xlsx', 'csv'], default: 'pdf'  },
  bank_central:    { formats: ['xml', 'xlsx'],        default: 'xml'  },
  audit_report:    { formats: ['xlsx', 'csv'],        default: 'xlsx' },
  reconciliation:  { formats: ['xlsx', 'csv'],        default: 'xlsx' },
  custom:          { formats: ['csv', 'xlsx', 'pdf', 'json'],default: 'csv'  },
};

function StatusBadge({ status, label }: { status: ExportStatus; label: string }) {
  const config = statusStyles[status];
  const { Icon } = config;
  const isAnimated = status === 'processing';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${config.color}`}>
      <Icon className={`h-3 w-3 ${isAnimated ? 'animate-spin' : ''}`} />
      {label}
    </span>
  );
}

// Locale mapping for Intl formatters
const LOCALE_MAP: Record<string, string> = { es: 'es-GQ', fr: 'fr-FR', en: 'en-US' };

export default function TreasuryExportsPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();
  const { toast } = useToast();

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Modal state
  const [isNewExportOpen, setIsNewExportOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [selectedExport, setSelectedExport] = useState<TreasuryExport | null>(null);

  // New export form state
  const [exportType, setExportType] = useState<ExportType>('sage_x3');
  const [exportFormat, setExportFormat] = useState<ExportFormat>('csv');
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');

  // Build query params
  const queryParams: ExportParams = useMemo(() => {
    const params: ExportParams = { page, pageSize };
    if (statusFilter !== 'all') params.status = statusFilter as ExportStatus;
    if (typeFilter !== 'all') params.exportType = typeFilter as ExportType;
    return params;
  }, [page, pageSize, statusFilter, typeFilter]);

  // Data fetching
  const { data: exportData, isLoading, error, refetch } = useExports(queryParams);
  const { data: templates } = useExportTemplates();
  const generateExport = useGenerateExport();
  const downloadExport = useDownloadExport();

  const exports = exportData?.exports || [];
  const total = exportData?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  const intlLocale = LOCALE_MAP[locale] || 'es-GQ';

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString(intlLocale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatCurrency = (amount?: number | null) => {
    if (amount === undefined || amount === null) return '-';
    return new Intl.NumberFormat(intlLocale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleOpenDetail = (exp: TreasuryExport) => {
    setSelectedExport(exp);
    setIsDetailOpen(true);
  };

  const handleOpenNewExport = () => {
    // Set default dates to current month
    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    setPeriodStart(firstDay.toISOString().split('T')[0]);
    setPeriodEnd(lastDay.toISOString().split('T')[0]);
    setExportType('sage_x3');
    setExportFormat('csv');
    setIsNewExportOpen(true);
  };

  const handleGenerateExport = async () => {
    if (!periodStart || !periodEnd) {
      toast({
        title: t('common.error'),
        description: t('exports.messages.errorGenerating'),
        variant: 'destructive',
      });
      return;
    }

    try {
      const request: ExportCreateRequest = {
        exportType,
        exportFormat,
        periodStart,
        periodEnd,
      };

      await generateExport.mutateAsync(request);
      toast({
        title: t('exports.messages.exportStarted'),
        description: t('exports.messages.exportStartedDescription'),
      });
      setIsNewExportOpen(false);
    } catch (err) {
      const detail = err instanceof Error ? err.message : t('exports.messages.errorGenerating');
      toast({
        title: t('common.error'),
        description: detail,
        variant: 'destructive',
      });
    }
  };

  const handleDownload = async (exp: TreasuryExport) => {
    if (exp.status !== 'completed') {
      toast({
        title: t('exports.messages.exportNotAvailable'),
        description: t('exports.messages.exportNotAvailableDescription'),
        variant: 'destructive',
      });
      return;
    }

    try {
      const result = await downloadExport.mutateAsync(exp.id);

      // Trigger browser download from blob
      const url = URL.createObjectURL(result.blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast({
        title: t('exports.messages.downloadStarted'),
        description: `${t('exports.fields.file')}: ${result.fileName}`,
      });
    } catch {
      toast({
        title: t('common.error'),
        description: t('exports.messages.errorDownloading'),
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <FileSpreadsheet className="h-8 w-8" />
            {t('exports.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('exports.description')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => refetch()} variant="outline" disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
          <Button onClick={handleOpenNewExport}>
            <Plus className="mr-2 h-4 w-4" />
            {t('exports.newExport')}
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('exports.messages.errorLoading')}</p>
          </CardContent>
        </Card>
      )}

      {/* Available Templates */}
      {templates && templates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('exports.templates')}</CardTitle>
            <CardDescription>
              {t('exports.templatesDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              {templates.map((template) => (
                <Card
                  key={template.id}
                  className="cursor-pointer hover:shadow-md transition-shadow border-2 hover:border-primary/40"
                  onClick={() => {
                    const type = template.exportType;
                    const supported = SUPPORTED_FORMATS[type];
                    setExportType(type);
                    // Use template's format if supported, otherwise use default
                    setExportFormat(
                      supported.formats.includes(template.exportFormat)
                        ? template.exportFormat
                        : supported.default
                    );
                    const now = new Date();
                    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
                    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
                    setPeriodStart(firstDay.toISOString().split('T')[0]);
                    setPeriodEnd(lastDay.toISOString().split('T')[0]);
                    setIsNewExportOpen(true);
                  }}
                >
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium">{template.name}</p>
                        <p className="text-sm text-muted-foreground">{template.description}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge variant="secondary">{t(`exports.types.${template.exportType}`)}</Badge>
                          <Badge variant="outline">{t(`exports.formats.${template.exportFormat}`)}</Badge>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('exports.filters')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder={t('exports.status.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('exports.status.all')}</SelectItem>
                {exportStatuses.map((status) => (
                  <SelectItem key={status} value={status}>{t(`exports.status.${status}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Type Filter */}
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger>
                <SelectValue placeholder={t('exports.types.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('exports.types.all')}</SelectItem>
                {exportTypes.map((type) => (
                  <SelectItem key={type} value={type}>{t(`exports.types.${type}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Exports Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" />
            {t('exports.history')}
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
          ) : exports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <FileSpreadsheet className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">{t('exports.noRecords')}</h3>
              <p className="text-muted-foreground">
                {t('exports.noRecordsDescription')}
              </p>
              <Button className="mt-4" onClick={handleOpenNewExport}>
                <Plus className="mr-2 h-4 w-4" />
                {t('exports.newExport')}
              </Button>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('exports.table.date')}</TableHead>
                      <TableHead>{t('exports.table.type')}</TableHead>
                      <TableHead>{t('exports.table.format')}</TableHead>
                      <TableHead>{t('exports.table.period')}</TableHead>
                      <TableHead>{t('exports.table.status')}</TableHead>
                      <TableHead>{t('exports.table.records')}</TableHead>
                      <TableHead>{t('exports.table.totalAmount')}</TableHead>
                      <TableHead>{t('exports.table.size')}</TableHead>
                      <TableHead>{t('exports.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {exports.map((exp: TreasuryExport) => (
                      <TableRow key={exp.id}>
                        <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {formatDate(exp.requestedAt)}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">
                            {t(`exports.types.${exp.exportType}`)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {t(`exports.formats.${exp.exportFormat}`)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {exp.periodStart} - {exp.periodEnd}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={exp.status} label={t(`exports.status.${exp.status}`)} />
                        </TableCell>
                        <TableCell className="text-sm tabular-nums">
                          {exp.totalRecords ?? '-'}
                        </TableCell>
                        <TableCell className="text-sm tabular-nums">
                          {formatCurrency(exp.totalAmount)}
                        </TableCell>
                        <TableCell className="text-sm">
                          {formatFileSize(exp.fileSizeBytes)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleOpenDetail(exp)}
                              title={t('common.viewDetails')}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            {exp.status === 'completed' && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDownload(exp)}
                                disabled={downloadExport.isPending}
                                title={t('common.download')}
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
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

      {/* New Export Modal */}
      <Dialog open={isNewExportOpen} onOpenChange={setIsNewExportOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              {t('exports.newExport')}
            </DialogTitle>
            <DialogDescription>
              {t('exports.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>{t('exports.types.label')}</Label>
              <Select value={exportType} onValueChange={(v) => {
                const newType = v as ExportType;
                setExportType(newType);
                // Auto-select best format for this type
                const supported = SUPPORTED_FORMATS[newType];
                if (!supported.formats.includes(exportFormat)) {
                  setExportFormat(supported.default);
                }
              }}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {exportTypes.map((type) => (
                    <SelectItem key={type} value={type}>
                      <div>
                        <span className="font-medium">{t(`exports.types.${type}`)}</span>
                        <span className="text-muted-foreground ml-2">- {t(`exports.typeDescriptions.${type}`)}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>{t('exports.formats.label')}</Label>
              <Select value={exportFormat} onValueChange={(v) => setExportFormat(v as ExportFormat)}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SUPPORTED_FORMATS[exportType].formats.map((format) => (
                    <SelectItem key={format} value={format}>
                      {t(`exports.formats.${format}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{t('exports.fields.periodStart')}</Label>
                <Input
                  type="date"
                  className="mt-1"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                />
              </div>
              <div>
                <Label>{t('exports.fields.periodEnd')}</Label>
                <Input
                  type="date"
                  className="mt-1"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsNewExportOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleGenerateExport}
              disabled={generateExport.isPending || !periodStart || !periodEnd}
            >
              {generateExport.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('exports.generateExport')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail Modal */}
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5" />
              {t('exports.detail')}
            </DialogTitle>
          </DialogHeader>

          {selectedExport && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.table.type')}</p>
                  <Badge variant="secondary">
                    {t(`exports.types.${selectedExport.exportType}`)}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.table.format')}</p>
                  <Badge variant="outline">
                    {t(`exports.formats.${selectedExport.exportFormat}`)}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.table.status')}</p>
                  <StatusBadge status={selectedExport.status} label={t(`exports.status.${selectedExport.status}`)} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.fields.progress')}</p>
                  <p className="font-medium">{selectedExport.progressPercentage}%</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.table.period')}</p>
                  <p className="text-sm">
                    {selectedExport.periodStart} - {selectedExport.periodEnd}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.fields.requestedBy')}</p>
                  <p className="text-sm">{selectedExport.requestedByName || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.table.records')}</p>
                  <p className="font-medium">{selectedExport.totalRecords ?? '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.table.totalAmount')}</p>
                  <p className="font-medium">{formatCurrency(selectedExport.totalAmount)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.table.size')}</p>
                  <p className="text-sm">{formatFileSize(selectedExport.fileSizeBytes)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.fields.downloads')}</p>
                  <p className="text-sm">{selectedExport.downloadCount}</p>
                </div>
              </div>

              {selectedExport.fileName && (
                <div>
                  <p className="text-sm text-muted-foreground">{t('exports.fields.file')}</p>
                  <p className="font-mono text-sm">{selectedExport.fileName}</p>
                </div>
              )}

              {selectedExport.errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-800">{selectedExport.errorMessage}</p>
                </div>
              )}

              <div className="grid grid-cols-3 gap-4 pt-4 border-t text-sm">
                <div>
                  <p className="text-muted-foreground">{t('exports.fields.requested')}</p>
                  <p>{formatDate(selectedExport.requestedAt)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{t('exports.fields.started')}</p>
                  <p>{formatDate(selectedExport.startedAt)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{t('exports.fields.completed')}</p>
                  <p>{formatDate(selectedExport.completedAt)}</p>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDetailOpen(false)}>
              {t('common.close')}
            </Button>
            {selectedExport?.status === 'completed' && (
              <Button onClick={() => handleDownload(selectedExport)}>
                <Download className="mr-2 h-4 w-4" />
                {t('common.download')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
