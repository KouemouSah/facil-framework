'use client'

/**
 * AgentDashboard Component
 * Generic agent dashboard for processing service requests
 */

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import {
  Search,
  Filter,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  MessageSquare,
  Calendar,
  User,
  FileText,
  MoreHorizontal,
  SortAsc,
  SortDesc,
  AlertTriangle,
  ShieldCheck,
  Info,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

import { useServiceRequests } from '../hooks/useServiceRequests'
import {
  ServiceRequestStatus,
  getStatusColor,
  getStatusLabel,
  getVerificationStatusColor,
  getVerificationStatusLabel,
} from '../types'
import type {
  ServiceRequest,
  WorkflowCategory,
  ServiceRequestFilters,
} from '../types'

// ============================================================================
// TYPES
// ============================================================================

interface AgentDashboardProps {
  locale?: 'es' | 'fr' | 'en'
  category?: WorkflowCategory
  agentId?: string
  showAssignedOnly?: boolean
  onViewRequest?: (request: ServiceRequest) => void
  onApprove?: (request: ServiceRequest) => void
  onReject?: (request: ServiceRequest) => void
  onRequestInfo?: (request: ServiceRequest) => void
  onScheduleAppointment?: (request: ServiceRequest) => void
  onManualVerification?: (request: ServiceRequest) => void
}

interface StatCardProps {
  title: string
  value: number
  icon: React.ComponentType<{ className?: string }>
  color: string
}

// ============================================================================
// STAT CARD COMPONENT
// ============================================================================

function StatCard({ title, value, icon: Icon, color }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
          </div>
          <div className={`p-3 rounded-full ${color}`}>
            <Icon className="h-5 w-5 text-white" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// REQUEST ROW COMPONENT
// ============================================================================

interface RequestRowProps {
  request: ServiceRequest
  locale: 'es' | 'fr' | 'en'
  onView: () => void
  onApprove?: () => void
  onReject?: () => void
  onRequestInfo?: () => void
  onScheduleAppointment?: () => void
  onManualVerification?: () => void
}

function RequestRow({
  request,
  locale,
  onView,
  onApprove,
  onReject,
  onRequestInfo,
  onScheduleAppointment,
  onManualVerification,
}: RequestRowProps) {
  const t = useTranslations('service_requests')

  const canApprove = [ServiceRequestStatus.UNDER_REVIEW, ServiceRequestStatus.SUBMITTED].includes(request.status as ServiceRequestStatus)
  const canReject = [ServiceRequestStatus.UNDER_REVIEW, ServiceRequestStatus.SUBMITTED].includes(request.status as ServiceRequestStatus)
  const canRequestInfo = [ServiceRequestStatus.UNDER_REVIEW, ServiceRequestStatus.SUBMITTED].includes(request.status as ServiceRequestStatus)
  const canSchedule = request.status === ServiceRequestStatus.DOSSIER_VALIDE
  const canManualVerify = request.verificationStatus === 'not_found' || request.verificationStatus === 'partial_verification'

  return (
    <TableRow className="cursor-pointer hover:bg-muted/50">
      <TableCell onClick={onView}>
        <div className="font-medium">{request.requestNumber}</div>
        <div className="text-xs text-muted-foreground">
          {request.workflowCode.replace(/_/g, ' ')}
        </div>
      </TableCell>

      <TableCell onClick={onView}>
        <div className="flex items-center gap-2">
          <User className="h-4 w-4 text-muted-foreground" />
          <div>
            <div className="text-sm">{request.userName || 'N/A'}</div>
            <div className="text-xs text-muted-foreground">{request.userEmail}</div>
          </div>
        </div>
      </TableCell>

      <TableCell onClick={onView}>
        <Badge className={getStatusColor(request.status)}>
          {getStatusLabel(request.status as ServiceRequestStatus, locale)}
        </Badge>
      </TableCell>

      {/* Verification Status Column */}
      <TableCell onClick={onView}>
        <div className="flex items-center gap-2">
          <Badge className={getVerificationStatusColor(request.verificationStatus || 'pending')}>
            {request.verificationStatus === 'not_found' && (
              <AlertTriangle className="h-3 w-3 mr-1" />
            )}
            {request.verificationStatus === 'verified' && (
              <ShieldCheck className="h-3 w-3 mr-1" />
            )}
            {request.verificationStatus === 'verified_manually' && (
              <CheckCircle className="h-3 w-3 mr-1" />
            )}
            {getVerificationStatusLabel(request.verificationStatus || 'pending', locale)}
          </Badge>
          {(request.verificationStatus === 'not_found' || request.verificationStatus === 'partial_verification') && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-orange-500" />
                </TooltipTrigger>
                <TooltipContent>
                  <p className="max-w-xs">
                    {locale === 'es'
                      ? 'Documento no verificado en base de datos externa. Requiere verificacion manual.'
                      : locale === 'fr'
                      ? 'Document non verifie dans la base de donnees externe. Verification manuelle requise.'
                      : 'Document not verified in external database. Manual verification required.'}
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </TableCell>

      <TableCell onClick={onView}>
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span>{request.documentCount || 0}</span>
        </div>
      </TableCell>

      <TableCell onClick={onView}>
        <div className="text-sm">
          {new Date(request.createdAt).toLocaleDateString(locale)}
        </div>
        <div className="text-xs text-muted-foreground">
          {new Date(request.createdAt).toLocaleTimeString(locale)}
        </div>
      </TableCell>

      <TableCell>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onView}>
              <Eye className="h-4 w-4 mr-2" />
              {t('view_details')}
            </DropdownMenuItem>

            {canApprove && onApprove && (
              <DropdownMenuItem onClick={onApprove} className="text-green-600">
                <CheckCircle className="h-4 w-4 mr-2" />
                {t('approve')}
              </DropdownMenuItem>
            )}

            {canReject && onReject && (
              <DropdownMenuItem onClick={onReject} className="text-red-600">
                <XCircle className="h-4 w-4 mr-2" />
                {t('reject')}
              </DropdownMenuItem>
            )}

            <DropdownMenuSeparator />

            {canRequestInfo && onRequestInfo && (
              <DropdownMenuItem onClick={onRequestInfo}>
                <MessageSquare className="h-4 w-4 mr-2" />
                {t('request_info')}
              </DropdownMenuItem>
            )}

            {canSchedule && onScheduleAppointment && (
              <DropdownMenuItem onClick={onScheduleAppointment}>
                <Calendar className="h-4 w-4 mr-2" />
                {t('schedule_appointment')}
              </DropdownMenuItem>
            )}

            {canManualVerify && onManualVerification && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={onManualVerification} className="text-teal-600">
                  <ShieldCheck className="h-4 w-4 mr-2" />
                  {locale === 'es' ? 'Verificar manualmente' : locale === 'fr' ? 'Verifier manuellement' : 'Verify Manually'}
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function AgentDashboard({
  locale = 'es',
  category,
  agentId,
  showAssignedOnly = false,
  onViewRequest,
  onApprove,
  onReject,
  onRequestInfo,
  onScheduleAppointment,
  onManualVerification,
}: AgentDashboardProps) {
  const t = useTranslations('service_requests')
  const [searchTerm, setSearchTerm] = useState('')
  const [sortField, setSortField] = useState<'created_at' | 'status'>('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  const {
    requests,
    isLoading,
    error,
    pagination,
    filters,
    setFilters,
    loadAllRequests,
    setPage,
  } = useServiceRequests()

  // Initialize filters
  useEffect(() => {
    const initialFilters: ServiceRequestFilters = {}
    if (category) initialFilters.category = category
    if (showAssignedOnly && agentId) initialFilters.assignedAgentId = agentId
    setFilters(initialFilters)
  }, [category, agentId, showAssignedOnly, setFilters])

  // Load requests
  useEffect(() => {
    loadAllRequests(pagination.page, pagination.pageSize)
  }, [pagination.page, pagination.pageSize, filters, loadAllRequests])

  // Calculate stats
  const stats = useMemo(() => {
    const pending = requests.filter(r =>
      [ServiceRequestStatus.SUBMITTED, ServiceRequestStatus.UNDER_REVIEW].includes(r.status as ServiceRequestStatus)
    ).length
    const approved = requests.filter(r => r.status === ServiceRequestStatus.DOSSIER_VALIDE || r.status === ServiceRequestStatus.COMPLETED).length
    const rejected = requests.filter(r => r.status === ServiceRequestStatus.REJECTED).length
    const total = requests.length

    return { pending, approved, rejected, total }
  }, [requests])

  // Handle search
  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    setFilters({ ...filters, search: searchTerm })
  }, [searchTerm, filters, setFilters])

  // Handle status filter
  const handleStatusFilter = useCallback((status: string) => {
    if (status === 'all') {
      const { status: _, ...rest } = filters
      setFilters(rest)
    } else {
      setFilters({ ...filters, status })
    }
  }, [filters, setFilters])

  // Handle refresh
  const handleRefresh = useCallback(() => {
    loadAllRequests(pagination.page, pagination.pageSize)
  }, [pagination.page, pagination.pageSize, loadAllRequests])

  // Handle sort toggle
  const handleSort = useCallback((field: 'created_at' | 'status') => {
    if (sortField === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }, [sortField])

  // Sorted requests
  const sortedRequests = useMemo(() => {
    return [...requests].sort((a, b) => {
      let comparison = 0
      if (sortField === 'created_at') {
        comparison = new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
      } else if (sortField === 'status') {
        comparison = a.status.localeCompare(b.status)
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })
  }, [requests, sortField, sortOrder])

  const SortIcon = sortOrder === 'asc' ? SortAsc : SortDesc

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title={t('pending_review')}
          value={stats.pending}
          icon={Clock}
          color="bg-yellow-500"
        />
        <StatCard
          title={t('approved')}
          value={stats.approved}
          icon={CheckCircle}
          color="bg-green-500"
        />
        <StatCard
          title={t('rejected')}
          value={stats.rejected}
          icon={XCircle}
          color="bg-red-500"
        />
        <StatCard
          title={t('total')}
          value={stats.total}
          icon={FileText}
          color="bg-blue-500"
        />
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            <CardTitle className="text-lg">{t('service_requests')}</CardTitle>

            <div className="flex flex-wrap gap-2">
              {/* Search */}
              <form onSubmit={handleSearch} className="flex gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('search_placeholder')}
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-9 w-48"
                  />
                </div>
              </form>

              {/* Status Filter */}
              <Select
                value={filters.status || 'all'}
                onValueChange={handleStatusFilter}
              >
                <SelectTrigger className="w-40">
                  <Filter className="h-4 w-4 mr-2" />
                  <SelectValue placeholder={t('filter_status')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('all_statuses')}</SelectItem>
                  <SelectItem value="submitted">{t('status.submitted')}</SelectItem>
                  <SelectItem value="agent_review">{t('status.agent_review')}</SelectItem>
                  <SelectItem value="approved">{t('status.approved')}</SelectItem>
                  <SelectItem value="rejected">{t('status.rejected')}</SelectItem>
                  <SelectItem value="additional_info_required">{t('status.additional_info')}</SelectItem>
                </SelectContent>
              </Select>

              {/* Refresh */}
              <Button variant="outline" size="icon" onClick={handleRefresh}>
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {/* Table */}
          {isLoading && requests.length === 0 ? (
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-500">
              {error}
            </div>
          ) : sortedRequests.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {t('no_requests_found')}
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('request_number')}</TableHead>
                    <TableHead>{t('applicant')}</TableHead>
                    <TableHead>
                      <button
                        className="flex items-center gap-1 hover:text-foreground"
                        onClick={() => handleSort('status')}
                      >
                        {t('status')}
                        {sortField === 'status' && <SortIcon className="h-3 w-3" />}
                      </button>
                    </TableHead>
                    <TableHead className="w-[140px]">
                      {locale === 'es' ? 'Verificacion' : locale === 'fr' ? 'Verification' : 'Verification'}
                    </TableHead>
                    <TableHead>{t('documents')}</TableHead>
                    <TableHead>
                      <button
                        className="flex items-center gap-1 hover:text-foreground"
                        onClick={() => handleSort('created_at')}
                      >
                        {t('date')}
                        {sortField === 'created_at' && <SortIcon className="h-3 w-3" />}
                      </button>
                    </TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedRequests.map((request) => (
                    <RequestRow
                      key={request.id}
                      request={request}
                      locale={locale}
                      onView={() => onViewRequest?.(request)}
                      onApprove={() => onApprove?.(request)}
                      onReject={() => onReject?.(request)}
                      onRequestInfo={() => onRequestInfo?.(request)}
                      onScheduleAppointment={() => onScheduleAppointment?.(request)}
                      onManualVerification={() => onManualVerification?.(request)}
                    />
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between mt-4">
                <div className="text-sm text-muted-foreground">
                  {t('showing_of', {
                    start: (pagination.page - 1) * pagination.pageSize + 1,
                    end: Math.min(pagination.page * pagination.pageSize, pagination.total),
                    total: pagination.total,
                  })}
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>

                  <span className="text-sm">
                    {t('page_of', {
                      page: pagination.page,
                      total: pagination.totalPages,
                    })}
                  </span>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(pagination.page + 1)}
                    disabled={pagination.page >= pagination.totalPages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default AgentDashboard
