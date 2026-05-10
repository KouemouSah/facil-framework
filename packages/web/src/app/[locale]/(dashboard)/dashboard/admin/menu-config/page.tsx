'use client';

/**
 * Menu Configuration Admin Page
 * Manage workflow menu mappings (auto-generation rules)
 *
 * @module dashboard/admin/menu-config
 * @date 2026-01-19
 * @updated 2026-02-17 - i18n: replaced all hardcoded strings with t() calls
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  Menu,
  Plus,
  Search,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Check,
  X,
  LayoutGrid,
  Settings2,
  Eye,
  Copy,
} from 'lucide-react';
import { toast } from 'sonner';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import apiClient from '@/core/api/client';
import type {
  WorkflowMenuMapping,
  WorkflowMenuMappingListResponse,
} from '@/modules/agent-dashboard/types/menu-config';
import { OrphanDetectionPanel } from '@/modules/admin/components/OrphanDetectionPanel';
import { MenuPreview } from '@/modules/admin/components/menu-builder/MenuPreview';
import type { MenuItem } from '@/modules/admin/components/menu-builder/types';

const PAGE_SIZE = 10;

// =============================================================================
// API FUNCTIONS
// =============================================================================

async function fetchWorkflowMappings(
  page: number,
  isActive?: boolean,
  pageSize?: number
): Promise<WorkflowMenuMappingListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: (pageSize ?? PAGE_SIZE).toString(),
  });
  if (isActive !== undefined) {
    params.append('is_active', isActive.toString());
  }
  const response = await apiClient.get<WorkflowMenuMappingListResponse>(
    `/menu-config/workflow-mappings?${params}`
  );
  return response.data;
}

async function updateWorkflowMapping(
  id: number,
  data: Partial<WorkflowMenuMapping>
): Promise<WorkflowMenuMapping> {
  const response = await apiClient.put<WorkflowMenuMapping>(
    `/menu-config/workflow-mappings/${id}`,
    data
  );
  return response.data;
}

async function deleteWorkflowMapping(id: number): Promise<void> {
  await apiClient.delete(`/menu-config/workflow-mappings/${id}`);
}

async function createWorkflowMapping(
  data: Omit<WorkflowMenuMapping, 'id' | 'created_at' | 'updated_at'>
): Promise<WorkflowMenuMapping> {
  const response = await apiClient.post<WorkflowMenuMapping>(
    '/menu-config/workflow-mappings',
    data
  );
  return response.data;
}

// =============================================================================
// MAIN PAGE COMPONENT
// =============================================================================

export default function MenuConfigPage() {
  const locale = useLocale();
  const t = useTranslations('admin.menuConfig');

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: 'Admin', href: `/${locale}/dashboard/admin` },
        { label: 'Menu Config' },
      ]} />

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <Menu className="h-8 w-8" />
          {t('page.title')}
        </h1>
        <p className="text-muted-foreground mt-2">
          {t('page.subtitle')}
        </p>
      </div>

      {/* Navigation Cards */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-2 border-primary/20 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Settings2 className="h-5 w-5" />
              {t('page.navMappingsTitle')}
            </CardTitle>
            <CardDescription>
              {t('page.navMappingsDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Badge variant="secondary">{t('page.navCurrentSection')}</Badge>
          </CardContent>
        </Card>

        <Link href={`/${locale}/dashboard/admin/menu-config/display`}>
          <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer h-full">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <LayoutGrid className="h-5 w-5" />
                {t('page.navDisplayTitle')}
              </CardTitle>
              <CardDescription>
                {t('page.navDisplayDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" size="sm">
                {t('page.navAccess')} <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </Link>
      </div>

      <WorkflowMappingsTab />
    </div>
  );
}

// =============================================================================
// WORKFLOW MAPPINGS TAB
// =============================================================================

function WorkflowMappingsTab() {
  const locale = useLocale();
  const t = useTranslations('admin.menuConfig');
  const queryClient = useQueryClient();
  const [currentPage, setCurrentPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedMapping, setSelectedMapping] = useState<WorkflowMenuMapping | null>(null);
  // Selection state for batch actions
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isBatchDeleteDialogOpen, setIsBatchDeleteDialogOpen] = useState(false);
  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['workflow-mappings', currentPage, activeFilter],
    queryFn: () => fetchWorkflowMappings(
      currentPage,
      activeFilter === 'all' ? undefined : activeFilter === 'active'
    ),
  });

  // Fetch ALL active mappings for preview (not limited by pagination)
  const { data: allActiveData } = useQuery({
    queryKey: ['workflow-mappings', 'all-active'],
    queryFn: () => fetchWorkflowMappings(1, true, 100),
    staleTime: 60000,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<WorkflowMenuMapping> }) =>
      updateWorkflowMapping(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-mappings'] });
      toast.success(t('page.mappingUpdated'));
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : t('page.updateError'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWorkflowMapping,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-mappings'] });
      toast.success(t('page.mappingDeleted'));
      setIsDeleteDialogOpen(false);
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : t('page.deleteError'));
    },
  });

  // Batch update mutation (activate/deactivate multiple) — allSettled for partial failure resilience
  const batchUpdateMutation = useMutation({
    mutationFn: async ({ ids, data }: { ids: number[]; data: Partial<WorkflowMenuMapping> }) => {
      const results = await Promise.allSettled(ids.map(id => updateWorkflowMapping(id, data)));
      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;
      return { succeeded, failed };
    },
    onSuccess: ({ succeeded, failed }) => {
      queryClient.invalidateQueries({ queryKey: ['workflow-mappings'] });
      if (failed > 0) {
        toast.warning(t('page.batchUpdatePartial', { succeeded, failed }));
      } else {
        toast.success(t('page.batchUpdated', { succeeded }));
      }
      setSelectedIds(new Set());
    },
  });

  // Batch delete mutation — allSettled for partial failure resilience
  const batchDeleteMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      const results = await Promise.allSettled(ids.map(id => deleteWorkflowMapping(id)));
      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;
      return { succeeded, failed };
    },
    onSuccess: ({ succeeded, failed }) => {
      queryClient.invalidateQueries({ queryKey: ['workflow-mappings'] });
      if (failed > 0) {
        toast.warning(t('page.batchDeletePartial', { succeeded, failed }));
      } else {
        toast.success(t('page.batchDeleted', { succeeded }));
      }
      setSelectedIds(new Set());
      setIsBatchDeleteDialogOpen(false);
    },
  });

  // Clone handler — unique suffix to avoid duplicate menu_group_id
  const handleDuplicate = useCallback(async (mapping: WorkflowMenuMapping) => {
    setDuplicatingId(mapping.id);
    try {
      const suffix = '_copy_' + Date.now().toString(36).slice(-4);
      // Destructure to clone all fields, override identifiers
      const { id: _id, created_at: _ca, updated_at: _ua, ...rest } = mapping;
      const cloneData = {
        ...rest,
        menu_group_id: mapping.menu_group_id + suffix,
        is_active: false,
      };
      await createWorkflowMapping(cloneData);
      queryClient.invalidateQueries({ queryKey: ['workflow-mappings'] });
      toast.success(t('actions.duplicateSuccess', { defaultValue: 'Mapping duplicado' }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('actions.duplicateError', { defaultValue: 'Error al duplicar' }));
    } finally {
      setDuplicatingId(null);
    }
  }, [queryClient, t]);

  // Build preview MenuItems from ALL active mappings (not just current page)
  const previewMenuItems = useMemo((): MenuItem[] => {
    const activeMappings = allActiveData?.items ?? [];
    return activeMappings
      .sort((a, b) => a.display_order - b.display_order)
      .map((mapping) => {
        const subItems: MenuItem['items'] = [];
        if (mapping.include_pending) {
          subItems.push({ id: `${mapping.menu_group_id}_pending`, titleKey: t('preview.subPending'), href: '#', icon: 'Clock' });
        }
        if (mapping.include_validation) {
          subItems.push({ id: `${mapping.menu_group_id}_validation`, titleKey: t('preview.subValidation'), href: '#', icon: 'CheckSquare' });
        }
        if (mapping.include_appointments) {
          subItems.push({ id: `${mapping.menu_group_id}_appointments`, titleKey: t('preview.subAppointments'), href: '#', icon: 'Calendar' });
        }
        if (mapping.include_history) {
          subItems.push({ id: `${mapping.menu_group_id}_history`, titleKey: t('preview.subHistory'), href: '#', icon: 'History' });
        }
        return {
          id: mapping.menu_group_id,
          titleKey: mapping.menu_title_key,
          icon: mapping.menu_icon,
          items: subItems.length > 0 ? subItems : undefined,
          href: subItems.length === 0 ? '#' : undefined,
        };
      });
  }, [allActiveData?.items, t]);

  // Debounce search input (300ms)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchQuery(searchInput);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchInput]);

  useEffect(() => {
    setCurrentPage(1);
  }, [activeFilter]);

  // Clear selection when page changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [currentPage]);

  const filteredMappings = data?.items?.filter((mapping) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      mapping.workflow_pattern.toLowerCase().includes(query) ||
      mapping.menu_group_id.toLowerCase().includes(query) ||
      mapping.menu_title_key.toLowerCase().includes(query)
    );
  }) || [];

  const handleToggleActive = async (mapping: WorkflowMenuMapping) => {
    updateMutation.mutate({
      id: mapping.id,
      data: { is_active: !mapping.is_active },
    });
  };

  // Selection helpers
  const isAllSelected = filteredMappings.length > 0 &&
    filteredMappings.every(m => selectedIds.has(m.id));
  const isSomeSelected = selectedIds.size > 0 && !isAllSelected;

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(filteredMappings.map(m => m.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: number, checked: boolean) => {
    const newSet = new Set(selectedIds);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedIds(newSet);
  };

  const handleBatchActivate = () => {
    batchUpdateMutation.mutate({ ids: Array.from(selectedIds), data: { is_active: true } });
  };

  const handleBatchDeactivate = () => {
    batchUpdateMutation.mutate({ ids: Array.from(selectedIds), data: { is_active: false } });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : t('page.loadError')}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            {t('page.retry')}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Orphan Detection */}
      <OrphanDetectionPanel />

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('page.statsTotal')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data?.total || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('page.statsActive')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {data?.items?.filter(m => m.is_active).length || 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('page.statsInactive')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-muted-foreground">
              {data?.items?.filter(m => !m.is_active).length || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('page.navMappingsTitle')}</CardTitle>
              <CardDescription>
                {t('page.navMappingsDescription')}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Sheet>
                <SheetTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Eye className="h-4 w-4 mr-2" />
                    {t('preview.title', { defaultValue: 'Vista Previa' })}
                  </Button>
                </SheetTrigger>
                <SheetContent side="right" className="w-[380px] sm:w-[420px]">
                  <SheetHeader>
                    <SheetTitle>{t('preview.title', { defaultValue: 'Vista Previa' })}</SheetTitle>
                  </SheetHeader>
                  <div className="mt-4">
                    <MenuPreview menus={previewMenuItems} />
                    <p className="text-xs text-muted-foreground mt-4 px-1">
                      {t('preview.note', {
                        defaultValue: 'Esto es una aproximación. El menú real depende del rol y entidad del agente.',
                      })}
                    </p>
                  </div>
                </SheetContent>
              </Sheet>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {t('page.refresh')}
              </Button>
              <Button size="sm" asChild>
                <Link href={`/${locale}/dashboard/admin/workflow-mappings/new`}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('page.createMapping')}
                </Link>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('page.searchPlaceholder')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={activeFilter} onValueChange={setActiveFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('page.filterAll')}</SelectItem>
                <SelectItem value="active">{t('page.filterActive')}</SelectItem>
                <SelectItem value="inactive">{t('page.filterInactive')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Batch Actions Bar */}
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-3 p-3 mb-4 bg-muted/50 border rounded-lg">
              <span className="text-sm font-medium">
                {t('page.batchSelected', { count: selectedIds.size })}
              </span>
              <div className="flex-1" />
              <Button
                size="sm"
                variant="outline"
                onClick={handleBatchActivate}
                disabled={batchUpdateMutation.isPending}
              >
                {batchUpdateMutation.isPending && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                <Check className="mr-1 h-3 w-3" />
                {t('page.batchActivate')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleBatchDeactivate}
                disabled={batchUpdateMutation.isPending}
              >
                {batchUpdateMutation.isPending && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                <X className="mr-1 h-3 w-3" />
                {t('page.batchDeactivate')}
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => setIsBatchDeleteDialogOpen(true)}
                disabled={batchDeleteMutation.isPending}
              >
                <Trash2 className="mr-1 h-3 w-3" />
                {t('page.batchDelete')}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedIds(new Set())}
              >
                {t('page.batchCancel')}
              </Button>
            </div>
          )}

          <div className="border rounded-md overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <Checkbox
                      checked={isAllSelected ? true : isSomeSelected ? 'indeterminate' : false}
                      onCheckedChange={handleSelectAll}
                      aria-label={t('page.selectAll')}
                    />
                  </TableHead>
                  <TableHead>{t('page.tablePattern')}</TableHead>
                  <TableHead>{t('page.tableMenuId')}</TableHead>
                  <TableHead>{t('page.tableIcon')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('page.tableOptions')}</TableHead>
                  <TableHead>{t('page.tableStatus')}</TableHead>
                  <TableHead className="text-right">{t('page.tableActions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredMappings.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      {t('page.noMappingsFound')}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredMappings.map((mapping) => (
                    <TableRow key={mapping.id} data-state={selectedIds.has(mapping.id) ? 'selected' : undefined}>
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(mapping.id)}
                          onCheckedChange={(checked) => handleSelectOne(mapping.id, !!checked)}
                          aria-label={t('page.selectRow', { pattern: mapping.workflow_pattern })}
                        />
                      </TableCell>
                      <TableCell>
                        <code className="text-sm bg-muted px-2 py-1 rounded">
                          {mapping.workflow_pattern}
                        </code>
                      </TableCell>
                      <TableCell>
                        <span className="font-medium">{mapping.menu_group_id}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{mapping.menu_icon}</Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <div className="flex gap-1 flex-wrap">
                          {mapping.include_pending && <Badge variant="secondary" className="text-xs">{t('page.optionPending')}</Badge>}
                          {mapping.include_validation && <Badge variant="secondary" className="text-xs">{t('page.optionValidation')}</Badge>}
                          {mapping.include_appointments && <Badge variant="secondary" className="text-xs">{t('page.optionAppointments')}</Badge>}
                          {mapping.include_history && <Badge variant="secondary" className="text-xs">{t('page.optionHistory')}</Badge>}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={mapping.is_active}
                          onCheckedChange={() => handleToggleActive(mapping)}
                          disabled={updateMutation.isPending}
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            asChild
                          >
                            <Link href={`/${locale}/dashboard/admin/workflow-mappings/${mapping.id}`}>
                              <Pencil className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDuplicate(mapping)}
                            disabled={duplicatingId !== null}
                            title={t('actions.duplicate', { defaultValue: 'Duplicar' })}
                          >
                            {duplicatingId === mapping.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            onClick={() => {
                              setSelectedMapping(mapping);
                              setIsDeleteDialogOpen(true);
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                {t('page.pageOf', { page: data.page, pages: data.pages })}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.min(data.pages, prev + 1))}
                  disabled={currentPage >= data.pages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('page.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('page.deleteDescription', { pattern: selectedMapping?.workflow_pattern || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('page.deleteCancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedMapping && deleteMutation.mutate(selectedMapping.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('page.deleteConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Batch Delete Dialog */}
      <AlertDialog open={isBatchDeleteDialogOpen} onOpenChange={setIsBatchDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('page.batchDeleteTitle', { count: selectedIds.size })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('page.batchDeleteDescription', { count: selectedIds.size })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('page.deleteCancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => batchDeleteMutation.mutate(Array.from(selectedIds))}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {batchDeleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('page.batchDeleteConfirm', { count: selectedIds.size })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
