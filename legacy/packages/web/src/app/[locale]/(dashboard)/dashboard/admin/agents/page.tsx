'use client';

/**
 * Agents & Admins Admin Page
 * Manages agent profiles and admin users with tabbed interface
 *
 * Uses useTranslations('admin.agents') for all UI text.
 *
 * @module dashboard/admin/agents
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Switch } from '@/components/ui/switch';
import {
  Users, UserCog, Shield, Sparkles, Activity, RefreshCw, Search,
  Plus, MoreVertical, Edit, Trash2, UserCheck, UserX, Eye, Building2,
  Download, FileSpreadsheet, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { exportToCsv, exportToExcel } from '@/core/utils/export';
import { useToast } from '@/hooks/use-toast';
import {
  useAgentProfiles, useAdminUsers, useAlertsDashboard,
  useDeactivateAgent, useReactivateAgent, useActivateUser,
  useDeactivateUser, useDeleteAgentUser,
} from '@/modules/agents-admin/hooks';
import type { AgentProfile, AgentType, AgentAvailability } from '@/modules/agents-admin/types';
import { WorkloadOverviewTab } from '@/modules/agents-admin/components/WorkloadOverviewTab';
import { AdminAssistantTab } from '@/modules/agents-admin/components/AdminAssistantTab';
import { BackendUnavailableAlert } from '@/modules/admin/components';
import { SortableHeader } from '@/components/ui/sortable-header';
import { useSortState } from '@/hooks/use-sort-state';

export default function AgentsPage() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('admin.agents');
  const tAdmin = useTranslations('admin');
  const tCommon = useTranslations('common');
  const { toast } = useToast();

  // Filters persisted in URL search params (preserved on back-navigation)
  const searchParams = useSearchParams();
  const updateFilter = useCallback((key: string, value: string) => {
    const sp = new URLSearchParams(searchParams.toString());
    if (value === 'all' || value === '') { sp.delete(key); } else { sp.set(key, value); }
    sp.set('page', '1'); // reset page on filter change
    router.replace(`?${sp.toString()}`, { scroll: false });
  }, [searchParams, router]);

  const activeTab = searchParams.get('tab') || 'agents';
  const setActiveTab = (v: string) => { const sp = new URLSearchParams(searchParams.toString()); sp.set('tab', v); router.replace(`?${sp.toString()}`, { scroll: false }); };
  const typeFilter = (searchParams.get('type') || 'all') as 'all' | AgentType;
  const setTypeFilter = (v: string) => updateFilter('type', v);
  const statusFilter = (searchParams.get('status') || 'all') as 'all' | 'active' | 'inactive';
  const setStatusFilter = (v: string) => updateFilter('status', v);
  const supervisorFilter = (searchParams.get('supervisor') || 'all') as 'all' | 'yes' | 'no';
  const setSupervisorFilter = (v: string) => updateFilter('supervisor', v);
  const entityFilter = searchParams.get('entity') || 'all';
  const setEntityFilter = (v: string) => updateFilter('entity', v);
  const availabilityFilter = (searchParams.get('availability') || 'all') as 'all' | AgentAvailability;
  const setAvailabilityFilter = (v: string) => updateFilter('availability', v);

  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '');
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('q') || '');
  const [agentSort, handleAgentSort] = useSortState('created_at', 'desc');
  const [adminSort, handleAdminSort, sortAdminData] = useSortState();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentProfile | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  // Pagination state — server-side (read from URL)
  const agentPage = Number(searchParams.get('page') || '1');
  const setAgentPage = (v: number | ((p: number) => number)) => {
    const newPage = typeof v === 'function' ? v(agentPage) : v;
    const sp = new URLSearchParams(searchParams.toString());
    sp.set('page', String(newPage));
    router.replace(`?${sp.toString()}`, { scroll: false });
  };
  const agentPageSize = 20;
  const [adminPage, setAdminPage] = useState(1);
  const adminPageSize = 20;

  // Debounce search: 400ms delay before sending to server
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(value.trim());
      setAgentPage(1);
      setAdminPage(1);
    }, 400);
  }, []);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, []);

  // Queries — server-side pagination + search (20 per page, supports 1M+ agents)
  const {
    data: agentsData, isLoading: agentsLoading, error: agentsError, refetch: refetchAgents,
  } = useAgentProfiles({
    agent_type: typeFilter !== 'all' ? typeFilter : undefined,
    is_active: statusFilter === 'all' ? undefined : statusFilter === 'active',
    is_supervisor: supervisorFilter === 'all' ? undefined : supervisorFilter === 'yes',
    availability: availabilityFilter !== 'all' ? availabilityFilter as AgentAvailability : undefined,
    entity_code: entityFilter !== 'all' ? entityFilter : undefined,
    search: debouncedSearch || undefined,
    page: agentPage,
    page_size: agentPageSize,
    sort_by: agentSort.column || undefined,
    sort_order: agentSort.direction,
  });

  const {
    data: adminsData, isLoading: adminsLoading, error: adminsError, refetch: refetchAdmins,
  } = useAdminUsers(adminPage, adminPageSize, debouncedSearch || undefined);

  const { data: alertsDashboard, isLoading: alertsLoading } = useAlertsDashboard();

  // Mutations
  const deactivateAgentMutation = useDeactivateAgent();
  const reactivateAgentMutation = useReactivateAgent();
  const activateUserMutation = useActivateUser();
  const deactivateUserMutation = useDeactivateUser();
  const deleteAgentMutation = useDeleteAgentUser();

  const agents = agentsData?.items || [];
  const admins = adminsData?.items || [];
  const agentTotal = agentsData?.total || 0;
  const adminTotal = adminsData?.total || 0;

  // Unique entities for filter dropdown (derived from current page — approximate)
  const uniqueEntities = Array.from(
    new Map(
      agents
        .filter((a) => a.entity_code)
        .map((a) => [a.entity_code, { code: a.entity_code!, name: a.entity_name || a.entity_code! }])
    ).values()
  ).sort((a, b) => a.code.localeCompare(b.code));

  // All filters are now server-side (entity_code included)
  const filteredAgents = agents;

  // Admins are fully server-side filtered (search + pagination)
  const filteredAdmins = admins;

  // Server-side pagination totals
  const agentTotalPages = Math.max(1, Math.ceil(agentTotal / agentPageSize));
  const paginatedAgents = filteredAgents; // Already paginated by server

  const adminTotalPages = Math.max(1, Math.ceil(adminTotal / adminPageSize));
  const paginatedAdmins = filteredAdmins; // Already paginated by server

  // Reset page when filters change
  const resetAgentPage = () => setAgentPage(1);
  const resetAdminPage = () => setAdminPage(1);

  // Stats from server totals (not page-level counts)
  const agentStats = {
    total: agentTotal,
    active: agentsData?.stats?.active ?? agentTotal,
    supervisors: agentsData?.stats?.supervisors ?? agents.filter((a) => a.is_supervisor).length,
    ministry: agentsData?.stats?.ministry ?? agents.filter((a) => a.agent_type === 'ministry_agent').length,
    entity: agentsData?.stats?.entity ?? agentTotal,
  };

  const adminStats = {
    total: admins.length,
    active: admins.filter((a) => a.status === 'active').length,
  };

  const handleCreateAgent = () => router.push(`/${locale}/dashboard/admin/agents/new?type=agent`);
  const handleCreateAdmin = () => router.push(`/${locale}/dashboard/admin/agents/new?type=admin`);
  const handleViewAgent = (agent: AgentProfile) => {
    // Preserve current filters in the detail URL so "back" restores them
    const returnParams = searchParams.toString();
    router.push(`/${locale}/dashboard/admin/agents/${agent.id}${returnParams ? `?returnFilters=${encodeURIComponent(returnParams)}` : ''}`);
  };
  const handleEditAgent = (agent: AgentProfile) => router.push(`/${locale}/dashboard/admin/agents/${agent.id}?mode=edit`);

  const handleToggleAgentStatus = async (agent: AgentProfile) => {
    try {
      if (agent.is_active) {
        await deactivateAgentMutation.mutateAsync({ profileId: agent.id, reason: t('toast.deactivatedByAdmin') });
        toast({ title: t('toast.agentDeactivated') });
      } else {
        await reactivateAgentMutation.mutateAsync(agent.id);
        toast({ title: t('toast.agentReactivated') });
      }
      refetchAgents();
    } catch {
      toast({ variant: 'destructive', title: tAdmin('error'), description: t('toast.errorAgentStatus') });
    }
  };

  const handleDeleteAgent = async () => {
    if (!selectedUserId) return;
    try {
      await deleteAgentMutation.mutateAsync(selectedUserId);
      toast({ title: t('toast.agentDeleted') });
      setDeleteDialogOpen(false);
      setSelectedUserId(null);
      setSelectedAgent(null);
      refetchAgents();
    } catch {
      toast({ variant: 'destructive', title: tAdmin('error'), description: t('toast.errorDeleteAgent') });
    }
  };

  const handleToggleAdminStatus = async (userId: string, currentStatus: string) => {
    try {
      if (currentStatus === 'active') {
        await deactivateUserMutation.mutateAsync({ userId, reason: t('toast.deactivatedByAdmin') });
        toast({ title: t('toast.adminDeactivated') });
      } else {
        await activateUserMutation.mutateAsync(userId);
        toast({ title: t('toast.adminActivated') });
      }
      refetchAdmins();
    } catch {
      toast({ variant: 'destructive', title: tAdmin('error'), description: t('toast.errorAdminStatus') });
    }
  };

  const getAgentTypeBadge = (type: string) => {
    if (type === 'ministry_agent') return <Badge variant="default">{t('status.ministry')}</Badge>;
    return <Badge variant="secondary">{t('status.entityBadge')}</Badge>;
  };

  const hasActiveFilters = typeFilter !== 'all' || statusFilter !== 'all' || supervisorFilter !== 'all' || entityFilter !== 'all' || availabilityFilter !== 'all' || searchQuery !== '';
  const resetFilters = () => {
    setTypeFilter('all'); setStatusFilter('all'); setSupervisorFilter('all');
    setEntityFilter('all'); setAvailabilityFilter('all'); setSearchQuery('');
    setDebouncedSearch('');
    if (debounceRef.current) clearTimeout(debounceRef.current);
    resetAgentPage(); resetAdminPage();
  };

  const isBackendUnavailable = !!agentsError || !!adminsError;

  // --- Export helpers ---
  const getAgentExportData = () =>
    filteredAgents.map((a) => ({
      [t('table.agent')]: a.user_full_name || '',
      Email: a.user_email || '',
      [t('table.type')]: a.agent_type === 'ministry_agent' ? t('status.ministry') : t('status.entityBadge'),
      [t('status.supervisor')]: a.is_supervisor ? 'Si' : 'No',
      [t('table.organization')]: a.ministry_name || a.entity_name || '-',
      Code: a.entity_code || a.ministry_code || '-',
      [t('table.status')]: a.is_active ? t('status.active') : t('status.inactive'),
      [t('table.availability')]: a.availability || '-',
      [t('table.tasks')]: a.current_assignments ?? 0,
    }));

  const getAdminExportData = () =>
    filteredAdmins.map((a) => ({
      [t('table.administrator')]: `${a.first_name} ${a.last_name}`,
      Email: a.email || '',
      [t('table.status')]: a.status === 'active' ? t('status.active') : t('status.inactive'),
      [t('table.lastLogin')]: a.last_login ? new Date(a.last_login).toLocaleString() : t('never'),
      [t('table.createdAt')]: new Date(a.created_at).toLocaleDateString(),
    }));

  const dateStr = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground mt-2">{t('subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCreateAdmin}>
            <Shield className="h-4 w-4 mr-2" />
            {t('createAdmin')}
          </Button>
          <Button onClick={handleCreateAgent}>
            <Plus className="h-4 w-4 mr-2" />
            {t('createAgent')}
          </Button>
        </div>
      </div>

      {isBackendUnavailable && <BackendUnavailableAlert />}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="agents" className="flex items-center gap-2">
            <UserCog className="h-4 w-4" />
            {t('tabs.agents')} ({agentStats.total})
          </TabsTrigger>
          <TabsTrigger value="admins" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            {t('tabs.admins')} ({adminStats.total})
          </TabsTrigger>
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            {t('tabs.overview')}
            {(alertsDashboard?.total_alerts ?? 0) > 0 && (
              <Badge variant="destructive" className="h-5 min-w-5 px-1 text-[10px]">
                {alertsDashboard?.total_alerts}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="assistant" className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            {t('tabs.assistant')}
          </TabsTrigger>
        </TabsList>

        {/* Agents Tab */}
        <TabsContent value="agents" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-5">
            {[
              { label: t('stats.totalAgents'), value: agentStats.total },
              { label: t('stats.active'), value: agentStats.active, color: 'text-green-600' },
              { label: t('stats.supervisors'), value: agentStats.supervisors, color: 'text-amber-600' },
              { label: t('stats.ministries'), value: agentStats.ministry },
              { label: t('stats.entities'), value: agentStats.entity },
            ].map((stat) => (
              <Card key={stat.label}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">{stat.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className={`text-2xl font-bold ${stat.color || ''}`}>{stat.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t('listAgents')}</CardTitle>
                  <CardDescription>
                    {t('agentsFound', { count: filteredAgents.length })}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" disabled={filteredAgents.length === 0}>
                        <Download className="h-4 w-4 mr-1" />
                        {tAdmin('export') || 'Export'}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => exportToCsv(getAgentExportData(), { fileName: `agents_${dateStr}` })}>
                        <Download className="h-4 w-4 mr-2" />CSV
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => exportToExcel(getAgentExportData(), { fileName: `agents_${dateStr}`, sheetName: 'Agents' })}>
                        <FileSpreadsheet className="h-4 w-4 mr-2" />Excel
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button variant="outline" size="sm" onClick={() => refetchAgents()}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              {/* Filters row */}
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <div className="relative w-52">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder={tAdmin('searchPlaceholder')}
                    value={searchQuery}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    className="pl-9 h-9"
                  />
                </div>
                <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v as typeof typeFilter); resetAgentPage(); }}>
                  <SelectTrigger className="w-[150px] h-9">
                    <SelectValue placeholder={t('filters.allTypes')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('filters.allTypes')}</SelectItem>
                    <SelectItem value="ministry_agent">{t('filters.ministryAgent')}</SelectItem>
                    <SelectItem value="entity_agent">{t('filters.entityAgent')}</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={entityFilter} onValueChange={(v) => { setEntityFilter(v); resetAgentPage(); }}>
                  <SelectTrigger className="w-[160px] h-9">
                    <SelectValue placeholder={t('filters.allEntities')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('filters.allEntities')}</SelectItem>
                    {uniqueEntities.map((e) => (
                      <SelectItem key={e.code} value={e.code}>{e.code} — {e.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v as typeof statusFilter); resetAgentPage(); }}>
                  <SelectTrigger className="w-[130px] h-9">
                    <SelectValue placeholder={t('filters.allStatuses')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('filters.allStatuses')}</SelectItem>
                    <SelectItem value="active">{t('status.active')}</SelectItem>
                    <SelectItem value="inactive">{t('status.inactive')}</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={supervisorFilter} onValueChange={(v) => { setSupervisorFilter(v as typeof supervisorFilter); resetAgentPage(); }}>
                  <SelectTrigger className="w-[140px] h-9">
                    <SelectValue placeholder={t('filters.allSupervisors')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('filters.allSupervisors')}</SelectItem>
                    <SelectItem value="yes">{t('status.supervisor')}</SelectItem>
                    <SelectItem value="no">{t('filters.noSupervisor')}</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={availabilityFilter} onValueChange={(v) => { setAvailabilityFilter(v as typeof availabilityFilter); resetAgentPage(); }}>
                  <SelectTrigger className="w-[155px] h-9">
                    <SelectValue placeholder={t('filters.allAvailability')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('filters.allAvailability')}</SelectItem>
                    <SelectItem value="available">{t('availability.available')}</SelectItem>
                    <SelectItem value="on_leave">{t('availability.onLeave')}</SelectItem>
                    <SelectItem value="sick_leave">{t('availability.sickLeave')}</SelectItem>
                    <SelectItem value="training">{t('availability.training')}</SelectItem>
                    <SelectItem value="mission">{t('availability.mission')}</SelectItem>
                    <SelectItem value="temporarily_unavailable">{t('availability.temporarilyUnavailable')}</SelectItem>
                  </SelectContent>
                </Select>
                {hasActiveFilters && (
                  <Button variant="ghost" size="sm" onClick={resetFilters} className="h-9 text-xs text-muted-foreground">
                    {t('filters.reset')}
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {agentsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground">{tAdmin('loading')}</span>
                </div>
              ) : filteredAgents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Users className="h-12 w-12 mb-4 opacity-50" />
                  <p>{t('noAgentsFound')}</p>
                </div>
              ) : (
                <div className="border rounded-md overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <SortableHeader column="user_full_name" label={t('table.agent')} sort={agentSort} onSort={handleAgentSort} />
                      <SortableHeader column="agent_type" label={t('table.type')} sort={agentSort} onSort={handleAgentSort} />
                      <SortableHeader column="entity_name" label={t('table.organization')} sort={agentSort} onSort={handleAgentSort} className="hidden lg:table-cell" />
                      <TableHead className="hidden xl:table-cell">{t('table.site')}</TableHead>
                      <SortableHeader column="is_active" label={t('table.status')} sort={agentSort} onSort={handleAgentSort} />
                      <SortableHeader column="availability" label={t('table.availability')} sort={agentSort} onSort={handleAgentSort} className="hidden md:table-cell" />
                      <SortableHeader column="current_assignments" label={t('table.tasks')} sort={agentSort} onSort={handleAgentSort} className="hidden md:table-cell" />
                      <TableHead className="text-right">{t('table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedAgents.map((agent) => (
                      <TableRow key={agent.id} className={!agent.is_active ? 'opacity-60' : ''}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{agent.user_full_name || 'N/A'}</div>
                            <div className="text-sm text-muted-foreground">{agent.user_email}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getAgentTypeBadge(agent.agent_type)}
                            {agent.is_supervisor && (
                              <Badge variant="outline" className="border-amber-500 text-amber-700">
                                {t('status.supervisor')}
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="hidden lg:table-cell">
                          <div className="flex items-center gap-2">
                            <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
                            <div className="min-w-0">
                              <div className="truncate">{agent.ministry_name || agent.entity_name || '-'}</div>
                              {agent.entity_code && (
                                <div className="text-xs text-muted-foreground">{agent.entity_code}</div>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden xl:table-cell text-xs text-muted-foreground">
                          {agent.location_name || agent.location_city || '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Switch
                              checked={agent.is_active}
                              onCheckedChange={() => handleToggleAgentStatus(agent)}
                              disabled={deactivateAgentMutation.isPending || reactivateAgentMutation.isPending}
                            />
                            <span className={`text-xs ${agent.is_active ? 'text-green-700' : 'text-muted-foreground'}`}>
                              {agent.is_active ? t('status.active') : t('status.inactive')}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          {agent.availability ? (
                            <Badge variant={agent.availability === 'available' ? 'default' : 'secondary'} className="text-xs">
                              {t(`availability.${agent.availability === 'on_leave' ? 'onLeave' : agent.availability === 'sick_leave' ? 'sickLeave' : agent.availability === 'temporarily_unavailable' ? 'temporarilyUnavailable' : agent.availability}`)}
                            </Badge>
                          ) : '-'}
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          {agent.current_assignments !== undefined ? <span>{agent.current_assignments}</span> : '-'}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon"><MoreVertical className="h-4 w-4" /></Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleViewAgent(agent)}>
                                <Eye className="h-4 w-4 mr-2" />{t('viewDetails')}
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => handleEditAgent(agent)}>
                                <Edit className="h-4 w-4 mr-2" />{t('modify')}
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => handleToggleAgentStatus(agent)}>
                                {agent.is_active
                                  ? <><UserX className="h-4 w-4 mr-2" />{t('deactivate')}</>
                                  : <><UserCheck className="h-4 w-4 mr-2" />{t('reactivate')}</>}
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-red-600"
                                onClick={() => { setSelectedAgent(agent); setSelectedUserId(agent.user_id); setDeleteDialogOpen(true); }}
                              >
                                <Trash2 className="h-4 w-4 mr-2" />{t('delete')}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                </div>
              )}
              {/* Agents Pagination */}
              {filteredAgents.length > 0 && (
                <div className="flex items-center justify-between pt-4">
                  <span className="text-sm text-muted-foreground">
                    {tCommon('showing')} {(agentPage - 1) * agentPageSize + 1}-{Math.min(agentPage * agentPageSize, agentTotal)} {tCommon('of')} {agentTotal}
                  </span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-muted-foreground">
                      {tCommon('page')} {agentPage} {tCommon('of')} {agentTotalPages}
                    </span>
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setAgentPage(p => Math.max(1, p - 1))} disabled={agentPage === 1 || agentsLoading}>
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setAgentPage(p => Math.min(agentTotalPages, p + 1))} disabled={agentPage === agentTotalPages || agentsLoading}>
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Admins Tab */}
        <TabsContent value="admins" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">{t('totalAdmins')}</CardTitle></CardHeader>
              <CardContent><div className="text-2xl font-bold">{adminStats.total}</div></CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">{t('stats.active')}</CardTitle></CardHeader>
              <CardContent><div className="text-2xl font-bold text-green-600">{adminStats.active}</div></CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t('listAdmins')}</CardTitle>
                  <CardDescription>{t('adminsFound', { count: filteredAdmins.length })}</CardDescription>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative w-64">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input placeholder={tAdmin('searchPlaceholder')} value={searchQuery} onChange={(e) => handleSearchChange(e.target.value)} className="pl-9" />
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" disabled={filteredAdmins.length === 0}>
                        <Download className="h-4 w-4 mr-1" />
                        {tAdmin('export') || 'Export'}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => exportToCsv(getAdminExportData(), { fileName: `admins_${dateStr}` })}>
                        <Download className="h-4 w-4 mr-2" />CSV
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => exportToExcel(getAdminExportData(), { fileName: `admins_${dateStr}`, sheetName: 'Admins' })}>
                        <FileSpreadsheet className="h-4 w-4 mr-2" />Excel
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button variant="outline" size="sm" onClick={() => refetchAdmins()}><RefreshCw className="h-4 w-4" /></Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {adminsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground">{tAdmin('loading')}</span>
                </div>
              ) : filteredAdmins.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Shield className="h-12 w-12 mb-4 opacity-50" /><p>{t('noAdminsFound')}</p>
                </div>
              ) : (
                <div className="border rounded-md overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <SortableHeader column="first_name" label={t('table.administrator')} sort={adminSort} onSort={handleAdminSort} />
                      <SortableHeader column="status" label={t('table.status')} sort={adminSort} onSort={handleAdminSort} />
                      <SortableHeader column="last_login" label={t('table.lastLogin')} sort={adminSort} onSort={handleAdminSort} className="hidden md:table-cell" />
                      <SortableHeader column="created_at" label={t('table.createdAt')} sort={adminSort} onSort={handleAdminSort} className="hidden lg:table-cell" />
                      <TableHead className="text-right">{t('table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(sortAdminData(paginatedAdmins as unknown as Record<string, unknown>[], { first_name: 'string', status: 'string', last_login: 'date', created_at: 'date' }) as unknown as typeof paginatedAdmins).map((admin) => (
                      <TableRow key={admin.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{admin.first_name} {admin.last_name}</div>
                            <div className="text-sm text-muted-foreground">{admin.email}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          {admin.status === 'active'
                            ? <Badge className="bg-green-100 text-green-800">{t('status.active')}</Badge>
                            : <Badge variant="destructive">{t('status.inactive')}</Badge>}
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          {admin.last_login
                            ? new Date(admin.last_login).toLocaleDateString(locale, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
                            : t('never')}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell">
                          {new Date(admin.created_at).toLocaleDateString(locale)}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon"><MoreVertical className="h-4 w-4" /></Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleToggleAdminStatus(admin.id, admin.status)}>
                                {admin.status === 'active'
                                  ? <><UserX className="h-4 w-4 mr-2" />{t('deactivate')}</>
                                  : <><UserCheck className="h-4 w-4 mr-2" />{t('activate')}</>}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                </div>
              )}
              {/* Admins Pagination */}
              {filteredAdmins.length > 0 && (
                <div className="flex items-center justify-between pt-4">
                  <span className="text-sm text-muted-foreground">
                    {tCommon('showing')} {(adminPage - 1) * adminPageSize + 1}-{Math.min(adminPage * adminPageSize, adminTotal)} {tCommon('of')} {adminTotal}
                  </span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-muted-foreground">
                      {tCommon('page')} {adminPage} {tCommon('of')} {adminTotalPages}
                    </span>
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setAdminPage(p => Math.max(1, p - 1))} disabled={adminPage === 1 || adminsLoading}>
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setAdminPage(p => Math.min(adminTotalPages, p + 1))} disabled={adminPage === adminTotalPages || adminsLoading}>
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Overview Tab */}
        <TabsContent value="overview">
          <WorkloadOverviewTab
            agents={agents}
            agentsLoading={agentsLoading}
            dashboard={alertsDashboard}
            dashboardLoading={alertsLoading}
            onViewAgent={(agentId) => router.push(`/${locale}/dashboard/admin/agents/${agentId}`)}
          />
        </TabsContent>

        {/* Assistant IA Tab */}
        <TabsContent value="assistant">
          <AdminAssistantTab />
        </TabsContent>
      </Tabs>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('confirmDeleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('confirmDeleteDesc', { name: selectedAgent?.user_full_name || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tAdmin('cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteAgent} className="bg-red-600 hover:bg-red-700">
              {t('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
