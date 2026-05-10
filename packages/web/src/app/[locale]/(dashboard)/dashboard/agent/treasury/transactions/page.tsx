/**
 * Treasury Transactions History Page
 * Shows processed payments (approved, rejected, completed) with filters, export, date range, and pagination.
 */

'use client';

import { useState, useMemo, useCallback } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
  Download,
  Filter,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react';
import { usePendingPayments } from '@/modules/treasury/hooks';
import { PaymentMethodBadge, WorkflowStatusBadge } from '@/modules/treasury/components';
import type { PendingPayment } from '@/modules/treasury/types';

interface TransactionFilters {
  status: string; // 'processed' | 'approved_by_agent' | 'rejected_by_agent' | 'completed' | 'all'
  method?: string;
  dateFrom?: string;
  dateTo?: string;
  page: number;
  pageSize: number;
}

const PAGE_SIZE_OPTIONS = [10, 20, 30, 50] as const;

export default function TreasuryTransactionsPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();

  const [filters, setFilters] = useState<TransactionFilters>({
    status: 'processed', // Default: only processed (not pending)
    page: 1,
    pageSize: 20,
  });
  const [searchTerm, setSearchTerm] = useState('');

  // Server-side pagination + filtering
  const { data: paymentsData, isLoading, error, refetch } = usePendingPayments({
    status: filters.status,
    method: filters.method,
    page: filters.page,
    pageSize: filters.pageSize,
    dateFrom: filters.dateFrom,
    dateTo: filters.dateTo,
  });

  // Client-side search filter (on top of server-side filters)
  const filteredTransactions = useMemo(() => {
    const transactions = paymentsData?.payments || [];
    if (!searchTerm) return transactions;
    const term = searchTerm.toLowerCase();
    return transactions.filter((tx: PendingPayment) =>
      tx.paymentReference.toLowerCase().includes(term) ||
      tx.userName?.toLowerCase().includes(term) ||
      tx.requestReference?.toLowerCase().includes(term)
    );
  }, [paymentsData?.payments, searchTerm]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const updateFilter = useCallback((key: keyof TransactionFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === 'all' && key === 'method' ? undefined : value,
      page: key === 'page' ? Number(value) : 1, // Reset to page 1 on filter change, except page navigation
    }));
  }, []);

  const clearDateRange = useCallback(() => {
    setFilters((prev) => ({
      ...prev,
      dateFrom: undefined,
      dateTo: undefined,
      page: 1,
    }));
  }, []);

  // CSV Export
  const handleExport = useCallback(() => {
    const transactions = paymentsData?.payments || [];
    if (transactions.length === 0) return;

    const headers = [
      t('transactions.table.reference'),
      t('transactions.table.citizen'),
      'Email',
      t('transactions.table.amount'),
      t('transactions.table.method'),
      t('transactions.table.workflowStatus'),
      t('transactions.table.date'),
      'Workflow',
    ];

    const rows = transactions.map((tx: PendingPayment) => [
      tx.paymentReference,
      tx.userName || 'N/A',
      tx.userEmail || '',
      tx.totalAmount.toString(),
      tx.paymentMethod,
      tx.workflowStatus,
      tx.submittedAt || tx.createdAt,
      tx.workflowCode || '',
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map((row) =>
        row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')
      ),
    ].join('\n');

    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const dateStr = new Date().toISOString().split('T')[0];
    link.download = `treasury-transactions-${dateStr}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [paymentsData?.payments, t]);

  // Stats from current page data
  const allTransactions = paymentsData?.payments || [];
  const totalAmount = allTransactions.reduce((sum: number, tx: PendingPayment) => sum + tx.totalAmount, 0);
  const approvedCount = allTransactions.filter((tx: PendingPayment) => tx.workflowStatus === 'approved_by_agent').length;
  const rejectedCount = allTransactions.filter((tx: PendingPayment) => tx.workflowStatus === 'rejected_by_agent').length;
  const completedCount = allTransactions.filter((tx: PendingPayment) => tx.workflowStatus === 'completed').length;

  const totalItems = paymentsData?.total || 0;
  const totalPages = Math.ceil(totalItems / filters.pageSize);
  const hasDateFilter = filters.dateFrom || filters.dateTo;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('transactions.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('transactions.description')}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleExport}
            disabled={!allTransactions.length}
          >
            <Download className="mr-2 h-4 w-4" />
            {t('transactions.export')}
          </Button>
          <Button onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('transactions.loadError')}</p>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Filter className="h-5 w-5" />
            {t('common.filters')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('transactions.searchPlaceholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Status Filter */}
            <Select
              value={filters.status}
              onValueChange={(v) => updateFilter('status', v)}
            >
              <SelectTrigger>
                <SelectValue placeholder={t('transactions.filters.status')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="processed">{t('transactions.filters.processed')}</SelectItem>
                <SelectItem value="approved_by_agent">{t('transactions.filters.approved')}</SelectItem>
                <SelectItem value="rejected_by_agent">{t('transactions.filters.rejected')}</SelectItem>
                <SelectItem value="completed">{t('transactions.filters.completed')}</SelectItem>
                <SelectItem value="all">{t('transactions.filters.statusAll')}</SelectItem>
              </SelectContent>
            </Select>

            {/* Method Filter */}
            <Select
              value={filters.method || 'all'}
              onValueChange={(v) => updateFilter('method', v)}
            >
              <SelectTrigger>
                <SelectValue placeholder={t('transactions.filters.method')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('transactions.filters.methodAll')}</SelectItem>
                <SelectItem value="cash">{t('transactions.filters.cash')}</SelectItem>
                <SelectItem value="check">{t('transactions.filters.check')}</SelectItem>
                <SelectItem value="mobile_money">{t('transactions.filters.mobile_money')}</SelectItem>
                <SelectItem value="bank_transfer">{t('transactions.filters.bank_transfer')}</SelectItem>
                <SelectItem value="card">{t('transactions.filters.card')}</SelectItem>
              </SelectContent>
            </Select>

            {/* Page Size */}
            <Select
              value={String(filters.pageSize)}
              onValueChange={(v) => setFilters((prev) => ({ ...prev, pageSize: Number(v), page: 1 }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size} {t('transactions.perPage')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date Range Row */}
          <div className="flex flex-wrap items-center gap-3 mt-4">
            <span className="text-sm text-muted-foreground">{t('transactions.dateRange')}:</span>
            <Input
              type="date"
              value={filters.dateFrom || ''}
              onChange={(e) => setFilters((prev) => ({ ...prev, dateFrom: e.target.value || undefined, page: 1 }))}
              className="w-auto"
            />
            <span className="text-sm text-muted-foreground">-</span>
            <Input
              type="date"
              value={filters.dateTo || ''}
              onChange={(e) => setFilters((prev) => ({ ...prev, dateTo: e.target.value || undefined, page: 1 }))}
              className="w-auto"
            />
            {hasDateFilter && (
              <Button variant="ghost" size="sm" onClick={clearDateRange}>
                <X className="h-4 w-4 mr-1" />
                {t('transactions.clearDates')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{totalItems}</div>
            <p className="text-xs text-muted-foreground">{t('transactions.stats.total')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">
              {formatCurrency(totalAmount)}
            </div>
            <p className="text-xs text-muted-foreground">{t('transactions.stats.totalAmount')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-600">
              {approvedCount + completedCount}
            </div>
            <p className="text-xs text-muted-foreground">{t('transactions.stats.approved')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-red-600">
              {rejectedCount}
            </div>
            <p className="text-xs text-muted-foreground">{t('transactions.stats.rejected')}</p>
          </CardContent>
        </Card>
      </div>

      {/* Transactions Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            {t('transactions.title')}
            <Badge variant="secondary" className="ml-2">
              {totalItems}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredTransactions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <History className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">{t('transactions.noRecords')}</h3>
              <p className="text-muted-foreground">
                {t('transactions.noRecordsDescription')}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('transactions.table.reference')}</TableHead>
                      <TableHead>{t('transactions.table.citizen')}</TableHead>
                      <TableHead>{t('transactions.table.amount')}</TableHead>
                      <TableHead>{t('transactions.table.method')}</TableHead>
                      <TableHead>{t('transactions.table.workflowStatus')}</TableHead>
                      <TableHead>{t('transactions.table.date')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredTransactions.map((tx: PendingPayment) => (
                      <TableRow key={tx.id}>
                        <TableCell>
                          <div>
                            <p className="font-mono text-sm">{tx.paymentReference}</p>
                            {tx.requestReference && (
                              <p className="text-xs text-muted-foreground">{tx.requestReference}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium text-sm">{tx.userName || 'N/A'}</p>
                            {tx.userEmail && (
                              <p className="text-xs text-muted-foreground">{tx.userEmail}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-bold">
                          {formatCurrency(tx.totalAmount)}
                        </TableCell>
                        <TableCell>
                          <PaymentMethodBadge method={tx.paymentMethod} />
                        </TableCell>
                        <TableCell>
                          <WorkflowStatusBadge status={tx.workflowStatus} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {formatDate(tx.submittedAt || tx.createdAt)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <p className="text-sm text-muted-foreground">
                  {t('common.pagination.showing', {
                    from: (filters.page - 1) * filters.pageSize + 1,
                    to: Math.min(filters.page * filters.pageSize, totalItems),
                    total: totalItems,
                  })}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFilters((p) => ({ ...p, page: p.page - 1 }))}
                    disabled={filters.page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    {t('common.pagination.previous')}
                  </Button>
                  <span className="text-sm text-muted-foreground px-2">
                    {filters.page} / {totalPages || 1}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFilters((p) => ({ ...p, page: p.page + 1 }))}
                    disabled={filters.page >= totalPages}
                  >
                    {t('common.pagination.next')}
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
