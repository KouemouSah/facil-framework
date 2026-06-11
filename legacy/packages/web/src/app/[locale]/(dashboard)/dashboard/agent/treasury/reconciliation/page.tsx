/**
 * Treasury Reconciliation Page
 * Match bank transactions (from BANGE webhooks) with system payments
 * + System Payments overview with validation/reconciliation status
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandItem,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import {
  Search,
  Loader2,
  AlertCircle,
  RefreshCw,
  Link2,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Banknote,
  Zap,
  Target,
  ChevronsUpDown,
  Minus,
  Wallet,
  TrendingUp,
  CreditCard,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useUnreconciledTransactions, useReconcileTransaction, useReconciliationSuggestions, useAutoMatch, usePendingPayments } from '@/modules/treasury/hooks';
import { useTreasuryStats } from '@/modules/treasury/hooks/useTreasuryStats';
import { treasuryApi } from '@/modules/treasury/services/api';
import type { BankTransaction, BankTransactionParams, ReconciliationSuggestion, SearchPaymentResult, PendingPayment } from '@/modules/treasury/types';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 20;
const SP_PAGE_SIZE = 10;

export default function TreasuryReconciliationPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();

  // Bank transactions pagination + filter
  const [page, setPage] = useState(1);
  const [bankTxStatus, setBankTxStatus] = useState<string>('unreconciled');

  // System payments pagination
  const [spPage, setSpPage] = useState(1);

  // Search with debounce (C4 + M9)
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Reset page on status filter change
  useEffect(() => {
    setPage(1);
  }, [bankTxStatus]);

  // Reconciliation dialog state
  const [selectedTransaction, setSelectedTransaction] = useState<BankTransaction | null>(null);
  const [selectedPayment, setSelectedPayment] = useState<SearchPaymentResult | null>(null);
  const [isReconcileDialogOpen, setIsReconcileDialogOpen] = useState(false);
  const [paymentSearchOpen, setPaymentSearchOpen] = useState(false);
  const [paymentSearchQuery, setPaymentSearchQuery] = useState('');

  // Data fetching — bank transactions with status filter
  const { data: transactionsData, isLoading, error, refetch } = useUnreconciledTransactions({
    page,
    pageSize: PAGE_SIZE,
    search: debouncedSearch || undefined,
    status: bankTxStatus === 'unreconciled' ? undefined : bankTxStatus as BankTransactionParams['status'],
  });

  // System payments (all statuses)
  const { data: systemPaymentsData, isLoading: spLoading } = usePendingPayments({
    workflowStatus: 'all' as never,
    page: spPage,
    pageSize: SP_PAGE_SIZE,
  });

  // Global stats for KPI
  const { data: statsData } = useTreasuryStats();

  // Reconcile mutation
  const reconcileMutation = useReconcileTransaction();
  const isReconciling = reconcileMutation.isPending;

  // Smart matching suggestions
  const { data: suggestionsData } = useReconciliationSuggestions();
  const autoMatchMutation = useAutoMatch();
  const suggestions = suggestionsData?.suggestions || [];
  const highConfidenceSuggestions = suggestions.filter((s: ReconciliationSuggestion) => s.bestScore >= 80);

  // Payment search for ComboBox
  const { data: searchPaymentResults } = useQuery({
    queryKey: ['reconciliation-payment-search', paymentSearchQuery, selectedTransaction?.currency],
    queryFn: () => treasuryApi.searchPaymentsForReconciliation(paymentSearchQuery, selectedTransaction?.currency),
    enabled: paymentSearchQuery.length >= 2,
    staleTime: 10 * 1000,
  });

  // Computed values
  const totalTransactions = transactionsData?.total || 0;
  const totalPages = Math.max(1, Math.ceil(totalTransactions / PAGE_SIZE));
  const transactions = transactionsData?.transactions || [];

  const systemPayments = systemPaymentsData?.payments || [];
  const spTotal = systemPaymentsData?.total || 0;
  const spTotalPages = Math.max(1, Math.ceil(spTotal / SP_PAGE_SIZE));

  // KPI computations
  const completedPayments = systemPayments.filter((p: PendingPayment) => p.workflowStatus === 'completed').length;
  const totalValidatedAmount = systemPayments
    .filter((p: PendingPayment) => p.workflowStatus === 'completed')
    .reduce((sum: number, p: PendingPayment) => sum + (p.totalAmount || 0), 0);

  const formatCurrency = useCallback((amount: number, currency: string = 'XAF') => {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
    }).format(amount);
  }, [locale]);

  const formatDate = useCallback((dateString: string | undefined | null) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }, [locale]);

  const openReconcileDialog = (transaction: BankTransaction, payment?: SearchPaymentResult) => {
    setSelectedTransaction(transaction);
    setSelectedPayment(payment || null);
    setPaymentSearchQuery('');
    setPaymentSearchOpen(false);
    setIsReconcileDialogOpen(true);
  };

  const handleReconcile = async () => {
    if (!selectedTransaction || !selectedPayment) return;

    await reconcileMutation.mutateAsync({
      bankTransactionId: selectedTransaction.id,
      servicePaymentId: selectedPayment.id,
    });

    setIsReconcileDialogOpen(false);
    setSelectedTransaction(null);
    setSelectedPayment(null);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'unreconciled':
        return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">{t('reconciliationPage.status.unreconciled')}</Badge>;
      case 'reconciled':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">{t('reconciliationPage.status.reconciled')}</Badge>;
      case 'failed':
        return <Badge variant="destructive">{t('reconciliationPage.status.failed')}</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getWorkflowStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">{t('reconciliationPage.workflowStatus.completed')}</Badge>;
      case 'rejected_by_agent':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">{t('reconciliationPage.workflowStatus.rejected')}</Badge>;
      case 'expired':
        return <Badge variant="outline" className="bg-gray-50 text-gray-600 border-gray-200">{t('reconciliationPage.workflowStatus.expired')}</Badge>;
      case 'pending_agent_review':
        return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">{t('reconciliationPage.workflowStatus.pending')}</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getPaymentMethodLabel = (method: string) => {
    const labels: Record<string, string> = {
      cash: 'Cash',
      check: 'Cheque',
      mobile_money: 'Mobile Money',
      card: 'Tarjeta',
      bank_transfer: 'Transferencia',
    };
    return labels[method] || method;
  };

  const getScoreBadgeClass = (score: number) => {
    if (score >= 80) return 'bg-green-600 text-white';
    if (score >= 60) return 'bg-yellow-500 text-white';
    return 'bg-gray-400 text-white';
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('reconciliation.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('reconciliation.description')}
          </p>
        </div>
        <Button onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </Button>
      </div>

      {/* Enriched KPIs — 6 cards (3x2 desktop, 2x3 mobile) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Card>
          <CardContent className="pt-3 pb-2">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-blue-100 rounded-lg">
                <Wallet className="h-4 w-4 text-blue-700" />
              </div>
              <div>
                <p className="text-xl font-bold">{spTotal}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{t('reconciliationPage.kpiEnriched.totalSystemPayments')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-2">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-green-100 rounded-lg">
                <CheckCircle2 className="h-4 w-4 text-green-700" />
              </div>
              <div>
                <p className="text-xl font-bold">{completedPayments}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{t('reconciliationPage.kpiEnriched.completedPayments')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-2">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-emerald-100 rounded-lg">
                <TrendingUp className="h-4 w-4 text-emerald-700" />
              </div>
              <div>
                <p className="text-xl font-bold">{formatCurrency(totalValidatedAmount)}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{t('reconciliationPage.kpiEnriched.totalValidatedAmount')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-2">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-purple-100 rounded-lg">
                <CreditCard className="h-4 w-4 text-purple-700" />
              </div>
              <div>
                <p className="text-xl font-bold">{statsData?.unreconciledCount ?? 0}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{t('reconciliationPage.kpiEnriched.totalBankTransactions')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-2">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-yellow-100 rounded-lg">
                <Banknote className="h-4 w-4 text-yellow-700" />
              </div>
              <div>
                <p className="text-xl font-bold">{suggestions.length}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{t('reconciliationPage.kpi.suggestions')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-2">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-indigo-100 rounded-lg">
                <Zap className="h-4 w-4 text-indigo-700" />
              </div>
              <div>
                <p className="text-xl font-bold">{highConfidenceSuggestions.length}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{t('reconciliationPage.kpi.highConfidence')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('reconciliationPage.loadError')}</p>
          </CardContent>
        </Card>
      )}

      {/* Smart Matching Suggestions */}
      {suggestions.length > 0 && (
        <Card className="border-green-200">
          <CardHeader className="py-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-green-800 text-base">
                  <Target className="h-4 w-4" />
                  {t('reconciliationPage.suggestions.title')}
                  <Badge variant="secondary" className="ml-2">{suggestions.length}</Badge>
                </CardTitle>
                <CardDescription className="text-xs">
                  {t('reconciliationPage.suggestions.description')}
                </CardDescription>
              </div>
              {highConfidenceSuggestions.length > 0 && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => autoMatchMutation.mutate(80)}
                  disabled={autoMatchMutation.isPending}
                >
                  {autoMatchMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                  )}
                  {t('reconciliationPage.suggestions.autoReconcile', { count: highConfidenceSuggestions.length })}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            {autoMatchMutation.isSuccess && (
              <div className="mb-3 p-2 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
                {t('reconciliationPage.suggestions.matchedResult', { count: autoMatchMutation.data.matchedCount })}
                {autoMatchMutation.data.skippedCount > 0 && (
                  <span className="text-yellow-700 ml-2">
                    {t('reconciliationPage.suggestions.skippedResult', { count: autoMatchMutation.data.skippedCount })}
                  </span>
                )}
              </div>
            )}
            <div className="space-y-2">
              {suggestions.slice(0, 10).map((suggestion: ReconciliationSuggestion) => (
                <div key={suggestion.transactionId} className="border rounded-lg p-2">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm">{suggestion.bankReference}</span>
                      <Badge variant="outline">{formatCurrency(suggestion.bankAmount, suggestion.bankCurrency)}</Badge>
                    </div>
                    <Badge className={cn('text-xs', getScoreBadgeClass(suggestion.bestScore))}>
                      {t('reconciliationPage.suggestions.score', { score: suggestion.bestScore })}
                    </Badge>
                  </div>
                  {suggestion.candidates.length > 0 && (
                    <div className="text-xs text-muted-foreground space-y-1 ml-4">
                      {suggestion.candidates.map((c, idx) => (
                        <div key={c.paymentId} className="flex items-center gap-2 flex-wrap">
                          <span className="text-muted-foreground">#{idx + 1}</span>
                          <span className="font-mono">{c.paymentReference}</span>
                          <span>{formatCurrency(c.paymentAmount)}</span>
                          <span className="italic">{c.payerName}</span>
                          <Badge variant="outline" className="text-[10px] h-4">
                            {c.reasons.map((r) => t(`reconciliationPage.reasons.${r}`)).join(', ')}
                          </Badge>
                          <Button
                            variant="outline"
                            size="sm"
                            className="ml-auto h-6 text-xs"
                            onClick={() => {
                              const tx = transactions.find(
                                (tr: BankTransaction) => tr.id === suggestion.transactionId
                              );
                              const bankTx: BankTransaction = tx || {
                                id: suggestion.transactionId,
                                bankReference: suggestion.bankReference,
                                amount: suggestion.bankAmount,
                                currency: suggestion.bankCurrency,
                                bankCode: suggestion.bankCode as BankTransaction['bankCode'],
                                status: 'unreconciled' as const,
                                transactionId: suggestion.bankReference,
                                receivedAt: suggestion.bankDate,
                                createdAt: suggestion.bankDate,
                              };
                              openReconcileDialog(bankTx, {
                                id: c.paymentId,
                                paymentReference: c.paymentReference,
                                totalAmount: c.paymentAmount,
                                currency: suggestion.bankCurrency,
                                paymentMethod: c.paymentMethod,
                                paymentDate: c.paymentDate,
                                payerName: c.payerName,
                                payerEmail: '',
                              });
                            }}
                          >
                            <Link2 className="h-3 w-3 mr-1" />
                            {t('reconciliationPage.reconcileButton')}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bank Transactions Table — with status filter */}
      <Card>
        <CardHeader className="py-3">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Link2 className="h-4 w-4" />
                {t('reconciliationPage.tableTitle')}
                {totalTransactions > 0 && (
                  <Badge variant="secondary" className="ml-2">{totalTransactions}</Badge>
                )}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('reconciliationPage.tableDescription')}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Select value={bankTxStatus} onValueChange={setBankTxStatus}>
                <SelectTrigger className="w-[160px] h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="unreconciled">{t('reconciliationPage.statusFilter.unreconciled')}</SelectItem>
                  <SelectItem value="reconciled">{t('reconciliationPage.statusFilter.reconciled')}</SelectItem>
                  <SelectItem value="all">{t('reconciliationPage.statusFilter.all')}</SelectItem>
                </SelectContent>
              </Select>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder={t('reconciliationPage.searchPlaceholder')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 h-9 w-[250px]"
                />
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : transactions.length === 0 ? (
            debouncedSearch ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Search className="h-10 w-10 text-muted-foreground mb-3" />
                <h3 className="text-base font-semibold">{t('reconciliationPage.noSearchResults')}</h3>
                <p className="text-sm text-muted-foreground">
                  {t('reconciliationPage.noSearchResultsDescription')}
                </p>
              </div>
            ) : bankTxStatus === 'unreconciled' ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <CheckCircle2 className="h-10 w-10 text-green-500 mb-3" />
                <h3 className="text-base font-semibold">{t('reconciliationPage.allReconciled')}</h3>
                <p className="text-sm text-muted-foreground">
                  {t('reconciliationPage.allReconciledDescription')}
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <CreditCard className="h-10 w-10 text-muted-foreground mb-3" />
                <h3 className="text-base font-semibold">{t('reconciliationPage.noBankTransactions')}</h3>
                <p className="text-sm text-muted-foreground">
                  {t('reconciliationPage.noBankTransactionsDescription')}
                </p>
              </div>
            )
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('reconciliationPage.table.bankReference')}</TableHead>
                      <TableHead>{t('reconciliationPage.table.accountHolder')}</TableHead>
                      <TableHead>{t('reconciliationPage.table.amount')}</TableHead>
                      <TableHead>{t('reconciliationPage.table.bank')}</TableHead>
                      <TableHead>{t('reconciliationPage.table.status')}</TableHead>
                      <TableHead>{t('reconciliationPage.table.date')}</TableHead>
                      <TableHead className="text-right">{t('reconciliationPage.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((tx: BankTransaction) => (
                      <TableRow key={tx.id}>
                        <TableCell className="font-mono text-sm">{tx.bankReference}</TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium">{tx.accountHolderName || 'N/A'}</p>
                            {tx.accountNumber && (
                              <p className="text-xs text-muted-foreground">{tx.accountNumber}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-bold">{formatCurrency(tx.amount, tx.currency)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{tx.bankCode || 'BANGE'}</Badge>
                        </TableCell>
                        <TableCell>{getStatusBadge(tx.status)}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(tx.bankTransactionDate || tx.createdAt)}
                        </TableCell>
                        <TableCell className="text-right">
                          {tx.status === 'unreconciled' && (
                            <Button
                              variant="default"
                              size="sm"
                              onClick={() => openReconcileDialog(tx)}
                              disabled={isReconciling}
                            >
                              <Link2 className="mr-2 h-4 w-4" />
                              {t('reconciliationPage.reconcileButton')}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t">
                  <p className="text-sm text-muted-foreground">
                    {t('reconciliationPage.pagination.showing', {
                      from: (page - 1) * PAGE_SIZE + 1,
                      to: Math.min(page * PAGE_SIZE, totalTransactions),
                      total: totalTransactions,
                    })}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm font-medium px-2">{page} / {totalPages}</span>
                    <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* System Payments Section */}
      <Card>
        <CardHeader className="py-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Wallet className="h-4 w-4" />
                {t('reconciliationPage.systemPayments.title')}
                {spTotal > 0 && (
                  <Badge variant="secondary" className="ml-2">{spTotal}</Badge>
                )}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('reconciliationPage.systemPayments.description')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {spLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : systemPayments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Wallet className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="text-base font-semibold">{t('reconciliationPage.systemPayments.empty')}</h3>
              <p className="text-sm text-muted-foreground">
                {t('reconciliationPage.systemPayments.emptyDescription')}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('reconciliationPage.systemPayments.table.reference')}</TableHead>
                      <TableHead>{t('reconciliationPage.systemPayments.table.method')}</TableHead>
                      <TableHead>{t('reconciliationPage.systemPayments.table.amount')}</TableHead>
                      <TableHead>{t('reconciliationPage.systemPayments.table.status')}</TableHead>
                      <TableHead>{t('reconciliationPage.systemPayments.table.reconciled')}</TableHead>
                      <TableHead>{t('reconciliationPage.systemPayments.table.validatedAt')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {systemPayments.map((sp: PendingPayment) => (
                      <TableRow key={sp.id}>
                        <TableCell className="font-mono text-sm">{sp.paymentReference}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{getPaymentMethodLabel(sp.paymentMethod as string)}</Badge>
                        </TableCell>
                        <TableCell className="font-bold">{formatCurrency(sp.totalAmount, sp.currency)}</TableCell>
                        <TableCell>{getWorkflowStatusBadge(sp.workflowStatus as string)}</TableCell>
                        <TableCell>
                          {sp.bankTransactionId ? (
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                          ) : (
                            <Minus className="h-4 w-4 text-muted-foreground" />
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(sp.validatedAt)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* System payments pagination */}
              {spTotalPages > 1 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t">
                  <p className="text-sm text-muted-foreground">
                    {t('reconciliationPage.pagination.showing', {
                      from: (spPage - 1) * SP_PAGE_SIZE + 1,
                      to: Math.min(spPage * SP_PAGE_SIZE, spTotal),
                      total: spTotal,
                    })}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setSpPage(p => Math.max(1, p - 1))} disabled={spPage <= 1}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm font-medium px-2">{spPage} / {spTotalPages}</span>
                    <Button variant="outline" size="sm" onClick={() => setSpPage(p => Math.min(spTotalPages, p + 1))} disabled={spPage >= spTotalPages}>
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Reconciliation Dialog (C3: ComboBox replaces text input) */}
      <Dialog open={isReconcileDialogOpen} onOpenChange={setIsReconcileDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-blue-500" />
              {t('reconciliationPage.dialog.title')}
            </DialogTitle>
            <DialogDescription>
              {t('reconciliationPage.dialog.description')}
            </DialogDescription>
          </DialogHeader>

          {selectedTransaction && (
            <div className="space-y-4 py-4">
              {/* Transaction Details */}
              <div className="bg-muted/50 p-4 rounded-lg space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('reconciliationPage.dialog.bankReferenceLabel')}:</span>
                  <span className="font-mono">{selectedTransaction.bankReference}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('reconciliationPage.dialog.amountLabel')}:</span>
                  <span className="font-bold text-lg">
                    {formatCurrency(selectedTransaction.amount, selectedTransaction.currency)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('reconciliationPage.dialog.accountHolderLabel')}:</span>
                  <span>{selectedTransaction.accountHolderName || 'N/A'}</span>
                </div>
                {selectedTransaction.accountNumber && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('reconciliationPage.dialog.accountNumberLabel')}:</span>
                    <span>{selectedTransaction.accountNumber}</span>
                  </div>
                )}
              </div>

              {/* Payment Search ComboBox */}
              <div className="space-y-2">
                <Label>{t('reconciliationPage.dialog.paymentReferenceLabel')} *</Label>
                {selectedPayment ? (
                  <div className="border rounded-lg p-3 bg-green-50 border-green-200">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-mono text-sm font-medium">{selectedPayment.paymentReference}</p>
                        <p className="text-xs text-muted-foreground">
                          {selectedPayment.payerName} — {formatCurrency(selectedPayment.totalAmount, selectedPayment.currency)}
                        </p>
                        {selectedPayment.paymentDate && (
                          <p className="text-xs text-muted-foreground">{formatDate(selectedPayment.paymentDate)}</p>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedPayment(null)}
                      >
                        {t('reconciliationPage.dialog.changePayment')}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Popover open={paymentSearchOpen} onOpenChange={setPaymentSearchOpen}>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        role="combobox"
                        className="w-full justify-between font-normal"
                      >
                        {t('reconciliationPage.dialog.searchPayments')}
                        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[450px] p-0" align="start">
                      <Command shouldFilter={false}>
                        <CommandInput
                          placeholder={t('reconciliationPage.dialog.searchPayments')}
                          value={paymentSearchQuery}
                          onValueChange={setPaymentSearchQuery}
                        />
                        <CommandList>
                          <CommandEmpty>
                            {paymentSearchQuery.length < 2
                              ? t('reconciliationPage.dialog.typeToSearch')
                              : t('reconciliationPage.dialog.noPaymentsFound')
                            }
                          </CommandEmpty>
                          {(searchPaymentResults || []).map((p) => (
                            <CommandItem
                              key={p.id}
                              value={p.id}
                              onSelect={() => {
                                setSelectedPayment(p);
                                setPaymentSearchOpen(false);
                              }}
                              className="flex flex-col items-start gap-1 py-2"
                            >
                              <div className="flex items-center gap-2 w-full">
                                <span className="font-mono text-sm font-medium">{p.paymentReference}</span>
                                <span className="ml-auto font-bold">{formatCurrency(p.totalAmount, p.currency)}</span>
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {p.payerName} {p.paymentDate ? `— ${formatDate(p.paymentDate)}` : ''}
                              </div>
                            </CommandItem>
                          ))}
                        </CommandList>
                      </Command>
                    </PopoverContent>
                  </Popover>
                )}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsReconcileDialogOpen(false)}
              disabled={isReconciling}
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleReconcile}
              disabled={isReconciling || !selectedPayment}
            >
              {isReconciling ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('reconciliationPage.dialog.reconciling')}
                </>
              ) : (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  {t('reconciliationPage.dialog.confirmButton')}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
