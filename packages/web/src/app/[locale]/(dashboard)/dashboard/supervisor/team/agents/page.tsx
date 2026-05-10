'use client';

/**
 * Team Agents Page - Supervisor View
 * List and view all agents under supervision
 *
 * Backend endpoint: GET /supervisor/agents
 * Model: AgentListItem from supervisor_routes.py
 *
 * @route /[locale]/dashboard/supervisor/team/agents
 * @date 2026-01-19
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
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Loader2,
  AlertCircle,
  ArrowLeft,
  Search,
  RefreshCw,
  Users,
  User,
  Activity,
  BarChart3,
  Download,
  ArrowRightLeft,
} from 'lucide-react';
import { toast } from 'sonner';
import apiClient from '@/core/api/client';
import Link from 'next/link';
import { Progress } from '@/components/ui/progress';
import { LocationFilter, useLocationFilterState } from '@/modules/inspections/components/LocationFilter';
import { useAgentProfile } from '@/modules/agent-dashboard/hooks/useAgentDashboard';
import type { AgentListItem, AgentAssignmentItem } from '../../types';
import { WORKLOAD_STATUS_COLORS, AVAILABILITY_COLORS, formatSuccessRate, getSuccessRateColor } from '../../types';

export default function TeamAgentsPage() {
  const locale = useLocale();
  const t = useTranslations('supervisor');
  const tCommon = useTranslations('common');

  const [searchTerm, setSearchTerm] = useState('');
  const [includeUnavailable, setIncludeUnavailable] = useState(false);
  const [reassignDialogOpen, setReassignDialogOpen] = useState(false);
  const { data: agentProfile } = useAgentProfile();
  const { locationFilter, setLocationFilter } = useLocationFilterState(agentProfile);
  const [sourceAgent, setSourceAgent] = useState<AgentListItem | null>(null);
  const [targetAgentId, setTargetAgentId] = useState<string>('');
  const [selectedAssignments, setSelectedAssignments] = useState<Set<string>>(new Set());
  const [isReassigning, setIsReassigning] = useState(false);

  // Fetch source agent assignments when dialog opens
  const { data: sourceAssignments, isLoading: assignmentsLoading } = useQuery<AgentAssignmentItem[]>({
    queryKey: ['supervisor', 'agent-assignments', sourceAgent?.agent_profile_id],
    queryFn: async () => {
      const response = await apiClient.get(`/supervisor/agents/${sourceAgent!.agent_profile_id}/assignments`);
      return response.data;
    },
    enabled: !!sourceAgent && reassignDialogOpen,
  });

  const openReassignDialog = (agent: AgentListItem) => {
    setSourceAgent(agent);
    setTargetAgentId('');
    setSelectedAssignments(new Set());
    setReassignDialogOpen(true);
  };

  const toggleAssignment = (id: string) => {
    setSelectedAssignments(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!sourceAssignments) return;
    if (selectedAssignments.size === sourceAssignments.length) {
      setSelectedAssignments(new Set());
    } else {
      setSelectedAssignments(new Set(sourceAssignments.map(a => a.assignment_id)));
    }
  };

  const handleBulkReassign = async () => {
    if (!targetAgentId || selectedAssignments.size === 0) return;
    setIsReassigning(true);
    try {
      const response = await apiClient.post('/supervisor/bulk/reassign', {
        assignment_ids: Array.from(selectedAssignments),
        target_agent_id: targetAgentId,
      });
      const result = response.data;
      toast.success(t('team.reassignSuccess', {
        defaultValue: '{count} dossier(s) reasignados',
        count: result.reassigned,
      }));
      setReassignDialogOpen(false);
      refetch();
    } catch {
      toast.error(t('team.reassignError', { defaultValue: 'Error al reasignar' }));
    } finally {
      setIsReassigning(false);
    }
  };

  // Fetch agents - uses GET /supervisor/agents
  const { data: agents, isLoading, isError, error, refetch } = useQuery<AgentListItem[]>({
    queryKey: ['supervisor', 'agents', includeUnavailable, locationFilter],
    queryFn: async () => {
      const params: Record<string, string | boolean> = { include_unavailable: includeUnavailable };
      if (locationFilter) params.entity_location_id = locationFilter;
      const response = await apiClient.get('/supervisor/agents', { params });
      return response.data;
    },
  });

  // Filter agents
  const filteredAgents = agents?.filter((agent) => {
    const matchesSearch =
      agent.agent_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      agent.agent_email.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesSearch;
  });

  // Calculate summary stats
  const totalAgents = agents?.length || 0;
  const availableAgents = agents?.filter(a => a.availability === 'available').length || 0;
  const overloadedAgents = agents?.filter(a => a.workload_status === 'overloaded').length || 0;
  const avgCapacity = agents?.length
    ? agents.reduce((sum, a) => sum + a.capacity_percentage, 0) / agents.length
    : 0;

  // Loading state
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

  // Error state
  if (isError) {
    return (
      <div className="space-y-6">
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
            <Users className="h-6 w-6" />
            {t('nav.teamAgents')}
          </h1>
          <p className="text-muted-foreground">{t('team.agentsDescription') || 'Manage and monitor your team agents'}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('team.totalAgents') || 'Total Agents'}</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalAgents}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('team.available') || 'Available'}</CardTitle>
            <User className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{availableAgents}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('team.overloaded') || 'Overloaded'}</CardTitle>
            <Activity className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overloadedAgents}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('team.avgCapacity') || 'Avg Capacity'}</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgCapacity.toFixed(0)}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Search and filters */}
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
            <LocationFilter
              entityCode={agentProfile?.entity_code}
              isMainOffice={agentProfile?.is_main_office ?? false}
              value={locationFilter}
              onChange={setLocationFilter}
            />
            <div className="flex items-center gap-2">
              <Switch
                id="include-unavailable"
                checked={includeUnavailable}
                onCheckedChange={setIncludeUnavailable}
              />
              <Label htmlFor="include-unavailable" className="text-sm">
                {t('team.showUnavailable') || 'Show unavailable'}
              </Label>
            </div>
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const response = await apiClient.get('/supervisor/export/assignments', {
                    params: { format: 'csv', period_days: 30 },
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
                } catch {
                  toast.error(t('team.exportError', { defaultValue: 'Error al exportar CSV' }));
                }
              }}
            >
              <Download className="h-4 w-4 mr-2" />
              {t('team.exportCsv', { defaultValue: 'Export CSV' })}
            </Button>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              {tCommon('refresh')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Agents Table */}
      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('team.agent') || 'Agent'}</TableHead>
                <TableHead>{t('team.assignments') || 'Assignments'}</TableHead>
                <TableHead>{t('team.capacity') || 'Capacity'}</TableHead>
                <TableHead>{t('team.workloadStatus') || 'Workload'}</TableHead>
                <TableHead>{t('team.availability') || 'Availability'}</TableHead>
                <TableHead>{t('team.successRate') || 'Success Rate'}</TableHead>
                <TableHead className="text-right">{tCommon('actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAgents?.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    {tCommon('noData')}
                  </TableCell>
                </TableRow>
              ) : (
                filteredAgents?.map((agent) => (
                  <TableRow key={agent.agent_profile_id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{agent.agent_name}</p>
                        <p className="text-xs text-muted-foreground">{agent.agent_email}</p>
                        {agent.specializations && agent.specializations.length > 0 && (
                          <div className="flex gap-1 mt-1">
                            {agent.specializations.slice(0, 2).map((spec) => (
                              <Badge key={spec} variant="outline" className="text-xs">
                                {t('workflowNames.' + spec)}
                              </Badge>
                            ))}
                            {agent.specializations.length > 2 && (
                              <Badge variant="outline" className="text-xs">
                                +{agent.specializations.length - 2}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">{agent.current_assignments}</span>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span>{agent.capacity_percentage.toFixed(0)}%</span>
                        </div>
                        <Progress
                          value={Math.min(agent.capacity_percentage, 100)}
                          className={`h-2 ${agent.capacity_percentage > 80 ? '[&>div]:bg-red-500' : agent.capacity_percentage > 60 ? '[&>div]:bg-yellow-500' : '[&>div]:bg-green-500'}`}
                        />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={WORKLOAD_STATUS_COLORS[agent.workload_status] || 'bg-gray-100'}>
                        {t('workloadStatus.' + agent.workload_status)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={AVAILABILITY_COLORS[agent.availability] || 'bg-gray-100'}>
                        {t('availabilityStatus.' + agent.availability)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className={getSuccessRateColor(agent.success_rate)}>
                        {formatSuccessRate(agent.success_rate)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex gap-1 justify-end">
                        {agent.current_assignments > 0 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openReassignDialog(agent)}
                          >
                            <ArrowRightLeft className="h-3 w-3 mr-1" />
                            {t('team.reassign', { defaultValue: 'Reasignar' })}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toast.info(`${agent.agent_name} — ${agent.current_assignments} assignments, ${formatSuccessRate(agent.success_rate)} success rate`)}
                        >
                          {tCommon('viewDetails') || 'View'}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Bulk Reassign Dialog */}
      <Dialog open={reassignDialogOpen} onOpenChange={setReassignDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ArrowRightLeft className="h-5 w-5" />
              {t('team.bulkReassign', { defaultValue: 'Reasignación masiva' })}
            </DialogTitle>
            <DialogDescription>
              {sourceAgent?.agent_name} — {sourceAgent?.current_assignments} {t('team.assignments', { defaultValue: 'asignaciones' })}
            </DialogDescription>
          </DialogHeader>

          {/* Target agent selector */}
          <div className="space-y-2">
            <Label>{t('team.targetAgent', { defaultValue: 'Agente destino' })}</Label>
            <Select value={targetAgentId} onValueChange={setTargetAgentId}>
              <SelectTrigger>
                <SelectValue placeholder={t('team.selectAgent', { defaultValue: 'Seleccionar agente' })} />
              </SelectTrigger>
              <SelectContent>
                {agents?.filter(a =>
                  a.agent_profile_id !== sourceAgent?.agent_profile_id &&
                  a.availability === 'available'
                ).map(a => (
                  <SelectItem key={a.agent_profile_id} value={a.agent_profile_id}>
                    {a.agent_name} ({a.capacity_percentage.toFixed(0)}%) - {t('workloadStatus.' + a.workload_status)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Assignments list */}
          <div className="border rounded-md">
            {assignmentsLoading ? (
              <div className="flex justify-center p-4">
                <Loader2 className="h-5 w-5 animate-spin" />
              </div>
            ) : !sourceAssignments?.length ? (
              <p className="text-center text-muted-foreground p-4">
                {t('team.noAssignments', { defaultValue: 'Sin asignaciones activas' })}
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        checked={sourceAssignments.length > 0 && selectedAssignments.size === sourceAssignments.length}
                        onCheckedChange={toggleAll}
                      />
                    </TableHead>
                    <TableHead>{t('team.reference', { defaultValue: 'Referencia' })}</TableHead>
                    <TableHead>{t('team.workflow', { defaultValue: 'Trámite' })}</TableHead>
                    <TableHead>{tCommon('status')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sourceAssignments.map(item => (
                    <TableRow key={item.assignment_id}>
                      <TableCell>
                        <Checkbox
                          checked={selectedAssignments.has(item.assignment_id)}
                          onCheckedChange={() => toggleAssignment(item.assignment_id)}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {item.request_reference || item.request_id.slice(0, 8)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {item.workflow_code ? t('workflowNames.' + item.workflow_code) : '-'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs">
                          {t('assignmentStatus.' + item.status)}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setReassignDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={handleBulkReassign}
              disabled={isReassigning || selectedAssignments.size === 0 || !targetAgentId}
            >
              {isReassigning && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t('team.reassignSelected', {
                defaultValue: 'Reasignar {count} seleccionados',
                count: selectedAssignments.size,
              })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
