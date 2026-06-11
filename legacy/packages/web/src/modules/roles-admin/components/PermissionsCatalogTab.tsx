'use client';

/**
 * PermissionsCatalogTab Component
 * Read-only catalog of all system permissions with search, filters, and grouping
 *
 * Extracted from monolithic roles/page.tsx for maintainability
 */

import { useState, useEffect, useRef } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
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
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  Search,
  Loader2,
  AlertCircle,
  AlertTriangle,
  Key,
  RefreshCw,
  Building2,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';
import { usePermissions, useModuleNames } from '@/modules/permissions-admin';
import type { Permission } from '@/modules/permissions-admin';

const PERMISSIONS_PAGE_SIZE = 20;

export function PermissionsCatalogTab() {
  const t = useTranslations('admin.permissions');

  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [moduleFilter, setModuleFilter] = useState<string>('all');
  const [criticalFilter, setCriticalFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'grouped' | 'list'>('grouped');
  const [currentPage, setCurrentPage] = useState(1);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounce search (300ms)
  useEffect(() => {
    debounceRef.current = setTimeout(() => {
      setSearchQuery(searchInput);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, moduleFilter, criticalFilter]);

  const { data: permissions = [], isLoading, error, refetch } = usePermissions({
    module_name: moduleFilter === 'all' ? undefined : moduleFilter,
    is_critical: criticalFilter === 'all' ? undefined : criticalFilter === 'critical',
    search: searchQuery || undefined,
  });

  const moduleNames = useModuleNames();

  const filteredPermissions = permissions.filter((perm) => {
    if (criticalFilter === 'normal' && perm.is_critical) return false;
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      perm.name.toLowerCase().includes(query) ||
      perm.description?.toLowerCase().includes(query) ||
      perm.resource.toLowerCase().includes(query)
    );
  });

  const totalPages = Math.ceil(filteredPermissions.length / PERMISSIONS_PAGE_SIZE);
  const paginatedPermissions = viewMode === 'list'
    ? filteredPermissions.slice(
        (currentPage - 1) * PERMISSIONS_PAGE_SIZE,
        currentPage * PERMISSIONS_PAGE_SIZE
      )
    : filteredPermissions;

  const groupedByModule = filteredPermissions.reduce((acc, perm) => {
    const module = perm.module_name || 'other';
    if (!acc[module]) acc[module] = [];
    acc[module].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);

  const stats = {
    total: permissions.length,
    critical: permissions.filter(p => p.is_critical).length,
    modules: new Set(permissions.map(p => p.module_name)).size,
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
            <RefreshCw className="h-4 w-4 mr-2" />
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">{stats.modules} {t('module')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              {t('critical')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-500">{stats.critical}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('module')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.modules}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('found')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{filteredPermissions.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Catalog */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                {t('list')}
              </CardTitle>
              <CardDescription>
                {stats.total} {t('found')}
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-col gap-4 mb-6">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('searchPlaceholder')}
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={moduleFilter} onValueChange={setModuleFilter}>
                <SelectTrigger className="w-full sm:w-[200px]">
                  <SelectValue placeholder={t('module')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allModules')} ({stats.modules})</SelectItem>
                  <Separator className="my-1" />
                  {moduleNames.map((module) => {
                    const count = permissions.filter(p => p.module_name === module).length;
                    return (
                      <SelectItem key={module} value={module}>
                        {module} ({count})
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
              <Select value={criticalFilter} onValueChange={setCriticalFilter}>
                <SelectTrigger className="w-full sm:w-[180px]">
                  <SelectValue placeholder={t('criticality')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allCriticality')}</SelectItem>
                  <SelectItem value="critical">{t('critical')} ({stats.critical})</SelectItem>
                  <SelectItem value="normal">Normal ({stats.total - stats.critical})</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex gap-1 border rounded-lg p-1">
                <Button
                  variant={viewMode === 'grouped' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('grouped')}
                  className="gap-2"
                >
                  <Building2 className="h-4 w-4" />
                  {t('byModule')}
                </Button>
                <Button
                  variant={viewMode === 'list' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('list')}
                  className="gap-2"
                >
                  <Key className="h-4 w-4" />
                  {t('list')}
                </Button>
              </div>
              {viewMode === 'list' && filteredPermissions.length > 0 && (
                <span className="text-sm text-muted-foreground">
                  {(currentPage - 1) * PERMISSIONS_PAGE_SIZE + 1}-
                  {Math.min(currentPage * PERMISSIONS_PAGE_SIZE, filteredPermissions.length)} / {filteredPermissions.length}
                </span>
              )}
            </div>
          </div>

          {viewMode === 'grouped' ? (
            <Accordion type="multiple" className="w-full" defaultValue={Object.keys(groupedByModule).slice(0, 2)}>
              {Object.entries(groupedByModule)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([module, perms]) => (
                <AccordionItem key={module} value={module}>
                  <AccordionTrigger className="hover:no-underline">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="capitalize font-mono">
                        {module}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        {perms.length} permission{perms.length > 1 ? 's' : ''}
                      </span>
                      {perms.some(p => p.is_critical) && (
                        <Badge variant="secondary" className="gap-1 bg-amber-100 text-amber-700 border-amber-300">
                          <AlertTriangle className="h-3 w-3" />
                          {perms.filter(p => p.is_critical).length} {t('critical').toLowerCase()}
                        </Badge>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="border rounded-md mt-2 overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-muted/50">
                            <TableHead className="w-[40%]">{t('description')}</TableHead>
                            <TableHead className="w-[20%]">{t('resource')}</TableHead>
                            <TableHead className="w-[15%]">{t('action')}</TableHead>
                            <TableHead className="w-[25%]">{t('criticality')}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {perms.map((perm) => (
                            <PermissionRow key={perm.id} perm={perm} showModule={false} t={t} />
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          ) : (
            <>
              <div className="border rounded-md overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead className="w-[35%]">{t('description')}</TableHead>
                      <TableHead className="w-[15%]">{t('module')}</TableHead>
                      <TableHead className="w-[15%]">{t('resource')}</TableHead>
                      <TableHead className="w-[10%]">{t('action')}</TableHead>
                      <TableHead className="w-[25%]">{t('criticality')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedPermissions.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-muted-foreground py-12">
                          <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p>{t('noPermissions')}</p>
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedPermissions.map((perm) => (
                        <PermissionRow key={perm.id} perm={perm} showModule t={t} />
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-muted-foreground">
                    {currentPage} / {totalPages} ({filteredPermissions.length})
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
                    <div className="flex items-center gap-1">
                      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                        let pageNum: number;
                        if (totalPages <= 5) {
                          pageNum = i + 1;
                        } else if (currentPage <= 3) {
                          pageNum = i + 1;
                        } else if (currentPage >= totalPages - 2) {
                          pageNum = totalPages - 4 + i;
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
                          >
                            {pageNum}
                          </Button>
                        );
                      })}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage >= totalPages}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Extracted row to avoid duplication between grouped and list views
function PermissionRow({
  perm,
  showModule,
  t,
}: {
  perm: Permission;
  showModule: boolean;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <TableRow className="hover:bg-muted/30">
      <TableCell>
        <div className="space-y-1">
          <div className="font-medium text-sm">
            {perm.description || perm.name}
          </div>
          <code className="text-xs bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
            {perm.name}
          </code>
        </div>
      </TableCell>
      {showModule && (
        <TableCell>
          <Badge variant="outline" className="capitalize font-mono text-xs">
            {perm.module_name || 'other'}
          </Badge>
        </TableCell>
      )}
      <TableCell>
        <Badge variant="secondary" className="font-mono text-xs">
          {perm.resource}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm font-medium text-primary">
          {perm.action}
        </span>
      </TableCell>
      <TableCell>
        {perm.is_critical ? (
          <Badge className="gap-1 bg-amber-100 text-amber-700 border-amber-300 hover:bg-amber-100">
            <AlertTriangle className="h-3 w-3" />
            {t('critical')}
          </Badge>
        ) : (
          <Badge variant="outline" className="text-muted-foreground">Normal</Badge>
        )}
      </TableCell>
    </TableRow>
  );
}
