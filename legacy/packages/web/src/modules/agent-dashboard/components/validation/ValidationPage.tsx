'use client';

/**
 * ValidationPage - Generic verification list page for all entities
 * Lists service requests pending identity/document verification
 *
 * @module agent-dashboard/components/validation
 * @date 2026-01-31
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { RefreshCw, ChevronLeft, Search, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  usePendingVerifications,
  VerificationStatusBadge,
} from '@/modules/verified-identifiers';
import type { PendingVerificationItem } from '@/modules/verified-identifiers';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface ValidationPageProps {
  entityCode: EntityCode;
  /** Base path for navigation (e.g., '/dashboard/agent/dgt') */
  basePath?: string;
  /** Workflow group for detail URL (e.g., 'licencias') */
  workflowGroup?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function ValidationPage({
  entityCode,
  basePath,
  workflowGroup,
}: ValidationPageProps) {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [searchQuery, setSearchQuery] = useState('');

  // Derive entity path from entityCode if basePath not provided
  const entityPath = basePath || `/dashboard/agent/${entityCode.toLowerCase().replace('_', '-')}`;

  const { data, isLoading, isError, refetch, isFetching } =
    usePendingVerifications({
      entityCode,
      verificationStatus: statusFilter,
      page,
      pageSize,
    });

  const handleRowClick = (item: PendingVerificationItem) => {
    const detailPath = workflowGroup
      ? `/${locale}${entityPath}/${workflowGroup}/validation/${item.id}`
      : `/${locale}${entityPath}/validation/${item.id}`;
    router.push(`${detailPath}?entity=${entityCode}`);
  };

  const handleBack = () => {
    router.push(`/${locale}${entityPath}`);
  };

  // Filter items by search query (client-side)
  const filteredItems =
    data?.items.filter(
      (item) =>
        !searchQuery ||
        item.reference.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.citizenName.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleBack}>
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {t('verification.title', { defaultValue: 'Verificación de Identidad' })}
            </h1>
            <p className="text-muted-foreground">
              {t('verification.subtitle', {
                defaultValue: 'Solicitudes pendientes de verificación de documentos',
              })}
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw
            className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`}
          />
          {t('common.refresh', { defaultValue: 'Actualizar' })}
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('common.search', { defaultValue: 'Buscar por referencia o nombre...' })}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[200px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Estado" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pending">
                  {t('verification.pending', { defaultValue: 'Pendiente' })}
                </SelectItem>
                <SelectItem value="verified_manually">
                  {t('verification.verified_manually', { defaultValue: 'Verificado manualmente' })}
                </SelectItem>
                <SelectItem value="verification_failed">
                  {t('verification.failed', { defaultValue: 'Fallido' })}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Stats summary */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('verification.totalPending', { defaultValue: 'Total pendientes' })}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-3xl font-bold">{data.total}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('common.page', { defaultValue: 'Página' })}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-3xl font-bold">
                {data.page} / {Math.ceil(data.total / data.pageSize) || 1}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('common.showing', { defaultValue: 'Mostrando' })}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-3xl font-bold">
                {filteredItems.length} {t('common.of', { defaultValue: 'de' })} {data.items.length}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Table */}
      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="text-center py-12 text-red-500">
              {t('common.error', { defaultValue: 'Error al cargar los datos' })}
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              {t('verification.noPending', {
                defaultValue: 'No hay verificaciones pendientes',
              })}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    {t('common.reference', { defaultValue: 'Referencia' })}
                  </TableHead>
                  <TableHead>
                    {t('common.citizen', { defaultValue: 'Ciudadano' })}
                  </TableHead>
                  <TableHead>
                    {t('verification.identifiers', { defaultValue: 'Identificadores' })}
                  </TableHead>
                  <TableHead>
                    {t('verification.pending', { defaultValue: 'Pendientes' })}
                  </TableHead>
                  <TableHead>
                    {t('common.status', { defaultValue: 'Estado' })}
                  </TableHead>
                  <TableHead>
                    {t('common.date', { defaultValue: 'Fecha' })}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleRowClick(item)}
                  >
                    <TableCell className="font-medium">
                      {item.reference}
                    </TableCell>
                    <TableCell>{item.citizenName}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {item.identifiers.slice(0, 3).map((id, idx) => (
                          <Badge
                            key={idx}
                            variant="outline"
                            className="text-xs"
                          >
                            {id.identifierType}: {id.value.substring(0, 8)}...
                          </Badge>
                        ))}
                        {item.identifiers.length > 3 && (
                          <Badge variant="secondary" className="text-xs">
                            +{item.identifiers.length - 3}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={item.pendingCount > 0 ? 'destructive' : 'default'}
                        className={
                          item.pendingCount === 0
                            ? 'bg-green-500'
                            : ''
                        }
                      >
                        {item.pendingCount} / {item.identifiers.length}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <VerificationStatusBadge
                        status={item.verificationStatus}
                        showIcon={false}
                      />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.submittedAt
                        ? new Date(item.submittedAt).toLocaleDateString('es-ES')
                        : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {data && data.total > pageSize && (
            <div className="flex items-center justify-between pt-4 border-t mt-4">
              <p className="text-sm text-muted-foreground">
                {t('common.showingOf', {
                  defaultValue: `Mostrando ${(page - 1) * pageSize + 1}-${Math.min(
                    page * pageSize,
                    data.total
                  )} de ${data.total}`,
                })}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  {t('common.previous', { defaultValue: 'Anterior' })}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page * pageSize >= data.total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t('common.next', { defaultValue: 'Siguiente' })}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default ValidationPage;
