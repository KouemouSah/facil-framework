'use client'

/**
 * Smart Assignment Center — Supervisor
 * 3-tab interface: Unassigned | Escalations | Reassign
 * Each tab shows items with 1-click assign via dialog
 * Entity-scoped: supervisors see only their entity's items
 *
 * @route /[locale]/dashboard/supervisor/assignments/manual
 */

import { useState, useCallback } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Progress } from '@/components/ui/progress'
import {
  ArrowLeft,
  Loader2,
  Search,
  UserPlus,
  AlertTriangle,
  ArrowRightLeft,
  Inbox,
  Star,
  CheckCircle2,
  RefreshCw,
  Clock,
  User,
} from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/core/api/client'
import { useAgentProfile } from '@/modules/agent-dashboard/hooks/useAgentDashboard'
import { formatDistanceToNow } from 'date-fns'
import { es, fr, enUS } from 'date-fns/locale'

// ─── Types ───────────────────────────────────────────────────────────────────

interface AssignableItem {
  id: string
  reference: string
  workflow_code: string
  entity_code: string
  status: string
  created_at: string | null
  citizen_name: string
  entity_name: string
  assignment_state: string
  assigned_agent_name: string | null
  current_assignment_id: string | null
  current_agent_profile_id: string | null
}

interface AvailableAgent {
  agent_profile_id: string
  full_name: string
  email: string
  is_supervisor: boolean
  current_assignments: number
  max_concurrent_assignments: number
  workload_status: string
  availability: string
  success_rate: number | null
  avg_processing_hours: number | null
  capacity_percent: number
  is_recommended: boolean
}

interface AssignableItemsResponse {
  items: AssignableItem[]
  total: number
  page: number
  page_size: number
}

type PriorityPreset = 'normal' | 'high' | 'urgent'
type TabValue = 'unassigned' | 'escalated' | 'active'

const PRIORITY_MAP: Record<PriorityPreset, { level: number; color: string }> = {
  normal: { level: 5, color: 'bg-blue-100 text-blue-700' },
  high: { level: 8, color: 'bg-orange-100 text-orange-700' },
  urgent: { level: 10, color: 'bg-red-100 text-red-700' },
}

const dateLocales: Record<string, typeof es> = { es, fr, en: enUS }

// ─── API Functions ───────────────────────────────────────────────────────────

async function fetchAssignableItems(
  tab: TabValue,
  locationId: string,
  search: string,
  page: number
): Promise<AssignableItemsResponse> {
  const params: Record<string, string | number> = { tab, page, page_size: 20 }
  if (locationId) params.entity_location_id = locationId
  if (search) params.search = search
  const res = await apiClient.get<AssignableItemsResponse>('/assignments/assignable-items', { params })
  return res.data
}

async function fetchAgentsForEntity(entityCode: string): Promise<AvailableAgent[]> {
  const res = await apiClient.get<{ agents: AvailableAgent[] }>(
    `/assignments/available-agents-for-item/${entityCode}`
  )
  return res.data.agents
}

async function createManualAssignment(data: {
  item_id: string
  item_type: string
  agent_profile_id: string
  priority_level: number
  notes?: string
}) {
  const res = await apiClient.post('/assignments/manual', data)
  return res.data
}

async function reassignAssignment(
  assignmentId: string,
  data: { new_agent_profile_id: string; reason: string; notes?: string }
) {
  const res = await apiClient.put(`/assignments/${assignmentId}/reassign`, data)
  return res.data
}

async function assignEscalation(requestId: string, agentProfileId: string) {
  const res = await apiClient.post(`/supervisor/escalations/${requestId}/assign?agent_id=${agentProfileId}`)
  return res.data
}

// ─── Hooks ───────────────────────────────────────────────────────────────────

interface EntityLocation {
  id: string
  entity_code: string
  location_name: string
  city: string
  is_main_office: boolean
}

function useSupervisorLocations(entityCode: string | undefined) {
  return useQuery({
    queryKey: ['entity-locations', entityCode],
    queryFn: async () => {
      if (!entityCode) return []
      try {
        const res = await apiClient.get<EntityLocation[]>(
          `/entity-locations/by-entity/${entityCode}`
        )
        return res.data
      } catch {
        return []
      }
    },
    enabled: !!entityCode,
    staleTime: 5 * 60 * 1000,
  })
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function SmartAssignmentPage() {
  const locale = useLocale()
  const t = useTranslations('supervisor.manual')
  const tCommon = useTranslations('common')
  const dateLocale = dateLocales[locale] || enUS
  const queryClient = useQueryClient()

  // Tab & filter state
  const [activeTab, setActiveTab] = useState<TabValue>('unassigned')
  const [locationFilter, setLocationFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<AssignableItem | null>(null)
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [priority, setPriority] = useState<PriorityPreset>('normal')
  const [notes, setNotes] = useState('')

  // Supervisor profile — to know entity_code and is_main_office
  const { data: agentProfile } = useAgentProfile()
  const supervisorEntityCode = agentProfile?.entity_code
  const isMainOffice = agentProfile?.is_main_office ?? false

  // Sites (entity_locations) for filter dropdown — only for main-office supervisors
  const { data: locations = [] } = useSupervisorLocations(
    isMainOffice ? supervisorEntityCode : undefined
  )

  // Fetch items for current tab
  const {
    data: itemsData,
    isLoading: loadingItems,
    error: itemsError,
    refetch: refetchItems,
  } = useQuery({
    queryKey: ['assignable-items', activeTab, locationFilter, searchQuery, page],
    queryFn: () => fetchAssignableItems(activeTab, locationFilter, searchQuery, page),
  })

  // Fetch agents when dialog opens (by entity_code of selected item)
  const {
    data: agents = [],
    isLoading: loadingAgents,
    error: agentsError,
  } = useQuery({
    queryKey: ['agents-for-entity', selectedItem?.entity_code],
    queryFn: () => fetchAgentsForEntity(selectedItem!.entity_code),
    enabled: dialogOpen && !!selectedItem?.entity_code,
  })

  // Mutations
  const assignMutation = useMutation({
    mutationFn: async () => {
      if (!selectedItem || !selectedAgentId) throw new Error(t('incompleteData'))

      if (activeTab === 'escalated') {
        return assignEscalation(selectedItem.id, selectedAgentId)
      } else if (activeTab === 'active' && selectedItem.current_assignment_id) {
        return reassignAssignment(selectedItem.current_assignment_id, {
          new_agent_profile_id: selectedAgentId,
          reason: 'supervisor_decision',
          notes: notes || undefined,
        })
      } else {
        return createManualAssignment({
          item_id: selectedItem.id,
          item_type: 'service_request',
          agent_profile_id: selectedAgentId,
          priority_level: PRIORITY_MAP[priority].level,
          notes: notes || undefined,
        })
      }
    },
    onSuccess: () => {
      const actionLabel =
        activeTab === 'active' ? t('reassigned') : activeTab === 'escalated' ? t('escalationAssigned') : t('assigned')
      toast.success(`${actionLabel}: ${selectedItem?.reference}`)
      closeDialog()
      queryClient.invalidateQueries({ queryKey: ['assignable-items'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || t('assignError'))
    },
  })

  // Handlers
  const openDialog = useCallback((item: AssignableItem) => {
    setSelectedItem(item)
    setSelectedAgentId('')
    setPriority('normal')
    setNotes('')
    setDialogOpen(true)
  }, [])

  const closeDialog = useCallback(() => {
    setDialogOpen(false)
    setSelectedItem(null)
    setSelectedAgentId('')
  }, [])

  const handleTabChange = useCallback((tab: string) => {
    setActiveTab(tab as TabValue)
    setPage(1)
  }, [])

  const handleSearch = useCallback((value: string) => {
    setSearchQuery(value)
    setPage(1)
  }, [])

  const handleLocationFilter = useCallback((value: string) => {
    setLocationFilter(value === '_all' ? '' : value)
    setPage(1)
  }, [])

  // Helpers
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '\u2014'
    try {
      return formatDistanceToNow(new Date(dateStr), { addSuffix: true, locale: dateLocale })
    } catch {
      return dateStr
    }
  }

  const formatWorkflow = (code: string) =>
    code
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())

  const items = itemsData?.items || []
  const total = itemsData?.total || 0
  const totalPages = Math.ceil(total / 20)

  const tabCounts = {
    unassigned: activeTab === 'unassigned' ? total : null,
    escalated: activeTab === 'escalated' ? total : null,
    active: activeTab === 'active' ? total : null,
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/supervisor`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{t('title')}</h1>
          <p className="text-sm text-muted-foreground">{t('subtitle')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetchItems()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t('refresh')}
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="unassigned" className="gap-2">
            <Inbox className="h-4 w-4" />
            {t('tabUnassigned')}
            {tabCounts.unassigned !== null && (
              <Badge variant="secondary" className="ml-1 text-xs">
                {tabCounts.unassigned}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="escalated" className="gap-2">
            <AlertTriangle className="h-4 w-4" />
            {t('tabEscalations')}
            {tabCounts.escalated !== null && (
              <Badge variant="destructive" className="ml-1 text-xs">
                {tabCounts.escalated}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="active" className="gap-2">
            <ArrowRightLeft className="h-4 w-4" />
            {t('tabReassign')}
            {tabCounts.active !== null && (
              <Badge variant="secondary" className="ml-1 text-xs">
                {tabCounts.active}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Filters */}
        <div className="flex gap-3 mt-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t('searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          {isMainOffice && locations.length > 1 && (
            <Select value={locationFilter || '_all'} onValueChange={handleLocationFilter}>
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder={t('allSites') || 'Todos los sitios'} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_all">{t('allSites') || 'Todos los sitios'}</SelectItem>
                {locations.map((loc) => (
                  <SelectItem key={loc.id} value={loc.id}>
                    {loc.location_name} — {loc.city}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Content for all tabs (same table structure) */}
        {(['unassigned', 'escalated', 'active'] as const).map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  {tab === 'unassigned' && t('cardTitleUnassigned')}
                  {tab === 'escalated' && t('cardTitleEscalated')}
                  {tab === 'active' && t('cardTitleActive')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loadingItems ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : itemsError ? (
                  <div className="text-center py-12 text-destructive">
                    <AlertTriangle className="h-6 w-6 mx-auto mb-2" />
                    <p>
                      {itemsError instanceof Error
                        ? itemsError.message
                        : t('loadError')}
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3"
                      onClick={() => refetchItems()}
                    >
                      {t('retry')}
                    </Button>
                  </div>
                ) : items.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-500" />
                    <p className="font-medium">
                      {tab === 'unassigned' && t('emptyUnassigned')}
                      {tab === 'escalated' && t('emptyEscalated')}
                      {tab === 'active' && t('emptyActive')}
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="border rounded-md">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>{t('colReference')}</TableHead>
                            <TableHead>{t('colWorkflow')}</TableHead>
                            <TableHead>{t('colEntity')}</TableHead>
                            <TableHead>{t('colApplicant')}</TableHead>
                            {tab === 'active' && <TableHead>{t('colCurrentAgent')}</TableHead>}
                            {tab === 'escalated' && <TableHead>{tCommon('status')}</TableHead>}
                            <TableHead>{t('colDate')}</TableHead>
                            <TableHead className="text-right">{t('colAction')}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {items.map((item) => (
                            <TableRow key={item.id}>
                              <TableCell className="font-mono text-sm font-medium">
                                {item.reference}
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline" className="text-xs">
                                  {formatWorkflow(item.workflow_code)}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-sm">{item.entity_name}</TableCell>
                              <TableCell className="text-sm">{item.citizen_name}</TableCell>
                              {tab === 'active' && (
                                <TableCell>
                                  <div className="flex items-center gap-1.5">
                                    <User className="h-3.5 w-3.5 text-muted-foreground" />
                                    <span className="text-sm">
                                      {item.assigned_agent_name || '\u2014'}
                                    </span>
                                  </div>
                                </TableCell>
                              )}
                              {tab === 'escalated' && (
                                <TableCell>
                                  <Badge
                                    variant={
                                      item.assignment_state === 'pending'
                                        ? 'destructive'
                                        : 'secondary'
                                    }
                                    className="text-xs"
                                  >
                                    {item.assignment_state === 'pending'
                                      ? t('statusPending')
                                      : t('statusInReview')}
                                  </Badge>
                                </TableCell>
                              )}
                              <TableCell className="text-sm text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatDate(item.created_at)}
                                </div>
                              </TableCell>
                              <TableCell className="text-right">
                                <Button size="sm" onClick={() => openDialog(item)}>
                                  {tab === 'active' ? (
                                    <>
                                      <ArrowRightLeft className="mr-1.5 h-3.5 w-3.5" />
                                      {t('reassign')}
                                    </>
                                  ) : (
                                    <>
                                      <UserPlus className="mr-1.5 h-3.5 w-3.5" />
                                      {t('assign')}
                                    </>
                                  )}
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div className="flex items-center justify-between mt-4">
                        <p className="text-sm text-muted-foreground">
                          {t('paginationResults', { total, page, totalPages })}
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={page <= 1}
                            onClick={() => setPage((p) => p - 1)}
                          >
                            {t('previous')}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= totalPages}
                            onClick={() => setPage((p) => p + 1)}
                          >
                            {t('next')}
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>

      {/* ─── Assignment Dialog ─────────────────────────────────────────── */}
      <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {activeTab === 'active' ? t('dialogTitleReassign') : t('dialogTitleAssign')}
            </DialogTitle>
            <DialogDescription>
              <span className="font-mono font-semibold">{selectedItem?.reference}</span>
              {' \u2014 '}
              {selectedItem ? formatWorkflow(selectedItem.workflow_code) : ''}
              {' \u2014 '}
              {selectedItem?.entity_name}
            </DialogDescription>
          </DialogHeader>

          {/* Agent selection */}
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">{t('selectAgent')}</label>
              {loadingAgents ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span className="ml-2 text-sm text-muted-foreground">{t('loadingAgents')}</span>
                </div>
              ) : agentsError ? (
                <div className="text-center py-4 text-sm text-destructive">
                  {t('agentsError')}
                </div>
              ) : agents.length === 0 ? (
                <div className="text-center py-6 text-sm text-muted-foreground">
                  {t('noAgentsAvailable')}{' '}
                  <span className="font-medium">{selectedItem?.entity_name}</span>
                </div>
              ) : (
                <div className="space-y-2 max-h-[280px] overflow-y-auto">
                  {agents.map((agent) => (
                    <button
                      key={agent.agent_profile_id}
                      type="button"
                      onClick={() => setSelectedAgentId(agent.agent_profile_id)}
                      className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-colors text-left ${
                        selectedAgentId === agent.agent_profile_id
                          ? 'border-primary bg-primary/5 ring-1 ring-primary'
                          : 'border-border hover:bg-muted/50'
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm truncate">
                            {agent.full_name}
                          </span>
                          {agent.is_recommended && (
                            <Badge className="bg-green-100 text-green-700 text-[10px] px-1.5">
                              <Star className="h-3 w-3 mr-0.5" />
                              {t('recommended')}
                            </Badge>
                          )}
                          {agent.is_supervisor && (
                            <Badge variant="outline" className="text-[10px] px-1.5">
                              {t('supervisorBadge')}
                            </Badge>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {agent.current_assignments}/{agent.max_concurrent_assignments} {t('assignments')}
                          {agent.success_rate !== null && (
                            <span className="ml-2">
                              · {agent.success_rate.toFixed(0)}% {t('successRate')}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="w-16 shrink-0">
                        <Progress
                          value={agent.capacity_percent}
                          className="h-2"
                        />
                        <span className="text-[10px] text-muted-foreground">
                          {agent.capacity_percent}%
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Priority — only for new assignments (not escalations) */}
            {activeTab !== 'escalated' && (
              <div>
                <label className="text-sm font-medium mb-2 block">{t('priority')}</label>
                <div className="flex gap-2">
                  {(['normal', 'high', 'urgent'] as PriorityPreset[]).map((p) => (
                    <Button
                      key={p}
                      type="button"
                      variant={priority === p ? 'default' : 'outline'}
                      size="sm"
                      className={priority === p ? PRIORITY_MAP[p].color : ''}
                      onClick={() => setPriority(p)}
                    >
                      {t(`priority_${p}`)}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Notes */}
            <div>
              <label className="text-sm font-medium mb-2 block">{t('notesLabel')}</label>
              <Textarea
                placeholder={t('notesPlaceholder')}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                className="resize-none"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={() => assignMutation.mutate()}
              disabled={!selectedAgentId || assignMutation.isPending}
            >
              {assignMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : activeTab === 'active' ? (
                <ArrowRightLeft className="mr-2 h-4 w-4" />
              ) : (
                <UserPlus className="mr-2 h-4 w-4" />
              )}
              {activeTab === 'active' ? t('confirmReassign') : t('confirmAssign')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
