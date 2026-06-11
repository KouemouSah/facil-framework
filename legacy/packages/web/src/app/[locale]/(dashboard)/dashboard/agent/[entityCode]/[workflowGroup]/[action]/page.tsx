/**
 * Dynamic Workflow Action Page - Unified for ALL Agent Entities
 * Displays service requests table with filters for pending, validation, appointments, history
 *
 * This single page handles all entities:
 *   - ALL entities including cnedoge-pasaporte and cnedoge-residencia
 *   - Entity-specific filters driven by declarative config (entity-filters.ts)
 *   - Zero entity-name branching in this component
 *
 * @route /[locale]/dashboard/agent/[entityCode]/[workflowGroup]/[action]
 * @date 2026-01-30
 */

'use client';

import { useState, useMemo, useCallback } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useLocale } from 'next-intl';
import Link from 'next/link';

// UI Components
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
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
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';

// Icons
import {
  Clock,
  CheckCircle,
  Calendar,
  History,
  ArrowLeft,
  Search,
  Filter,
  AlertCircle,
  Eye,
  AlertTriangle,
  FileText,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';

// Hooks
import { useEntityServiceRequests, type ActionType } from '@/modules/agent-dashboard/hooks';
import useMenuConfig from '@/modules/agent-dashboard/hooks/useMenuConfig';
import { useAgentDashboard } from '@/modules/agent-dashboard/hooks';

// Split View for pending action
import { PendingPage } from '@/modules/agent-dashboard/components/pending/PendingPage';
// Validation and History pages
import { ValidationPage } from '@/modules/agent-dashboard/components/validation';
import { HistoryPage } from '@/modules/agent-dashboard/components/history';
import { EscalationsPage } from '@/modules/agent-dashboard/components/escalations';
import { GenericFilteredList } from '@/modules/agent-dashboard/components/GenericFilteredList';
import { slugToEntityCode } from '@/modules/agent-dashboard/utils';

// Declarative entity config — backend-driven via availableWorkflows
import {
  ENTITY_WORKFLOW_TITLES,
  buildEffectiveFilters,
  resolveTypeLabel,
} from '@/modules/agent-dashboard/config/entity-filters';

// =============================================================================
// CONSTANTS
// =============================================================================

// Standard actions with dedicated components
const STANDARD_ACTIONS: ActionType[] = ['pending', 'validation', 'appointments', 'escalations', 'history'];

const ACTION_ICONS: Record<ActionType, React.ReactNode> = {
  pending: <Clock className="h-5 w-5" />,
  validation: <CheckCircle className="h-5 w-5" />,
  appointments: <Calendar className="h-5 w-5" />,
  escalations: <ShieldAlert className="h-5 w-5" />,
  history: <History className="h-5 w-5" />,
};

const ACTION_COLORS: Record<ActionType, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  validation: 'bg-blue-100 text-blue-800',
  appointments: 'bg-green-100 text-green-800',
  escalations: 'bg-orange-100 text-orange-800',
  history: 'bg-gray-100 text-gray-800',
};

const STATUS_COLORS: Record<string, string> = {
  SUBMITTED: 'bg-cyan-100 text-cyan-800',
  UNDER_REVIEW: 'bg-teal-100 text-teal-800',
  DOSSIER_VALIDE: 'bg-indigo-100 text-indigo-800',
  REJECTED: 'bg-red-100 text-red-800',
  CITA_SCHEDULED: 'bg-sky-100 text-sky-800',
  IN_PROGRESS: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-green-200 text-green-900',
  CANCELLED: 'bg-gray-200 text-gray-600',
  DOCUMENTS_REQUIRED: 'bg-orange-100 text-orange-800',
  PAYMENT_PENDING: 'bg-amber-100 text-amber-800',
  PAID: 'bg-emerald-100 text-emerald-800',
  APPROVED: 'bg-green-100 text-green-800',
};

const PRIORITY_COLORS: Record<string, string> = {
  URGENT: 'bg-red-500 text-white',
  HIGH: 'bg-orange-500 text-white',
  NORMAL: 'bg-blue-100 text-blue-800',
  LOW: 'bg-gray-100 text-gray-800',
};

const SLA_COLORS: Record<string, string> = {
  on_track: 'text-green-600',
  at_risk: 'text-yellow-600',
  violated: 'text-red-600',
};

// =============================================================================
// COMPONENT
// =============================================================================

export default function UnifiedWorkflowActionPage() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('agent');
  const tCommon = useTranslations('common');

  const searchParams = useSearchParams();

  // Extract route params (URL slug only used for navigation, NOT for API calls)
  const entityCodeSlug = (params?.entityCode as string) || '';
  const workflowGroup = (params?.workflowGroup as string) || '';
  const action = (params?.action as string) || '';

  // Entity code: ALWAYS from agent profile (BD source of truth).
  // The URL slug is a routing concern only — never sent to backend APIs.
  // This handles both:
  //   - /agent/oms/... (shared OMS module, 10 entity roles)
  //   - /agent/cnedoge-pasaporte/... (entity-specific route)
  const { entityCode: profileEntityCode } = useAgentDashboard();
  const ENTITY_CODE = profileEntityCode || slugToEntityCode(entityCodeSlug);

  // Validate action — standard actions get dedicated components, others get GenericFilteredList
  const isStandardAction = STANDARD_ACTIONS.includes(action as ActionType);
  const currentAction = isStandardAction ? (action as ActionType) : 'pending';
  const isValidAction = isStandardAction;

  // Backend-driven: get availableWorkflows from menu config API
  const { availableWorkflows } = useMenuConfig();

  // Build effective filters from backend workflows + optional static config
  const effectiveFilters = useMemo(
    () => buildEffectiveFilters(ENTITY_CODE, availableWorkflows),
    [ENTITY_CODE, availableWorkflows],
  );

  // Filter state — generic Record for entity-specific filters
  const [searchTerm, setSearchTerm] = useState('');
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [priority, setPriority] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  // Handle entity-specific filter change (with cascading reset for dependent filters)
  const handleFilterChange = useCallback((key: string, value: string) => {
    setFilterValues(prev => {
      const next = { ...prev, [key]: value };
      // Reset dependent filters when parent value changes
      for (const filter of effectiveFilters) {
        if (filter.showWhen?.filterKey === key && value !== filter.showWhen.value) {
          next[filter.key] = 'all';
        }
      }
      return next;
    });
    setCurrentPage(1);
  }, [effectiveFilters]);

  // Extract filter value (returns undefined for 'all' or unset)
  const getFilterValue = (key: string): string | undefined => {
    const val = filterValues[key];
    return val && val !== 'all' ? val : undefined;
  };

  // Fetch service requests
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
    entityCode: ENTITY_CODE,
    action: currentAction,
    search: searchTerm || undefined,
    priority: priority !== 'all' ? (priority as 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT') : undefined,
    solicitudType: getFilterValue('solicitudType') as 'expedicion' | 'renovacion' | undefined,
    motivo: getFilterValue('motivo') as 'vencimiento' | 'perdida' | 'robo' | 'deterioro' | undefined,
    workflowCode: getFilterValue('workflowCode'),
    page: currentPage,
    pageSize,
    enabled: isValidAction,
  });

  // Formatted workflow group name
  const formattedWorkflowGroup = useMemo(() => {
    const titleKey = ENTITY_WORKFLOW_TITLES[ENTITY_CODE];
    if (titleKey) {
      try {
        return t(titleKey);
      } catch {
        // Fallback to formatted workflowGroup
      }
    }
    if (!workflowGroup) return '';
    return workflowGroup
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }, [workflowGroup, ENTITY_CODE, t]);

  // Handle row click - save all request IDs for navigation
  const handleRowClick = (requestId: string) => {
    const requestIds = requests.map(r => r.id);
    sessionStorage.setItem('agent-request-ids', JSON.stringify(requestIds));
    router.push(`/${locale}/dashboard/agent/${entityCodeSlug}/request/${requestId}`);
  };

  // Reset filters
  const handleResetFilters = () => {
    setSearchTerm('');
    setFilterValues({});
    setPriority('all');
    setCurrentPage(1);
  };

  // Format date
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

  // Use split view for pending action (optimized for bulk processing)
  if (currentAction === 'pending') {
    return <PendingPage entityCode={ENTITY_CODE} />;
  }

  // Use ValidationPage for validation action
  if (currentAction === 'validation') {
    return (
      <ValidationPage
        entityCode={ENTITY_CODE}
        basePath={`/dashboard/agent/${entityCodeSlug}`}
        workflowGroup={workflowGroup as string}
      />
    );
  }

  // Use EscalationsPage for escalations action
  if (currentAction === 'escalations') {
    return (
      <EscalationsPage
        entityCode={ENTITY_CODE}
        basePath={`/dashboard/agent/${entityCodeSlug}`}
      />
    );
  }

  // Use HistoryPage for history action
  if (currentAction === 'history') {
    return (
      <HistoryPage
        entityCode={ENTITY_CODE}
        workflowCodes={availableWorkflows.length > 0 ? availableWorkflows : undefined}
        basePath={`/dashboard/agent/${entityCodeSlug}`}
      />
    );
  }

  // Non-standard action — render GenericFilteredList (for custom sub-items like "Completados")
  if (!isStandardAction) {
    return (
      <GenericFilteredList
        entityCode={ENTITY_CODE}
        entityUrlCode={entityCodeSlug}
        action={action}
        searchParams={searchParams}
      />
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="flex gap-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-10 w-40" />
          <Skeleton className="h-10 w-40" />
        </div>
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
          <AlertTitle>{t('table.loadError')}</AlertTitle>
          <AlertDescription>
            {error?.message || t('table.loadErrorDesc')}
          </AlertDescription>
        </Alert>
        <Button onClick={() => refetch()} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          {t('table.retry')}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href={`/${locale}/dashboard/agent/${entityCodeSlug}`}>
              <Button variant="ghost" size="sm" className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                {tCommon('back')}
              </Button>
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${ACTION_COLORS[currentAction]}`}>
              {ACTION_ICONS[currentAction]}
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                {formattedWorkflowGroup} - {t(`nav.${currentAction}`)}
              </h1>
              <p className="text-muted-foreground">
                {t('table.found', { count: total })}
              </p>
            </div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
          {t('table.refresh')}
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="h-4 w-4" />
            {t('filters.title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('filters.search')}
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Entity-specific filters (backend-driven + optional static config) */}
            {effectiveFilters.map((filter) => {
              // Check conditional visibility
              if (filter.showWhen) {
                const depValue = filterValues[filter.showWhen.filterKey];
                if (depValue !== filter.showWhen.value) return null;
              }

              return (
                <Select
                  key={filter.key}
                  value={filterValues[filter.key] || 'all'}
                  onValueChange={(value) => handleFilterChange(filter.key, value)}
                >
                  <SelectTrigger className={filter.width}>
                    <SelectValue placeholder={t(filter.placeholderKey)} />
                  </SelectTrigger>
                  <SelectContent>
                    {filter.options?.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.isRawLabel ? opt.labelKey : t(opt.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              );
            })}

            {/* Priority */}
            <Select
              value={priority}
              onValueChange={(value) => {
                setPriority(value);
                setCurrentPage(1);
              }}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder={t('filters.priority')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('filters.allPriorities')}</SelectItem>
                <SelectItem value="URGENT">{t('filters.urgent')}</SelectItem>
                <SelectItem value="HIGH">{t('filters.high')}</SelectItem>
                <SelectItem value="NORMAL">{t('filters.normal')}</SelectItem>
                <SelectItem value="LOW">{t('filters.low')}</SelectItem>
              </SelectContent>
            </Select>

            {/* Reset Filters */}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleResetFilters}
              className="text-muted-foreground"
            >
              {t('filters.clear')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('table.requests')}
          </CardTitle>
          <CardDescription>
            {t('table.clickToView')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {requests.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              {ACTION_ICONS[currentAction]}
              <p className="mt-4 text-lg font-medium">
                {t('table.noRequests')}
              </p>
              <p className="text-sm">
                {t('table.noRequestsFiltered')}
              </p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[140px]">{t('table.reference')}</TableHead>
                    <TableHead>{t('table.applicant')}</TableHead>
                    <TableHead className="w-[120px]">{t('table.tipo')}</TableHead>
                    <TableHead className="w-[100px]">{t('table.priority')}</TableHead>
                    <TableHead className="w-[120px]">{t('table.status')}</TableHead>
                    <TableHead className="w-[80px]">{t('table.sla')}</TableHead>
                    <TableHead className="w-[160px]">{t('table.date')}</TableHead>
                    <TableHead className="w-[80px]">{t('table.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {requests.map((request) => (
                    <TableRow
                      key={request.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleRowClick(request.id)}
                    >
                      <TableCell className="font-medium">
                        {request.reference}
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{request.citizenName}</div>
                          {request.citizenEmail && (
                            <div className="text-xs text-muted-foreground">
                              {request.citizenEmail}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {resolveTypeLabel(ENTITY_CODE, request, t)}
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
                      <TableCell>
                        <div className={`flex items-center gap-1 ${SLA_COLORS[request.slaStatus]}`}>
                          {request.slaStatus === 'violated' && (
                            <AlertTriangle className="h-4 w-4" />
                          )}
                          {request.slaStatus === 'at_risk' && (
                            <AlertCircle className="h-4 w-4" />
                          )}
                          <span className="text-xs capitalize">
                            {request.slaStatus === 'on_track'
                              ? t('table.slaOk')
                              : request.slaStatus === 'at_risk'
                                ? t('table.slaAtRisk')
                                : t('table.slaViolated')}
                          </span>
                        </div>
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
                    {t('table.showing', {
                      from: ((currentPage - 1) * pageSize) + 1,
                      to: Math.min(currentPage * pageSize, total),
                      total,
                    })}
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

      {/* Quick Navigation */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {STANDARD_ACTIONS.map((actionItem) => (
          <Link
            key={actionItem}
            href={`/${locale}/dashboard/agent/${entityCodeSlug}/${workflowGroup}/${actionItem}`}
          >
            <Card className={`cursor-pointer hover:bg-muted/50 transition-colors ${actionItem === currentAction ? 'border-primary ring-1 ring-primary' : ''}`}>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${ACTION_COLORS[actionItem]}`}>
                    {ACTION_ICONS[actionItem]}
                  </div>
                  <span className="font-medium">{t(`nav.${actionItem}`)}</span>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
