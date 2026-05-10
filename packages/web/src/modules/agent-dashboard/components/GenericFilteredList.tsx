/**
 * GenericFilteredList - Renders a filtered list of service requests
 * Used by custom sub-menu items (e.g., "Completados") defined via admin UI.
 *
 * Reads filter_params from URL search params and passes them to the API.
 *
 * @module agent-dashboard/components/GenericFilteredList
 * @date 2026-02-21
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import { Search, Eye, RefreshCw, AlertCircle, FileText, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { useEntityServiceRequests } from '../hooks/useEntityServiceRequests';
import type { EntityCode } from '../types';

interface GenericFilteredListProps {
  entityCode: EntityCode;
  entityUrlCode: string;
  searchParams: URLSearchParams;
  action: string;
}

const STATUS_COLORS: Record<string, string> = {
  SUBMITTED: 'bg-cyan-100 text-cyan-800',
  UNDER_REVIEW: 'bg-teal-100 text-teal-800',
  DOSSIER_VALIDE: 'bg-indigo-100 text-indigo-800',
  REJECTED: 'bg-red-100 text-red-800',
  COMPLETED: 'bg-green-200 text-green-900',
  CANCELLED: 'bg-gray-200 text-gray-600',
  APPROVED: 'bg-green-100 text-green-800',
  PAID: 'bg-emerald-100 text-emerald-800',
  EXPIRED: 'bg-gray-300 text-gray-700',
};

const PRIORITY_COLORS: Record<string, string> = {
  URGENT: 'bg-red-500 text-white',
  HIGH: 'bg-orange-500 text-white',
  NORMAL: 'bg-blue-100 text-blue-800',
  LOW: 'bg-gray-100 text-gray-800',
};

export function GenericFilteredList({
  entityCode,
  entityUrlCode,
  searchParams,
  action,
}: GenericFilteredListProps) {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('agent');
  const tCommon = useTranslations('common');

  // Read filter_params from URL search params
  const statusFilter = searchParams.get('status') || undefined;

  // Local state
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  // Fetch data with status filter
  const {
    requests,
    total,
    totalPages,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useEntityServiceRequests({
    entityCode,
    action: 'history', // Use history action as base (includes terminal statuses)
    status: statusFilter,
    search: searchTerm || undefined,
    page: currentPage,
    pageSize,
  });

  const handleRowClick = (requestId: string) => {
    const requestIds = requests.map(r => r.id);
    sessionStorage.setItem('agent-request-ids', JSON.stringify(requestIds));
    router.push(`/${locale}/dashboard/agent/${entityUrlCode}/request/${requestId}`);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Card>
          <CardContent className="pt-6">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-12 w-full mb-2" />
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{tCommon('error')}</AlertTitle>
          <AlertDescription>
            {error?.message || tCommon('errorGeneric')}
          </AlertDescription>
        </Alert>
        <Button onClick={() => refetch()} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          {tCommon('retry')}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Link href={`/${locale}/dashboard/agent/${entityUrlCode}`}>
            <Button variant="ghost" size="sm" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              {tCommon('back')}
            </Button>
          </Link>
          <h1 className="text-2xl font-bold tracking-tight capitalize">
            {action.replace(/-/g, ' ')}
          </h1>
          <p className="text-muted-foreground">
            {total} {t('nav.requests')}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
          {tCommon('refresh')}
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 max-w-md relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('nav.searchPlaceholder')}
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
            className="pl-10"
          />
        </div>
      </div>

      {/* Results Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('nav.requests')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {requests.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <FileText className="h-8 w-8 mb-4" />
              <p className="text-lg font-medium">{t('nav.noRequests')}</p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[140px]">{t('nav.reference')}</TableHead>
                    <TableHead>{t('nav.citizen')}</TableHead>
                    <TableHead className="w-[120px]">Workflow</TableHead>
                    <TableHead className="w-[100px]">{t('nav.priority')}</TableHead>
                    <TableHead className="w-[120px]">{t('nav.status')}</TableHead>
                    <TableHead className="w-[160px]">{t('nav.date')}</TableHead>
                    <TableHead className="w-[80px]">{t('nav.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {requests.map((request) => (
                    <TableRow
                      key={request.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleRowClick(request.id)}
                    >
                      <TableCell className="font-medium">{request.reference}</TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{request.citizenName}</div>
                          {request.citizenEmail && (
                            <div className="text-xs text-muted-foreground">{request.citizenEmail}</div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {request.workflowCode?.replace('_', ' ') || '-'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={PRIORITY_COLORS[request.priority] || PRIORITY_COLORS.NORMAL}>
                          {request.priority}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={STATUS_COLORS[request.status] || 'bg-gray-100'}>
                          {request.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(request.submittedAt || request.createdAt)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRowClick(request.id);
                          }}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, total)} / {total}
                  </p>
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious
                          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                          className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                        />
                      </PaginationItem>
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
                          <PaginationItem key={pageNum}>
                            <PaginationLink
                              onClick={() => setCurrentPage(pageNum)}
                              isActive={currentPage === pageNum}
                              className="cursor-pointer"
                            >
                              {pageNum}
                            </PaginationLink>
                          </PaginationItem>
                        );
                      })}
                      <PaginationItem>
                        <PaginationNext
                          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                          className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
