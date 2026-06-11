'use client';

/**
 * Display Configuration Admin Page
 * Manage workflow display configurations (columns and sections per workflow)
 *
 * @module dashboard/admin/menu-config/display
 * @date 2026-02-01
 */

import { useState, useCallback, useEffect } from 'react';
import { useTranslations } from 'next-intl';
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
  LayoutGrid,
  Plus,
  Search,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Columns,
  Rows,
  ArrowLeft,
  Check,
  X,
  Copy,
} from 'lucide-react';
import Link from 'next/link';
import { useLocale } from 'next-intl';
import { toast } from 'sonner';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import {
  useDisplayConfigOperations,
  useCreateDisplayConfig,
  AVAILABLE_SECTIONS,
} from '@/modules/admin/hooks';
import type { DisplayConfig } from '@/modules/admin/services/menuConfigService';

// =============================================================================
// MAIN PAGE COMPONENT
// =============================================================================

export default function DisplayConfigPage() {
  const t = useTranslations('admin.menuConfig.displayConfig');
  const locale = useLocale();
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedConfig, setSelectedConfig] = useState<DisplayConfig | null>(null);
  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isBatchDeleteDialogOpen, setIsBatchDeleteDialogOpen] = useState(false);
  const [batchAction, setBatchAction] = useState<'activate' | 'deactivate' | 'delete' | null>(null);
  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);

  const createMutation = useCreateDisplayConfig();

  const {
    configs,
    total,
    pages,
    isLoading,
    isError,
    error,
    refetch,
    updateConfigAsync,
    deleteConfigAsync,
    isUpdating,
    isDeleting,
  } = useDisplayConfigOperations({ page: currentPage, page_size: 10 });

  // P1-7: Reset pagination when search query changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  // P1-7: Clear selection when page changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [currentPage]);

  const filteredConfigs = configs.filter((config) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return config.workflow_code.toLowerCase().includes(query);
  });

  const handleDelete = async () => {
    if (!selectedConfig) return;
    await deleteConfigAsync(selectedConfig.id, selectedConfig.workflow_code);
    setIsDeleteDialogOpen(false);
    setSelectedConfig(null);
  };

  const handleToggleActive = async (config: DisplayConfig) => {
    await updateConfigAsync(config.id, { is_active: !config.is_active });
  };

  // Bulk selection helpers
  const isAllSelected = filteredConfigs.length > 0 &&
    filteredConfigs.every(c => selectedIds.has(c.id));
  const isSomeSelected = selectedIds.size > 0 && !isAllSelected;

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(filteredConfigs.map(c => c.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: number, checked: boolean) => {
    const newSet = new Set(selectedIds);
    if (checked) newSet.add(id); else newSet.delete(id);
    setSelectedIds(newSet);
  };

  const handleBatchActivate = async () => {
    setBatchAction('activate');
    try {
      const results = await Promise.allSettled(
        Array.from(selectedIds).map(id => updateConfigAsync(id, { is_active: true }))
      );
      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;
      if (failed > 0) {
        toast.warning(t('batchActivatedPartial', { succeeded: String(succeeded), failed: String(failed) }));
      } else {
        toast.success(t('batchActivated', { succeeded: String(succeeded) }));
      }
      setSelectedIds(new Set());
    } finally { setBatchAction(null); }
  };

  const handleBatchDeactivate = async () => {
    setBatchAction('deactivate');
    try {
      const results = await Promise.allSettled(
        Array.from(selectedIds).map(id => updateConfigAsync(id, { is_active: false }))
      );
      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;
      if (failed > 0) {
        toast.warning(t('batchDeactivatedPartial', { succeeded: String(succeeded), failed: String(failed) }));
      } else {
        toast.success(t('batchDeactivated', { succeeded: String(succeeded) }));
      }
      setSelectedIds(new Set());
    } finally { setBatchAction(null); }
  };

  const handleBatchDelete = async () => {
    setBatchAction('delete');
    try {
      const results = await Promise.allSettled(
        Array.from(selectedIds).map(id => deleteConfigAsync(id))
      );
      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;
      if (failed > 0) {
        toast.warning(t('batchDeletedPartial', { succeeded: String(succeeded), failed: String(failed) }));
      } else {
        toast.success(t('batchDeleted', { succeeded: String(succeeded) }));
      }
      setSelectedIds(new Set());
      setIsBatchDeleteDialogOpen(false);
    } finally { setBatchAction(null); }
  };

  // Clone handler — unique suffix to avoid duplicate workflow_code
  const handleDuplicate = useCallback(async (config: DisplayConfig) => {
    setDuplicatingId(config.id);
    try {
      const suffix = '_COPY_' + Date.now().toString(36).slice(-4).toUpperCase();
      await createMutation.mutateAsync({
        workflow_code: config.workflow_code + suffix,
        list_columns: config.list_columns,
        preview_sections: config.preview_sections,
        labels: config.labels ?? undefined,
      });
      toast.success(t('duplicated'));
    } catch { /* errors handled by hook */ }
    finally { setDuplicatingId(null); }
  }, [createMutation, t]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : t('messages.loadError')}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            {t('actions.retry')}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: 'Admin', href: `/${locale}/dashboard/admin` },
        { label: 'Menu Config', href: `/${locale}/dashboard/admin/menu-config` },
        { label: t('title') },
      ]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/${locale}/dashboard/admin/menu-config`}>
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <LayoutGrid className="h-8 w-8" />
              {t('title')}
            </h1>
            <p className="text-muted-foreground mt-2">{t('subtitle')}</p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('statsTotal')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Columns className="h-4 w-4" />
              {t('statsColumns')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground">{t('statsColumnsSubtitle')}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Rows className="h-4 w-4" />
              {t('statsSections')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{AVAILABLE_SECTIONS.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('title')}</CardTitle>
              <CardDescription>{t('subtitle')}</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {t('refresh')}
              </Button>
              <Button size="sm" asChild>
                <Link href={`/${locale}/dashboard/admin/menu-config/display/new`}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('createTitle')}
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
                placeholder={t('searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Batch Actions Bar */}
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-3 p-3 mb-4 bg-muted/50 border rounded-lg">
              <span className="text-sm font-medium">
                {t('selectedCount', { count: selectedIds.size })}
              </span>
              <div className="flex-1" />
              <Button size="sm" variant="outline" onClick={handleBatchActivate} disabled={batchAction !== null}>
                {batchAction === 'activate' ? <Loader2 className="mr-2 h-3 w-3 animate-spin" /> : <Check className="mr-1 h-3 w-3" />}
                {t('bulkActivateBtn')}
              </Button>
              <Button size="sm" variant="outline" onClick={handleBatchDeactivate} disabled={batchAction !== null}>
                {batchAction === 'deactivate' ? <Loader2 className="mr-2 h-3 w-3 animate-spin" /> : <X className="mr-1 h-3 w-3" />}
                {t('bulkDeactivateBtn')}
              </Button>
              <Button size="sm" variant="destructive" onClick={() => setIsBatchDeleteDialogOpen(true)} disabled={batchAction !== null}>
                <Trash2 className="mr-1 h-3 w-3" />
                {t('bulkDeleteBtn')}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
                {t('cancelBtn')}
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
                      aria-label={t('selectAll')}
                    />
                  </TableHead>
                  <TableHead>{t('pattern')}</TableHead>
                  <TableHead>{t('listColumns')}</TableHead>
                  <TableHead>{t('previewSections')}</TableHead>
                  <TableHead>{t('tableStatus')}</TableHead>
                  <TableHead className="text-right">{t('tableActions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredConfigs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      {t('noConfigsFound')}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredConfigs.map((config) => (
                    <TableRow key={config.id} data-state={selectedIds.has(config.id) ? 'selected' : undefined}>
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(config.id)}
                          onCheckedChange={(checked) => handleSelectOne(config.id, !!checked)}
                          aria-label={t('selectRow', { code: config.workflow_code })}
                        />
                      </TableCell>
                      <TableCell>
                        <code className="text-sm bg-muted px-2 py-1 rounded">
                          {config.workflow_code}
                        </code>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap max-w-[200px]">
                          {config.list_columns.slice(0, 3).map((col) => (
                            <Badge key={col} variant="secondary" className="text-xs">
                              {col}
                            </Badge>
                          ))}
                          {config.list_columns.length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{config.list_columns.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap max-w-[200px]">
                          {config.preview_sections.slice(0, 3).map((sec) => (
                            <Badge key={sec} variant="secondary" className="text-xs">
                              {sec}
                            </Badge>
                          ))}
                          {config.preview_sections.length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{config.preview_sections.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={config.is_active}
                          onCheckedChange={() => handleToggleActive(config)}
                          disabled={isUpdating}
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="icon" asChild>
                            <Link
                              href={`/${locale}/dashboard/admin/menu-config/display/${config.id}`}
                            >
                              <Pencil className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDuplicate(config)}
                            disabled={duplicatingId !== null}
                            title={t('duplicate')}
                          >
                            {duplicatingId === config.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            onClick={() => {
                              setSelectedConfig(config);
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
          {pages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                {t('pageOf', { current: currentPage, total: pages })}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                  disabled={currentPage <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((prev) => Math.min(pages, prev + 1))}
                  disabled={currentPage >= pages}
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
            <AlertDialogTitle>{t('confirmDelete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('confirmDeleteDescription', { pattern: selectedConfig?.workflow_code })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('cancelBtn')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('deleteBtn')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Batch Delete Dialog */}
      <AlertDialog open={isBatchDeleteDialogOpen} onOpenChange={setIsBatchDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('confirmBulkDelete', { count: selectedIds.size })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('confirmBulkDeleteDescription', { count: selectedIds.size })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('cancelBtn')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBatchDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {batchAction === 'delete' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('confirmBulkDeleteAction', { count: selectedIds.size })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
