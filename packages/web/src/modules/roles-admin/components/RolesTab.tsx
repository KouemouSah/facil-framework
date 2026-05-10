'use client';

/**
 * RolesTab Component — Phase 2 RBAC Engine Core
 *
 * Features:
 * - Clone role (1-click duplication)
 * - Export CSV
 * - Bulk delete (multi-select)
 * - Inline search + entity filter
 * - Slide-in panel for quick role preview
 */

import { useState, useEffect, useRef } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
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
  SheetDescription,
} from '@/components/ui/sheet';
import {
  Shield,
  Plus,
  Search,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  Lock,
  Building2,
  ChevronRight,
  ChevronLeft,
  Grid3X3,
  List,
  Copy,
  Download,
} from 'lucide-react';
import { toast } from 'sonner';
import { useRoles, useDeleteRole, useCloneRole, useBulkDeleteRoles, useRoleWithPermissions, rolesApi } from '@/modules/roles-admin';
import type { Role } from '@/modules/roles-admin';
import { PermissionMatrix } from './PermissionMatrix';

const PAGE_SIZE = 10;

export function RolesTab() {
  const t = useTranslations('admin.roles');
  const locale = useLocale();

  const [viewMode, setViewMode] = useState<'list' | 'matrix'>('list');
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('all');
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounce search (300ms)
  useEffect(() => {
    debounceRef.current = setTimeout(() => {
      setSearchQuery(searchInput);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]);

  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isBulkDeleteDialogOpen, setIsBulkDeleteDialogOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Multi-select for bulk actions
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Slide-in panel for quick preview
  const [previewRoleId, setPreviewRoleId] = useState<string | null>(null);

  useEffect(() => {
    setCurrentPage(1);
  }, [entityTypeFilter]);

  const { data: rolesData, isLoading, error, refetch } = useRoles({
    entity_type: entityTypeFilter === 'all' ? undefined : entityTypeFilter === 'null' ? null : entityTypeFilter,
    page: currentPage,
    page_size: PAGE_SIZE,
  });

  const deleteMutation = useDeleteRole();
  const cloneMutation = useCloneRole();
  const bulkDeleteMutation = useBulkDeleteRoles();

  // Preview role data
  const { data: previewRole } = useRoleWithPermissions(previewRoleId || '');

  const filteredRoles = rolesData?.roles?.filter((role: Role) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      role.name.toLowerCase().includes(query) ||
      role.code.toLowerCase().includes(query) ||
      role.description?.toLowerCase().includes(query)
    );
  }) || [];

  // Selection handlers
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredRoles.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredRoles.map((r: Role) => r.id)));
    }
  };

  const handleDeleteRole = async () => {
    if (!selectedRole) return;
    try {
      await deleteMutation.mutateAsync(selectedRole.id);
      toast.success(t('deleteSuccess'));
      setIsDeleteDialogOpen(false);
      setSelectedRole(null);
      selectedIds.delete(selectedRole.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('errorDeleting'));
    }
  };

  const handleCloneRole = async (role: Role) => {
    try {
      const cloned = await cloneMutation.mutateAsync({ roleId: role.id });
      toast.success(`Rol "${cloned.name}" clonado correctamente`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Error al clonar el rol');
    }
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    try {
      const result = await bulkDeleteMutation.mutateAsync(ids);
      toast.success(`${result.deleted_count} roles eliminados`);
      if (result.failed_count > 0) {
        toast.warning(`${result.failed_count} roles no se pudieron eliminar`);
      }
      setSelectedIds(new Set());
      setIsBulkDeleteDialogOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Error al eliminar roles');
    }
  };

  const handleExportCsv = async () => {
    try {
      await rolesApi.exportCsv();
      toast.success('Exportado correctamente');
    } catch {
      toast.error('Error al exportar');
    }
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
            <span>{error instanceof Error ? error.message : t('errorLoading')}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            Reintentar
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Matrix view
  if (viewMode === 'matrix') {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">{t('permissionsTab')} Matrix</h3>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setViewMode('list')}
            className="gap-2"
          >
            <List className="h-4 w-4" />
            {t('title')}
          </Button>
        </div>
        <PermissionMatrix />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('totalRoles', { count: rolesData?.total || 0 })}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{rolesData?.total || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('system')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rolesData?.roles?.filter((r: Role) => r.is_system).length || 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('custom')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rolesData?.roles?.filter((r: Role) => !r.is_system).length || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Roles Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('title')}</CardTitle>
              <CardDescription>
                {t('found', { count: filteredRoles.length })}
                {selectedIds.size > 0 && (
                  <span className="ml-2 text-primary font-medium">
                    ({selectedIds.size} seleccionados)
                  </span>
                )}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {/* Bulk actions toolbar */}
              {selectedIds.size > 0 && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setIsBulkDeleteDialogOpen(true)}
                  className="gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  Eliminar ({selectedIds.size})
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportCsv}
                className="gap-2"
                title="Exportar CSV"
              >
                <Download className="h-4 w-4" />
                CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setViewMode('matrix')}
                className="gap-2"
              >
                <Grid3X3 className="h-4 w-4" />
                Matrix
              </Button>
              <Link href={`/${locale}/dashboard/admin/roles/new`}>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  {t('createRole')}
                </Button>
              </Link>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('searchPlaceholder')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={entityTypeFilter} onValueChange={setEntityTypeFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allTypes')}</SelectItem>
                <SelectItem value="null">{t('global')}</SelectItem>
                <SelectItem value="agent">{t('ministry')}</SelectItem>
                <SelectItem value="entity_agent">{t('entityType')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="border rounded-md overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40px]">
                    <Checkbox
                      checked={filteredRoles.length > 0 && selectedIds.size === filteredRoles.length}
                      onCheckedChange={toggleSelectAll}
                    />
                  </TableHead>
                  <TableHead>{t('roleName')}</TableHead>
                  <TableHead>{t('roleCode')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('entityType')}</TableHead>
                  <TableHead>{t('status')}</TableHead>
                  <TableHead className="text-right">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRoles.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      {t('noRoles')}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredRoles.map((role: Role) => (
                    <TableRow
                      key={role.id}
                      className={selectedIds.has(role.id) ? 'bg-accent/50' : undefined}
                    >
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(role.id)}
                          onCheckedChange={() => toggleSelect(role.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <button
                          onClick={() => setPreviewRoleId(role.id)}
                          className="flex items-center gap-2 text-left hover:underline"
                        >
                          <Shield className="h-4 w-4 text-muted-foreground shrink-0" />
                          <div>
                            <div className="font-medium">{role.name}</div>
                            {role.description && (
                              <div className="text-sm text-muted-foreground truncate max-w-[300px]">
                                {role.description}
                              </div>
                            )}
                          </div>
                        </button>
                      </TableCell>
                      <TableCell>
                        <code className="text-sm bg-muted px-2 py-1 rounded">{role.code}</code>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {role.entity_type ? (
                          <Badge variant="outline" className="gap-1">
                            <Building2 className="h-3 w-3" />
                            {role.entity_type}
                          </Badge>
                        ) : (
                          <Badge variant="secondary">{t('global')}</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {role.is_system ? (
                          <Badge variant="default" className="gap-1">
                            <Lock className="h-3 w-3" />
                            {t('system')}
                          </Badge>
                        ) : (
                          <Badge variant="outline">{t('custom')}</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleCloneRole(role)}
                            disabled={cloneMutation.isPending}
                            title="Clonar rol"
                            className="h-8 w-8"
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          <Link href={`/${locale}/dashboard/admin/roles/${role.id}`}>
                            <Button
                              variant="ghost"
                              size="icon"
                              title={t('editRole')}
                              className="h-8 w-8"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </Link>
                          {!role.is_system && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => {
                                setSelectedRole(role);
                                setIsDeleteDialogOpen(true);
                              }}
                              className="text-destructive hover:text-destructive h-8 w-8"
                              title={t('deleteRole')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {rolesData && rolesData.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                {currentPage} / {rolesData.total_pages} ({rolesData.total})
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage <= 1 || isLoading}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, rolesData.total_pages) }, (_, i) => {
                    let pageNum: number;
                    if (rolesData.total_pages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= rolesData.total_pages - 2) {
                      pageNum = rolesData.total_pages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }
                    return (
                      <Button
                        key={pageNum}
                        variant={currentPage === pageNum ? 'default' : 'outline'}
                        size="sm"
                        className="w-8 h-8 p-0"
                        onClick={() => setCurrentPage(pageNum)}
                        disabled={isLoading}
                      >
                        {pageNum}
                      </Button>
                    );
                  })}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.min(rolesData.total_pages, prev + 1))}
                  disabled={currentPage >= rolesData.total_pages || isLoading}
                >
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Slide-in Role Preview Panel */}
      <Sheet open={!!previewRoleId} onOpenChange={(open) => !open && setPreviewRoleId(null)}>
        <SheetContent className="w-[400px] sm:w-[500px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              {previewRole?.name || 'Cargando...'}
            </SheetTitle>
            <SheetDescription>
              <code className="text-sm bg-muted px-2 py-1 rounded">{previewRole?.code}</code>
              {previewRole?.entity_type && (
                <Badge variant="outline" className="ml-2">{previewRole.entity_type}</Badge>
              )}
            </SheetDescription>
          </SheetHeader>

          {previewRole && (
            <div className="mt-6 space-y-4">
              {previewRole.description && (
                <p className="text-sm text-muted-foreground">{previewRole.description}</p>
              )}

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  Permisos ({previewRole.permissions_count || previewRole.permissions?.length || 0})
                </span>
                <Link href={`/${locale}/dashboard/admin/roles/${previewRoleId}`}>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Pencil className="h-3 w-3" />
                    Editar
                  </Button>
                </Link>
              </div>

              {/* Permission list grouped by module */}
              <div className="space-y-2 max-h-[calc(100vh-250px)] overflow-y-auto">
                {(() => {
                  const permissions = previewRole.permissions || [];
                  const grouped: Record<string, string[]> = {};
                  permissions.forEach((p: { name?: string } | string) => {
                    const name = typeof p === 'string' ? p : p.name || '';
                    const module = name.split('.')[0] || 'other';
                    if (!grouped[module]) grouped[module] = [];
                    grouped[module].push(name);
                  });
                  return Object.entries(grouped).sort().map(([module, perms]) => (
                    <div key={module} className="border rounded p-2">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold uppercase text-muted-foreground">{module}</span>
                        <Badge variant="secondary" className="text-xs">{perms.length}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {perms.sort().map(perm => (
                          <Badge key={perm} variant="outline" className="text-xs font-mono">
                            {perm.split('.').slice(1).join('.')}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Delete Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('confirmDelete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteRoleConfirmation', { name: selectedRole?.name || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteRole}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('deleteConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Delete Dialog */}
      <AlertDialog open={isBulkDeleteDialogOpen} onOpenChange={setIsBulkDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar {selectedIds.size} roles</AlertDialogTitle>
            <AlertDialogDescription>
              Esta accion es irreversible. Los roles del sistema no seran eliminados.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBulkDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {bulkDeleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Eliminar {selectedIds.size} roles
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
