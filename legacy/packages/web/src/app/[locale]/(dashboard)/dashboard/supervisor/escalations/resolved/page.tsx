'use client';

/**
 * Resolved Escalations Page - Supervisor View
 * Read-only view of recently resolved escalations with split-view details
 *
 * @route /[locale]/dashboard/supervisor/escalations/resolved
 * @date 2026-02-21
 */

import React, { useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
import {
  Loader2,
  AlertCircle,
  ArrowLeft,
  Search,
  RefreshCw,
  CheckCircle,
  Clock,
  User,
  FileText,
  AlertTriangle,
} from 'lucide-react';
import apiClient from '@/core/api/client';
import Link from 'next/link';
import { formatDistanceToNow, format } from 'date-fns';
import { es, fr, enUS } from 'date-fns/locale';
import type { Escalation } from '../../types';
import { getPriorityLevel, PRIORITY_COLORS } from '../../types';

export default function ResolvedEscalationsPage() {
  const locale = useLocale();
  const t = useTranslations('supervisor');
  const tCommon = useTranslations('common');

  const dateLocale = locale === 'es' ? es : locale === 'fr' ? fr : enUS;

  const [searchTerm, setSearchTerm] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [selectedEscalation, setSelectedEscalation] = useState<Escalation | null>(null);

  // Fetch resolved escalations
  const { data: escalations, isLoading, isError, error, refetch } = useQuery<Escalation[]>({
    queryKey: ['supervisor', 'escalations', 'resolved'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/escalations', {
        params: { status_filter: 'resolved', include_resolved: true }
      });
      return response.data;
    },
  });

  // Filter
  const filtered = escalations?.filter((esc) => {
    const matchesSearch =
      esc.case_reference?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      esc.escalated_by_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      esc.reason?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesPriority =
      priorityFilter === 'all' || getPriorityLevel(esc.priority_score) === priorityFilter;
    return matchesSearch && matchesPriority;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">{tCommon('loading')}</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            {tCommon('error')}
          </CardTitle>
          <CardDescription>
            {(error as Error)?.message || tCommon('errorGeneric')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => refetch()}>
            {tCommon('retry')}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/supervisor/escalations/pending`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <CheckCircle className="h-6 w-6 text-green-500" />
            {t('nav.resolvedEscalations')}
          </h1>
          <p className="text-muted-foreground">
            {filtered?.length || 0} {t('escalations.resolved').toLowerCase()}
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          {tCommon('refresh')}
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4 items-center">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={tCommon('search')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('escalations.priority.all', { defaultValue: 'Todas' })}</SelectItem>
                <SelectItem value="critical">{t('escalations.priority.critical')}</SelectItem>
                <SelectItem value="high">{t('escalations.priority.high')}</SelectItem>
                <SelectItem value="medium">{t('escalations.priority.medium')}</SelectItem>
                <SelectItem value="low">{t('escalations.priority.low')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Split View: Table + Details */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Table (60%) */}
        <Card className="lg:col-span-3">
          <CardContent className="pt-6">
            {!filtered?.length ? (
              <div className="text-center py-12 text-muted-foreground">
                <CheckCircle className="h-12 w-12 mx-auto mb-4 text-green-300" />
                <p>{t('escalations.noResolved', { defaultValue: 'No hay escalaciones resueltas' })}</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('escalations.reference')}</TableHead>
                    <TableHead>{t('escalations.priority.label', { defaultValue: 'Prioridad' })}</TableHead>
                    <TableHead>{t('escalations.escalatedBy')}</TableHead>
                    <TableHead>{t('escalations.escalatedAt')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((esc) => {
                    const priority = getPriorityLevel(esc.priority_score);
                    const isSelected = selectedEscalation?.id === esc.id;
                    return (
                      <TableRow
                        key={esc.id}
                        className={`cursor-pointer transition-colors ${isSelected ? 'bg-muted/50' : 'hover:bg-muted/30'}`}
                        onClick={() => setSelectedEscalation(esc)}
                      >
                        <TableCell>
                          <span className="font-mono text-sm">{esc.case_reference}</span>
                          <p className="text-xs text-muted-foreground">{t('workflowNames.' + esc.case_type)}</p>
                        </TableCell>
                        <TableCell>
                          <Badge className={PRIORITY_COLORS[priority]}>
                            {t(`escalations.priority.${priority}`)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm">{esc.escalated_by_name}</span>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-muted-foreground">
                            {formatDistanceToNow(new Date(esc.escalated_at), { addSuffix: true, locale: dateLocale })}
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Details Panel (40%) */}
        <Card className="lg:col-span-2">
          <CardContent className="pt-6">
            {!selectedEscalation ? (
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>{t('escalations.selectToView', { defaultValue: 'Seleccionar una escalación para ver detalles' })}</p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Reference + Status */}
                <div>
                  <h3 className="text-lg font-semibold">{selectedEscalation.case_reference}</h3>
                  <Badge variant="secondary" className="mt-1">{t('workflowNames.' + selectedEscalation.case_type)}</Badge>
                </div>

                {/* Priority */}
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">{t('escalations.priority.label', { defaultValue: 'Prioridad' })}:</span>
                  <Badge className={PRIORITY_COLORS[getPriorityLevel(selectedEscalation.priority_score)]}>
                    {t(`escalations.priority.${getPriorityLevel(selectedEscalation.priority_score)}`)}
                  </Badge>
                </div>

                {/* Reason */}
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">{t('escalations.reason')}</p>
                  <p className="text-sm bg-muted/50 p-3 rounded-md">{selectedEscalation.reason || '-'}</p>
                </div>

                {/* Escalated by */}
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{selectedEscalation.escalated_by_name}</p>
                    <p className="text-xs text-muted-foreground">{selectedEscalation.escalated_by_email}</p>
                  </div>
                </div>

                {/* Escalated at */}
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{t('escalations.escalatedAt')}</p>
                    <p className="text-xs text-muted-foreground">
                      {format(new Date(selectedEscalation.escalated_at), 'PPp', { locale: dateLocale })}
                    </p>
                  </div>
                </div>

                {/* Assigned to */}
                {selectedEscalation.assigned_to_name && (
                  <div className="flex items-center gap-2">
                    <User className="h-4 w-4 text-green-500" />
                    <div>
                      <p className="text-sm font-medium">{t('escalations.assignedTo')}</p>
                      <p className="text-xs text-muted-foreground">{selectedEscalation.assigned_to_name}</p>
                    </div>
                  </div>
                )}

                {/* Status */}
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-green-600 font-medium">{t('escalations.resolved')}</span>
                </div>

                {/* Request status */}
                <div className="pt-2 border-t">
                  <p className="text-sm font-medium text-muted-foreground mb-1">{tCommon('status')}</p>
                  <Badge variant="outline">{selectedEscalation.status}</Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
