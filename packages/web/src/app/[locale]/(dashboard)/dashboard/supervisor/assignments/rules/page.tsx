'use client';

/**
 * Assignment Rules Management Page
 * List and manage auto-assignment rules.
 * Aligned with backend: conditions/actions JSONB, status enum, server-side pagination.
 *
 * Backend scoping: GET /supervisor/rules already filters by supervisor's entity
 * via agent_context — no additional frontend filtering needed.
 *
 * @route /[locale]/dashboard/supervisor/assignments/rules
 */

import React, { useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Loader2, AlertCircle, Plus, Pencil, Trash2, Settings2, ArrowLeft,
  Search, RefreshCw, Play, Pause, ChevronLeft, ChevronRight, Zap, Target, TrendingUp,
} from 'lucide-react';
import apiClient from '@/core/api/client';
import Link from 'next/link';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';
import { es, fr, enUS } from 'date-fns/locale';

import type { AssignmentRule, RuleStatus } from '../../types';
import { RULE_STATUS_COLORS, STRATEGY_COLORS } from '../../types';

const PAGE_SIZE = 20;

export default function AssignmentRulesPage() {
  const locale = useLocale();
  const queryClient = useQueryClient();
  const t = useTranslations('supervisor.rules');
  const tCommon = useTranslations('common');

  const dateLocale = locale === 'es' ? es : locale === 'fr' ? fr : enUS;

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [deleteConfirmRule, setDeleteConfirmRule] = useState<AssignmentRule | null>(null);

  // Server-side paginated fetch — backend already scopes to supervisor's entity
  const { data: rulesResponse, isLoading, isError, error, refetch } = useQuery<{
    items: AssignmentRule[];
    total: number;
    page: number;
    page_size: number;
  }>({
    queryKey: ['supervisor', 'rules', statusFilter, currentPage, searchTerm],
    queryFn: async () => {
      const params = new URLSearchParams();
      // Backend param is "status_filter" (not "status")
      if (statusFilter !== 'all') {
        params.append('status_filter', statusFilter);
      }
      params.append('page', String(currentPage));
      params.append('page_size', String(PAGE_SIZE));
      const response = await apiClient.get(`/supervisor/rules?${params.toString()}`);
      return response.data;
    },
  });

  const rules = rulesResponse?.items ?? [];
  const total = rulesResponse?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Client-side search on the current page (server doesn't have search param)
  const filteredRules = searchTerm
    ? rules.filter((rule) =>
        rule.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (rule.description?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false)
      )
    : rules;

  // Activate/Deactivate mutations
  const activateMutation = useMutation({
    mutationFn: async (ruleId: string) => {
      const response = await apiClient.post(`/supervisor/rules/${ruleId}/activate`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'rules'] });
      toast.success(t('activated'));
    },
    onError: (err: Error) => {
      toast.error(err.message || tCommon('error'));
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async (ruleId: string) => {
      const response = await apiClient.post(`/supervisor/rules/${ruleId}/deactivate`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'rules'] });
      toast.success(t('deactivated'));
    },
    onError: (err: Error) => {
      toast.error(err.message || tCommon('error'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (ruleId: string) => {
      await apiClient.delete(`/supervisor/rules/${ruleId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'rules'] });
      setDeleteConfirmRule(null);
      toast.success(t('deleted'));
    },
    onError: (err: Error) => {
      toast.error(err.message || tCommon('error'));
    },
  });

  const handleToggleActive = (rule: AssignmentRule) => {
    if (rule.status === 'active') {
      deactivateMutation.mutate(rule.id);
    } else {
      activateMutation.mutate(rule.id);
    }
  };

  const formatConditions = (conditions: AssignmentRule['conditions']): string => {
    if (!conditions || Object.keys(conditions).length === 0) return t('noConditions');
    const parts: string[] = [];
    if (conditions.item_types?.length) {
      parts.push(`${t('workflowTypes')}: ${conditions.item_types.length}`);
    }
    if (conditions.payment_methods?.length) {
      parts.push(`${t('paymentMethod')}: ${conditions.payment_methods.length}`);
    }
    if (conditions.payment_types?.length) {
      parts.push(`${t('paymentType')}: ${conditions.payment_types.length}`);
    }
    if (conditions.has_penalties) parts.push(t('hasPenalties'));
    if (conditions.min_amount !== undefined) parts.push(`Min: ${conditions.min_amount.toLocaleString()} XAF`);
    if (conditions.max_amount !== undefined) parts.push(`Max: ${conditions.max_amount.toLocaleString()} XAF`);
    if (conditions.min_priority !== undefined) parts.push(`${t('priority')} >= ${conditions.min_priority}`);
    if (conditions.entity_location_id) parts.push(t('entityLocation'));
    return parts.join(' | ') || t('noConditions');
  };

  const getStrategyKey = (actions: AssignmentRule['actions']): string => {
    return actions?.selection_strategy || 'load_balance';
  };

  // Stats from current page data (informational only)
  const stats = {
    total,
    active: rules.filter((r) => r.status === 'active').length,
    draft: rules.filter((r) => r.status === 'draft').length,
    avgSuccessRate: rules.length
      ? (rules.reduce((sum, r) => sum + (r.success_rate || 0), 0) / rules.length * 100).toFixed(0)
      : '0',
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" /> {tCommon('error')}
          </CardTitle>
          <CardDescription>{(error as Error)?.message || tCommon('errorGeneric')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => refetch()}>{tCommon('retry')}</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/supervisor`}>
          <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Settings2 className="h-6 w-6" /> {t('title')}
          </h1>
          <p className="text-muted-foreground text-sm">{t('description')}</p>
        </div>
        <Link href={`/${locale}/dashboard/supervisor/assignments/rules/new`}>
          <Button><Plus className="h-4 w-4 mr-2" /> {t('createRule')}</Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid gap-3 grid-cols-4">
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">{tCommon('total')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold text-green-600">{stats.active}</div>
            <p className="text-xs text-muted-foreground">{t('status_active')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold text-yellow-600">{stats.draft}</div>
            <p className="text-xs text-muted-foreground">{t('drafts')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-1">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <span className="text-2xl font-bold">{stats.avgSuccessRate}%</span>
            </div>
            <p className="text-xs text-muted-foreground">{t('avgSuccessRate')}</p>
          </CardContent>
        </Card>
      </div>

      {/* Search and filters */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={tCommon('search')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setCurrentPage(1); }}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder={tCommon('status')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{tCommon('all')}</SelectItem>
            <SelectItem value="active">{t('status_active')}</SelectItem>
            <SelectItem value="inactive">{t('status_inactive')}</SelectItem>
            <SelectItem value="draft">{t('status_draft')}</SelectItem>
            <SelectItem value="archived">{t('status_archived')}</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="icon" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Rules Table */}
      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('name')}</TableHead>
                <TableHead>{t('conditionsTitle')}</TableHead>
                <TableHead>{t('assignmentStrategy')}</TableHead>
                <TableHead className="text-center">{t('priority')}</TableHead>
                <TableHead>{tCommon('status')}</TableHead>
                <TableHead className="text-center">{t('applications')}</TableHead>
                <TableHead className="text-center">{t('successRate')}</TableHead>
                <TableHead>{tCommon('updated')}</TableHead>
                <TableHead className="text-right">{tCommon('actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRules.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-12 text-muted-foreground">
                    {searchTerm ? (
                      tCommon('noResults')
                    ) : (
                      <div className="space-y-2">
                        <Zap className="h-8 w-8 mx-auto text-muted-foreground/50" />
                        <p>{t('noRules')}</p>
                        <p className="text-xs">{t('defaultLoadBalance')}</p>
                        <Link href={`/${locale}/dashboard/supervisor/assignments/rules/new`}>
                          <Button size="sm" className="mt-2">
                            <Plus className="h-4 w-4 mr-1" /> {t('createFirstRule')}
                          </Button>
                        </Link>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ) : (
                filteredRules.map((rule) => {
                  const strategyKey = getStrategyKey(rule.actions);
                  return (
                    <TableRow key={rule.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{rule.name}</p>
                          {rule.description && (
                            <p className="text-xs text-muted-foreground truncate max-w-[180px]">{rule.description}</p>
                          )}
                          <p className="text-[10px] text-muted-foreground">
                            {rule.entity_type}{rule.entity_id ? ` / ${rule.entity_id}` : ''}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">{formatConditions(rule.conditions)}</span>
                      </TableCell>
                      <TableCell>
                        <Badge className={STRATEGY_COLORS[strategyKey] || 'bg-gray-100 text-gray-800'}>
                          <Target className="h-3 w-3 mr-1" />
                          {t(`strategy_${strategyKey}`)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="secondary">{rule.priority}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={RULE_STATUS_COLORS[rule.status as RuleStatus] || ''}>
                          {t(`status_${rule.status}`)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center text-sm">
                        {rule.times_applied}
                        {rule.times_matched > 0 && (
                          <span className="text-xs text-muted-foreground ml-1">
                            ({rule.times_matched} {t('matches')})
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        <span className={`text-sm font-medium ${
                          rule.success_rate >= 0.8 ? 'text-green-600'
                            : rule.success_rate >= 0.5 ? 'text-yellow-600'
                            : rule.success_rate > 0 ? 'text-red-600'
                            : 'text-muted-foreground'
                        }`}>
                          {rule.times_applied > 0 ? `${(rule.success_rate * 100).toFixed(0)}%` : '\u2014'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {rule.updated_at
                            ? formatDistanceToNow(new Date(rule.updated_at), { addSuffix: true, locale: dateLocale })
                            : formatDistanceToNow(new Date(rule.created_at), { addSuffix: true, locale: dateLocale })}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost" size="icon"
                            onClick={() => handleToggleActive(rule)}
                            disabled={activateMutation.isPending || deactivateMutation.isPending}
                            title={rule.status === 'active' ? t('deactivate') : t('activate')}
                          >
                            {rule.status === 'active'
                              ? <Pause className="h-4 w-4 text-yellow-600" />
                              : <Play className="h-4 w-4 text-green-600" />}
                          </Button>
                          <Link href={`/${locale}/dashboard/supervisor/assignments/rules/${rule.id}/edit`}>
                            <Button variant="ghost" size="icon"><Pencil className="h-4 w-4" /></Button>
                          </Link>
                          <Button
                            variant="ghost" size="icon"
                            onClick={() => setDeleteConfirmRule(rule)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>

          {/* Server-side Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t">
              <p className="text-sm text-muted-foreground">
                {(currentPage - 1) * PAGE_SIZE + 1}-{Math.min(currentPage * PAGE_SIZE, total)} {t('of')} {total}
              </p>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} disabled={currentPage === 1}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                  const start = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
                  return start + i;
                }).filter(p => p <= totalPages).map((page) => (
                  <Button key={page} variant={currentPage === page ? 'default' : 'outline'} size="sm" onClick={() => setCurrentPage(page)} className="w-8">
                    {page}
                  </Button>
                ))}
                <Button variant="outline" size="sm" onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteConfirmRule} onOpenChange={() => setDeleteConfirmRule(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteConfirmRule && deleteMutation.mutate(deleteConfirmRule.id)}
              disabled={deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
