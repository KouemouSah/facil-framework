'use client';

/**
 * Supervisor Reports Page
 * Centralized reports with 3 tabs: Overview, Workload, Exports
 * Consumes existing backend endpoints — no new API needed
 *
 * @route /[locale]/dashboard/supervisor/reports
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
import { Progress } from '@/components/ui/progress';
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Loader2,
  AlertCircle,
  ArrowLeft,
  Users,
  TrendingUp,
  Clock,
  Target,
  Download,
  BarChart3,
  FileBarChart,
  Award,
  Scale,
} from 'lucide-react';
import { toast } from 'sonner';
import apiClient from '@/core/api/client';
import Link from 'next/link';
import type {
  SupervisorDashboardStats,
  AgentListItem,
  RuleEffectivenessItem,
  WorkloadBalanceResponse,
} from '../types';
import { getBalanceColor, getBalanceBadgeKey, WORKLOAD_STATUS_COLORS, formatSuccessRate, getSuccessRateColor } from '../types';

// =============================================================================
// ERROR CARD — reusable per-tab error component
// =============================================================================

function TabErrorCard({ error, onRetry, tCommon }: { error: Error | null; onRetry: () => void; tCommon: (key: string) => string }) {
  return (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-5 w-5" />
          {tCommon('error')}
        </CardTitle>
        <CardDescription>
          {error?.message || tCommon('errorGeneric')}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" onClick={onRetry}>
          {tCommon('retry')}
        </Button>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function SupervisorReportsPage() {
  const locale = useLocale();
  const t = useTranslations('supervisor');
  const tCommon = useTranslations('common');

  const [activeTab, setActiveTab] = useState('overview');
  const [exportPeriod, setExportPeriod] = useState('30');
  const [isExporting, setIsExporting] = useState(false);

  // --- Queries ---

  const {
    data: stats,
    isLoading: statsLoading,
    isError: statsError,
    error: statsErr,
    refetch: refetchStats,
  } = useQuery<SupervisorDashboardStats>({
    queryKey: ['supervisor', 'dashboard', 'reports'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/dashboard');
      return response.data;
    },
  });

  const {
    data: agents,
    isLoading: agentsLoading,
    isError: agentsError,
    error: agentsErr,
    refetch: refetchAgents,
  } = useQuery<AgentListItem[]>({
    queryKey: ['supervisor', 'agents', 'reports'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/agents');
      return response.data;
    },
  });

  const {
    data: rulesReport,
    isLoading: rulesLoading,
    isError: rulesError,
    error: rulesErr,
    refetch: refetchRules,
  } = useQuery<RuleEffectivenessItem[]>({
    queryKey: ['supervisor', 'rules-effectiveness'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/rules/effectiveness/report', {
        params: { min_applications: 5 },
      });
      return response.data;
    },
    enabled: activeTab === 'overview',
  });

  const {
    data: workload,
    isLoading: workloadLoading,
    isError: workloadError,
    error: workloadErr,
    refetch: refetchWorkload,
  } = useQuery<WorkloadBalanceResponse>({
    queryKey: ['supervisor', 'workload-balance', 'reports'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/workload/balance');
      return response.data;
    },
    enabled: activeTab === 'workload',
  });

  // --- Export handler ---

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const response = await apiClient.get('/supervisor/export/assignments', {
        params: { format: 'csv', period_days: parseInt(exportPeriod) },
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `assignments_export_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(t('reports.exportSuccess', { defaultValue: 'Exportación completada' }));
    } catch {
      toast.error(t('reports.exportError', { defaultValue: 'Error al exportar' }));
    } finally {
      setIsExporting(false);
    }
  };

  // --- Derived data ---

  const topAgents = agents
    ?.filter((a) => a.success_rate > 0)
    .sort((a, b) => b.success_rate - a.success_rate)
    .slice(0, 5);

  const capacityBuckets = agents
    ? [
        { range: '0-25%', count: agents.filter((a) => a.capacity_percentage <= 25).length, color: 'bg-green-500' },
        { range: '25-50%', count: agents.filter((a) => a.capacity_percentage > 25 && a.capacity_percentage <= 50).length, color: 'bg-blue-500' },
        { range: '50-75%', count: agents.filter((a) => a.capacity_percentage > 50 && a.capacity_percentage <= 75).length, color: 'bg-yellow-500' },
        { range: '75-100%', count: agents.filter((a) => a.capacity_percentage > 75).length, color: 'bg-red-500' },
      ]
    : [];

  // --- Global loading (only for initial page load) ---

  if (statsLoading && agentsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">{tCommon('loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/supervisor`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FileBarChart className="h-6 w-6" />
            {t('reports.title')}
          </h1>
          <p className="text-muted-foreground">
            {t('reports.description')}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="overview">{t('reports.overview')}</TabsTrigger>
          <TabsTrigger value="workload">{t('reports.workloadTab')}</TabsTrigger>
          <TabsTrigger value="exports">{t('reports.exportsTab')}</TabsTrigger>
        </TabsList>

        {/* =============== TAB 1: OVERVIEW =============== */}
        <TabsContent value="overview" className="space-y-6">
          {/* Per-tab error: stats */}
          {statsError && (
            <TabErrorCard error={statsErr as Error} onRetry={() => refetchStats()} tCommon={tCommon} />
          )}

          {/* Stats Cards */}
          {stats && (
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">{t('stats.teamActive', { defaultValue: 'Agentes Activos' })}</CardTitle>
                  <Users className="h-4 w-4 text-blue-500" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.team.activeAgents}</div>
                  <p className="text-xs text-muted-foreground">
                    / {stats.team.totalAgents} {t('team.totalAgents', { defaultValue: 'total' })}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">{t('stats.slaCompliance', { defaultValue: 'SLA Compliance' })}</CardTitle>
                  <Target className="h-4 w-4 text-green-500" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.performance.slaCompliance}%</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">{t('stats.avgResponseTime', { defaultValue: 'Tiempo Resp.' })}</CardTitle>
                  <Clock className="h-4 w-4 text-orange-500" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.performance.avgResponseTime}h</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">{t('stats.qualityScore', { defaultValue: 'Calidad' })}</CardTitle>
                  <TrendingUp className="h-4 w-4 text-purple-500" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {stats.performance.qualityScore > 0
                      ? `${stats.performance.qualityScore}%`
                      : <span className="text-muted-foreground">N/A</span>}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Per-tab error: agents */}
          {agentsError && (
            <TabErrorCard error={agentsErr as Error} onRetry={() => refetchAgents()} tCommon={tCommon} />
          )}

          {/* Top Agents + Rules Effectiveness side by side */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Top Agents */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Award className="h-5 w-5 text-yellow-500" />
                  {t('reports.topAgents')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {agentsLoading ? (
                  <div className="flex justify-center py-4"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
                ) : !topAgents?.length ? (
                  <p className="text-center text-muted-foreground py-4">{tCommon('noData')}</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>#</TableHead>
                        <TableHead>{t('team.agent', { defaultValue: 'Agente' })}</TableHead>
                        <TableHead>{t('team.successRate', { defaultValue: 'Éxito' })}</TableHead>
                        <TableHead>{t('team.assignments', { defaultValue: 'Asignaciones' })}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {topAgents.map((agent, i) => (
                        <TableRow key={agent.agent_profile_id || agent.agent_id}>
                          <TableCell className="font-medium">{i + 1}</TableCell>
                          <TableCell>
                            <p className="font-medium">{agent.agent_name}</p>
                            <p className="text-xs text-muted-foreground">{agent.agent_email}</p>
                          </TableCell>
                          <TableCell>
                            <span className={`${getSuccessRateColor(agent.success_rate)} ${agent.success_rate >= 0.8 ? 'font-medium' : ''}`}>
                              {formatSuccessRate(agent.success_rate)}
                            </span>
                          </TableCell>
                          <TableCell>{agent.current_assignments}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            {/* Rules Effectiveness */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-indigo-500" />
                  {t('reports.rulesEffectiveness')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {rulesError ? (
                  <TabErrorCard error={rulesErr as Error} onRetry={() => refetchRules()} tCommon={tCommon} />
                ) : rulesLoading ? (
                  <div className="flex justify-center py-4"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
                ) : !rulesReport?.length ? (
                  <p className="text-center text-muted-foreground py-4">
                    {t('reports.noRules')}
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('rules.title', { defaultValue: 'Regla' })}</TableHead>
                        <TableHead>{t('reports.timesApplied')}</TableHead>
                        <TableHead>{t('reports.matchRate')}</TableHead>
                        <TableHead>{t('reports.effectivenessScore')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rulesReport.slice(0, 5).map((rule) => (
                        <TableRow key={rule.rule_id}>
                          <TableCell>
                            <p className="font-medium text-sm">{rule.rule_name}</p>
                            <p className="text-xs text-muted-foreground">P{rule.priority}</p>
                          </TableCell>
                          <TableCell>{rule.times_applied}</TableCell>
                          <TableCell>{rule.application_rate.toFixed(0)}%</TableCell>
                          <TableCell>
                            <span className={rule.effectiveness_score >= 80 ? 'text-green-600 font-medium' : rule.effectiveness_score >= 50 ? 'text-yellow-600' : 'text-red-600'}>
                              {rule.effectiveness_score.toFixed(0)}%
                            </span>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* =============== TAB 2: WORKLOAD =============== */}
        <TabsContent value="workload" className="space-y-6">
          {workloadError ? (
            <TabErrorCard error={workloadErr as Error} onRetry={() => refetchWorkload()} tCommon={tCommon} />
          ) : workloadLoading || !workload ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* Balance Score + Capacity Distribution */}
              <div className="grid gap-4 md:grid-cols-3">
                <Card className="md:col-span-1">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Scale className="h-5 w-5" />
                      Balance Score
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-center">
                    <p className={`text-5xl font-bold ${getBalanceColor(workload.report.balance_score)}`}>
                      {workload.report.balance_score.toFixed(0)}
                    </p>
                    <Badge className={`mt-2 ${getBalanceBadgeKey(workload.report.balance_score).color}`}>
                      {t(getBalanceBadgeKey(workload.report.balance_score).key)}
                    </Badge>
                  </CardContent>
                </Card>

                <Card className="md:col-span-2">
                  <CardHeader>
                    <CardTitle>{t('reports.capacityDistribution')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {capacityBuckets.map((bucket) => (
                        <div key={bucket.range} className="flex items-center gap-3">
                          <span className="text-sm w-16">{bucket.range}</span>
                          <div className="flex-1">
                            <Progress
                              value={agents?.length ? (bucket.count / agents.length) * 100 : 0}
                              className={`h-4 [&>div]:${bucket.color}`}
                            />
                          </div>
                          <span className="text-sm font-medium w-8 text-right">{bucket.count}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Recommendations */}
              {workload.recommendations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>{t('workload.recommendations', { defaultValue: 'Recomendaciones' })}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {workload.recommendations.map((rec, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <AlertCircle className={`h-4 w-4 mt-0.5 shrink-0 ${
                            rec.priority === 'urgent' ? 'text-red-500' :
                            rec.priority === 'high' ? 'text-orange-500' : 'text-blue-500'
                          }`} />
                          <span>{rec.message}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* Agents by capacity */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('nav.agents')}</CardTitle>
                  <CardDescription>
                    {workload.report.total_agents} {t('team.totalAgents', { defaultValue: 'agentes' })} — {workload.report.total_assignments} {t('team.assignments', { defaultValue: 'asignaciones' })}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('team.agent', { defaultValue: 'Agente' })}</TableHead>
                        <TableHead>{t('team.capacity', { defaultValue: 'Capacidad' })}</TableHead>
                        <TableHead>{t('team.assignments', { defaultValue: 'Asignaciones' })}</TableHead>
                        <TableHead>{t('team.workloadStatus', { defaultValue: 'Estado' })}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {workload.agents
                        .sort((a, b) => b.capacity_percentage - a.capacity_percentage)
                        .map((agent) => (
                          <TableRow key={agent.agent_profile_id || agent.agent_id}>
                            <TableCell>
                              <p className="font-medium">{agent.agent_name}</p>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Progress
                                  value={Math.min(agent.capacity_percentage, 100)}
                                  className={`h-2 w-20 ${agent.capacity_percentage > 80 ? '[&>div]:bg-red-500' : agent.capacity_percentage > 60 ? '[&>div]:bg-yellow-500' : '[&>div]:bg-green-500'}`}
                                />
                                <span className="text-sm">{agent.capacity_percentage.toFixed(0)}%</span>
                              </div>
                            </TableCell>
                            <TableCell>{agent.current_assignments}</TableCell>
                            <TableCell>
                              <Badge className={`text-xs ${WORKLOAD_STATUS_COLORS[agent.workload_status] || ''}`}>
                                {t('workloadStatus.' + agent.workload_status)}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* =============== TAB 3: EXPORTS =============== */}
        <TabsContent value="exports" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Download className="h-5 w-5" />
                {t('reports.exportsTab')}
              </CardTitle>
              <CardDescription>
                {t('reports.exportDescription', { defaultValue: 'Exportar datos de asignaciones en formato CSV' })}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 items-end">
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t('reports.exportPeriod')}
                  </label>
                  <Select value={exportPeriod} onValueChange={setExportPeriod}>
                    <SelectTrigger className="w-48">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="7">{t('performance.last7days', { defaultValue: 'Últimos 7 días' })}</SelectItem>
                      <SelectItem value="30">{t('performance.last30days', { defaultValue: 'Últimos 30 días' })}</SelectItem>
                      <SelectItem value="90">{t('performance.last90days', { defaultValue: 'Últimos 90 días' })}</SelectItem>
                      <SelectItem value="365">{t('performance.lastYear', { defaultValue: 'Último año' })}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button onClick={handleExport} disabled={isExporting}>
                  {isExporting ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4 mr-2" />
                  )}
                  {t('reports.downloadCsv')}
                </Button>
              </div>

              {/* Export info */}
              <div className="mt-6 p-4 bg-muted/50 rounded-lg text-sm text-muted-foreground">
                <p className="font-medium mb-2">{t('reports.exportInfo', { defaultValue: 'Contenido del archivo CSV:' })}</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>{t('reports.exportCol1', { defaultValue: 'Fecha de asignación' })}</li>
                  <li>{t('reports.exportCol2', { defaultValue: 'Nombre del agente' })}</li>
                  <li>{t('reports.exportCol3', { defaultValue: 'Referencia de solicitud' })}</li>
                  <li>{t('reports.exportCol4', { defaultValue: 'Código de trámite' })}</li>
                  <li>{t('reports.exportCol5', { defaultValue: 'Estado' })}</li>
                  <li>{t('reports.exportCol6', { defaultValue: 'Horas de procesamiento' })}</li>
                  <li>{t('reports.exportCol7', { defaultValue: 'SLA cumplido' })}</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
