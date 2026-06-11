'use client'

/**
 * Entities Tab Content
 * CRUD management for entities with workflow_codes
 */

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Building,
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Search,
  AlertTriangle,
  Layers,
  Workflow,
  ChevronsUpDown,
  X,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
} from 'lucide-react'
import Link from 'next/link'
import { useLocale } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import { useWorkflows } from '@/modules/service-requests-admin/hooks'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'
import {
  useEntitiesWithDetails,
  useEntitiesSimple,
  useCreateEntity,
  useUpdateEntity,
  useDeleteEntity,
} from '@/modules/cities'
import { useWorkflowMappings } from '@/modules/admin/hooks/useWorkflowMappings'
import { hierarchyApi } from '@/modules/fiscal-services/services/api'
import type {
  EntityWithDetails,
  EntityCreate,
  EntityUpdate,
  EntityType,
  EntityFilters,
} from '@/modules/cities'
import type { WorkflowMenuMapping } from '@/modules/agent-dashboard/types/menu-config'
import { sqlLikeToRegex } from '@/core/utils/sql-like'

/**
 * Check if a workflow code matches any mapping pattern
 */
function findMatchingMapping(
  workflowCode: string,
  mappings: WorkflowMenuMapping[]
): WorkflowMenuMapping | null {
  for (const mapping of mappings) {
    const regex = sqlLikeToRegex(mapping.workflow_pattern)
    if (regex.test(workflowCode)) {
      return mapping
    }
  }
  return null
}

/**
 * Calculate mapping coverage for a list of workflow codes
 */
function calculateMappingCoverage(
  workflowCodes: string[],
  mappings: WorkflowMenuMapping[]
): { covered: number; total: number; missingCodes: string[] } {
  const missingCodes: string[] = []
  let covered = 0

  for (const code of workflowCodes) {
    const match = findMatchingMapping(code, mappings)
    if (match) {
      covered++
    } else {
      missingCodes.push(code)
    }
  }

  return { covered, total: workflowCodes.length, missingCodes }
}

interface EntityFormData {
  code: string
  name: string
  description: string
  entity_type: EntityType
  parent_type: 'ministry' | 'entity' | null  // Filter for parent selection
  parent_entity_id: string | null
  ministry_id: number | null
  workflow_codes: string[]
  is_active: boolean
}

const defaultFormData: EntityFormData = {
  code: '',
  name: '',
  description: '',
  entity_type: 'entity',
  parent_type: null,
  parent_entity_id: null,
  ministry_id: null,
  workflow_codes: [],
  is_active: true,
}

export default function EntitiesTabContent() {
  const t = useTranslations('admin.entities')
  const tCommon = useTranslations('common')
  const { toast } = useToast()
  const locale = useLocale()
  const { tw } = useWorkflowTranslations()

  // Fetch workflow mappings for coverage calculation
  const { data: mappingsData } = useWorkflowMappings({ page_size: 100 })
  const workflowMappings = mappingsData?.items || []

  // Filter states
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | EntityType>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')

  // Modal states
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedEntity, setSelectedEntity] = useState<EntityWithDetails | null>(null)
  const [formData, setFormData] = useState<EntityFormData>(defaultFormData)
  const [workflowSearchQuery, setWorkflowSearchQuery] = useState('')
  const [isWorkflowPopoverOpen, setIsWorkflowPopoverOpen] = useState(false)

  // API filters
  const apiFilters: EntityFilters = {
    ...(typeFilter !== 'all' && { entity_type: typeFilter }),
    ...(statusFilter !== 'all' && { is_active: statusFilter === 'active' }),
  }

  // Queries
  const { data: entitiesData, isLoading, error, refetch } = useEntitiesWithDetails(apiFilters)
  const { data: parentEntities } = useEntitiesSimple(true)
  const { data: availableWorkflows, isLoading: isLoadingWorkflows } = useWorkflows({ is_active: true })

  // Fetch ministries for entity linking
  const { data: ministriesData, isLoading: isLoadingMinistries } = useQuery({
    queryKey: ['ministries', 'list'],
    queryFn: () => hierarchyApi.ministries.list('es'),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
  const ministries = ministriesData?.map(m => ({ id: m.id, name: m.nameEs || m.name_es || '' })) || []

  // Mutations
  const createMutation = useCreateEntity()
  const updateMutation = useUpdateEntity()
  const deleteMutation = useDeleteEntity()

  const entities = entitiesData?.items || []

  // Filter available workflows by search query in the popover
  const filteredWorkflows = useMemo(() => {
    if (!availableWorkflows) return []
    if (!workflowSearchQuery) return availableWorkflows
    const search = workflowSearchQuery.toLowerCase()
    return availableWorkflows.filter(
      (w) =>
        w.code.toLowerCase().includes(search) ||
        w.name_es.toLowerCase().includes(search) ||
        tw(workflowNameKey(w.code), w.name_es).toLowerCase().includes(search)
    )
  }, [availableWorkflows, workflowSearchQuery, tw])

  // Toggle workflow code selection
  const handleToggleWorkflowCode = (code: string) => {
    const currentCodes = formData.workflow_codes || []
    const isSelected = currentCodes.includes(code)
    if (isSelected) {
      setFormData({
        ...formData,
        workflow_codes: currentCodes.filter((c) => c !== code),
      })
    } else {
      setFormData({
        ...formData,
        workflow_codes: [...currentCodes, code],
      })
    }
  }

  // Remove a specific workflow code
  const handleRemoveWorkflowCode = (code: string) => {
    setFormData({
      ...formData,
      workflow_codes: (formData.workflow_codes || []).filter((c) => c !== code),
    })
  }

  // Filter entities by search
  const filteredEntities = entities.filter((e) => {
    if (!searchQuery) return true
    const search = searchQuery.toLowerCase()
    return (
      e.code.toLowerCase().includes(search) ||
      e.name.toLowerCase().includes(search) ||
      e.parent_entity_code?.toLowerCase().includes(search) ||
      e.ministry_name?.toLowerCase().includes(search)
    )
  })

  // Open create dialog
  const handleCreate = () => {
    setSelectedEntity(null)
    setFormData(defaultFormData)
    setWorkflowSearchQuery('')
    setIsDialogOpen(true)
  }

  // Open edit dialog
  const handleEdit = (entity: EntityWithDetails) => {
    setSelectedEntity(entity)
    // Determine parent_type based on existing data
    let parentType: 'ministry' | 'entity' | null = null
    if (entity.ministry_id) {
      parentType = 'ministry'
    } else if (entity.parent_entity_id) {
      parentType = 'entity'
    }
    setFormData({
      code: entity.code,
      name: entity.name,
      description: entity.description || '',
      entity_type: entity.entity_type,
      parent_type: parentType,
      parent_entity_id: entity.parent_entity_id,
      ministry_id: entity.ministry_id,
      workflow_codes: entity.workflow_codes || [],
      is_active: entity.is_active,
    })
    setWorkflowSearchQuery('')
    setIsDialogOpen(true)
  }

  // Open delete confirmation
  const handleDeleteClick = (entity: EntityWithDetails) => {
    setSelectedEntity(entity)
    setIsDeleteDialogOpen(true)
  }

  // Submit form
  const handleSubmit = async () => {
    if (!formData.code || !formData.name) {
      toast({
        variant: 'destructive',
        title: tCommon('error'),
        description: t('codeAndNameRequired'),
      })
      return
    }

    // Prepare data for API - exclude parent_type which is frontend-only
    const { parent_type: _parent_type, ...apiData } = formData
    const data: EntityCreate | EntityUpdate = {
      code: apiData.code,
      name: apiData.name,
      description: apiData.description || null,
      entity_type: apiData.entity_type,
      parent_entity_id: apiData.parent_entity_id || null,
      ministry_id: apiData.ministry_id || null,
      workflow_codes: apiData.workflow_codes || [],
      is_active: apiData.is_active,
    }

    try {
      if (selectedEntity) {
        await updateMutation.mutateAsync({
          entityId: selectedEntity.id,
          data: data as EntityUpdate,
        })
        toast({ title: tCommon('success'), description: t('entityUpdated') })
      } else {
        await createMutation.mutateAsync(data as EntityCreate)
        toast({ title: tCommon('success'), description: t('entityCreated') })
      }
      setIsDialogOpen(false)
      refetch()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: tCommon('error'),
        description: err instanceof Error ? err.message : tCommon('errorSaving'),
      })
    }
  }

  // Delete entity
  const handleDelete = async () => {
    if (!selectedEntity) return

    try {
      await deleteMutation.mutateAsync(selectedEntity.id)
      toast({ title: tCommon('success'), description: t('entityDeleted') })
      setIsDeleteDialogOpen(false)
      refetch()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: tCommon('error'),
        description: err instanceof Error ? err.message : tCommon('errorDeleting'),
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* Entities Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{t('listTitle') || 'Entities List'}</CardTitle>
                <CardDescription>
                  {t('entitiesFound', { count: filteredEntities.length })}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => refetch()}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {tCommon('refresh') || 'Refresh'}
                </Button>
                <Button size="sm" onClick={handleCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('createEntity') || 'Create Entity'}
                </Button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex gap-4 flex-wrap">
              <div className="relative max-w-sm">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder={t('searchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select
                value={typeFilter}
                onValueChange={(v) => setTypeFilter(v as 'all' | EntityType)}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder={t('fieldType')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allTypes')}</SelectItem>
                  <SelectItem value="entity">{t('typeEntity')}</SelectItem>
                  <SelectItem value="department">{t('typeDepartment')}</SelectItem>
                  <SelectItem value="treasury">{t('typeTreasury')}</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={statusFilter}
                onValueChange={(v) => setStatusFilter(v as 'all' | 'active' | 'inactive')}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder={t('table.status')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allStatus')}</SelectItem>
                  <SelectItem value="active">{t('status.active')}</SelectItem>
                  <SelectItem value="inactive">{t('status.inactive')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">{tCommon('loading')}</span>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center py-8 text-red-500">
              <AlertTriangle className="h-5 w-5 mr-2" />
              {error.message}
            </div>
          )}

          {!isLoading && !error && filteredEntities.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Building className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('noEntitiesFound')}</p>
              <Button className="mt-4" onClick={handleCreate}>
                <Plus className="h-4 w-4 mr-2" />
                {t('createFirstEntity')}
              </Button>
            </div>
          )}

          {!isLoading && !error && filteredEntities.length > 0 && (
            <div className="border rounded-md overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('table.code')}</TableHead>
                  <TableHead>{t('table.name')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('table.type')}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t('table.parent')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('table.workflows')}</TableHead>
                  <TableHead>{t('table.status')}</TableHead>
                  <TableHead className="text-right">{t('table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEntities.map((entity) => (
                  <TableRow key={entity.id}>
                    <TableCell className="font-mono text-sm">{entity.code}</TableCell>
                    <TableCell className="font-medium max-w-[200px] truncate">{entity.name}</TableCell>
                    <TableCell className="hidden md:table-cell">
                      <Badge variant={entity.entity_type === 'entity' ? 'default' : entity.entity_type === 'treasury' ? 'outline' : 'secondary'}>
                        {entity.entity_type === 'entity' ? (
                          <Building className="h-3 w-3 mr-1" />
                        ) : entity.entity_type === 'treasury' ? (
                          <Building className="h-3 w-3 mr-1" />
                        ) : (
                          <Layers className="h-3 w-3 mr-1" />
                        )}
                        {entity.entity_type === 'entity' ? t('typeEntity') : entity.entity_type === 'treasury' ? t('typeTreasury') : t('typeDepartment')}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {entity.parent_entity_code ? (
                        <span className="text-sm text-muted-foreground">
                          {entity.parent_entity_code}
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {(() => {
                        const codes = entity.resolved_workflow_codes || []
                        const coverage = calculateMappingCoverage(codes, workflowMappings)
                        const coveragePercent = codes.length > 0 ? Math.round((coverage.covered / coverage.total) * 100) : 0
                        const badgeClass = coveragePercent === 100
                          ? 'bg-green-100 text-green-700 border-green-300'
                          : coveragePercent >= 50
                          ? 'bg-yellow-100 text-yellow-700 border-yellow-300'
                          : 'bg-red-100 text-red-700 border-red-300'

                        return (
                          <div className="flex flex-col gap-1">
                            <div className="flex items-center gap-1">
                              <Workflow className="h-3 w-3 text-muted-foreground" />
                              <span className="text-sm">{entity.workflow_count}</span>
                            </div>
                            {codes.length > 0 && (
                              <Badge variant="outline" className={`text-[10px] h-5 ${badgeClass}`}>
                                {coverage.covered}/{coverage.total} {t('mappings')}
                              </Badge>
                            )}
                          </div>
                        )
                      })()}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          entity.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-700'
                        }
                      >
                        {entity.is_active ? t('status.active') : t('status.inactive')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(entity)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDeleteClick(entity)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {selectedEntity ? t('editEntity') : t('createEntity')}
            </DialogTitle>
            <DialogDescription>
              {selectedEntity ? t('editDescription') : t('createDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">{t('fieldCode')} *</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  placeholder="Ej: CNEDOGE"
                  maxLength={50}
                  disabled={!!selectedEntity}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="entity_type">{t('fieldType')} *</Label>
                <Select
                  value={formData.entity_type}
                  onValueChange={(v) => setFormData({ ...formData, entity_type: v as EntityType })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="entity">{t('entityTypes.entity')}</SelectItem>
                    <SelectItem value="department">{t('entityTypes.department')}</SelectItem>
                    <SelectItem value="treasury">{t('entityTypes.treasury')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">{t('fieldName')} *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Ej: Centro Nacional de Documentos de Guinea Ecuatorial"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">{t('fieldDescription')}</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('fieldDescription') + '...'}
                rows={2}
              />
            </div>

            {/* Parent Type Selector - shown for both entity types */}
            <div className="space-y-2">
              <Label htmlFor="parent_type">{t('fieldParentType')}</Label>
              <Select
                value={formData.parent_type || '_none'}
                onValueChange={(v) => {
                  const newParentType = v === '_none' ? null : v as 'ministry' | 'entity'
                  setFormData({
                    ...formData,
                    parent_type: newParentType,
                    // Reset parent selections when type changes
                    parent_entity_id: newParentType === 'entity' ? formData.parent_entity_id : null,
                    ministry_id: newParentType === 'ministry' ? formData.ministry_id : null,
                  })
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('selectParentType')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">{t('independentEntity')}</SelectItem>
                  <SelectItem value="ministry">{t('parentTypeMinistry')}</SelectItem>
                  <SelectItem value="entity">{t('parentTypeEntity')}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t('parentTypeHint')}</p>
            </div>

            {/* Ministry Selector - shown when parent_type is 'ministry' */}
            {formData.parent_type === 'ministry' && (
              <div className="space-y-2">
                <Label htmlFor="ministry_id">{t('fieldMinistry')} *</Label>
                <Select
                  value={formData.ministry_id?.toString() || ''}
                  onValueChange={(v) => setFormData({ ...formData, ministry_id: v ? parseInt(v) : null })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectMinistry')} />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoadingMinistries ? (
                      <SelectItem value="_loading" disabled>{tCommon('loading')}</SelectItem>
                    ) : ministries.length === 0 ? (
                      <SelectItem value="_empty" disabled>{t('noMinistriesFound')}</SelectItem>
                    ) : (
                      ministries.map((m) => (
                        <SelectItem key={m.id} value={m.id.toString()}>
                          {m.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Parent Entity Selector - shown when parent_type is 'entity' */}
            {formData.parent_type === 'entity' && (
              <div className="space-y-2">
                <Label htmlFor="parent_entity_id">{t('fieldParent')} *</Label>
                <Select
                  value={formData.parent_entity_id || ''}
                  onValueChange={(v) => setFormData({ ...formData, parent_entity_id: v || null })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectParent')} />
                  </SelectTrigger>
                  <SelectContent>
                    {parentEntities
                      ?.filter((e) => e.entity_type === 'entity' || e.entity_type === 'treasury')
                      .map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.code} - {e.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label>{t('fieldWorkflowCodes')}</Label>
              <Popover open={isWorkflowPopoverOpen} onOpenChange={setIsWorkflowPopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={isWorkflowPopoverOpen}
                    className="w-full justify-between font-normal h-auto min-h-10"
                  >
                    {formData.workflow_codes.length > 0 ? (
                      <span className="text-sm">
                        {t('workflowsSelected', { count: formData.workflow_codes.length })}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">{t('selectWorkflows')}</span>
                    )}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[400px] p-0" align="start">
                  <div className="p-2 border-b">
                    <div className="relative">
                      <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        placeholder={t('searchWorkflows')}
                        value={workflowSearchQuery}
                        onChange={(e) => setWorkflowSearchQuery(e.target.value)}
                        className="pl-8 h-8"
                      />
                    </div>
                  </div>
                  <ScrollArea className="h-[250px]">
                    {isLoadingWorkflows ? (
                      <div className="flex items-center justify-center py-6">
                        <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-sm text-muted-foreground">{tCommon('loading')}</span>
                      </div>
                    ) : filteredWorkflows.length === 0 ? (
                      <div className="py-6 text-center text-sm text-muted-foreground">
                        {t('noWorkflowsFound')}
                      </div>
                    ) : (
                      <div className="p-2 space-y-1">
                        {filteredWorkflows.map((workflow) => {
                          const isSelected = formData.workflow_codes.includes(workflow.code)
                          return (
                            <div
                              key={workflow.code}
                              className={`flex items-center gap-2 p-2 rounded-md cursor-pointer hover:bg-muted ${
                                isSelected ? 'bg-muted' : ''
                              }`}
                              onClick={() => handleToggleWorkflowCode(workflow.code)}
                            >
                              <Checkbox
                                checked={isSelected}
                                onCheckedChange={() => handleToggleWorkflowCode(workflow.code)}
                                onClick={(e) => e.stopPropagation()}
                              />
                              <div className="flex-1 min-w-0">
                                <div className="font-mono text-sm font-medium truncate">
                                  {workflow.code}
                                </div>
                                <div className="text-xs text-muted-foreground truncate">
                                  {tw(workflowNameKey(workflow.code), workflow.name_es)}
                                </div>
                              </div>
                              {!workflow.is_generic && (
                                <Badge variant="outline" className="text-xs shrink-0">
                                  Predefined
                                </Badge>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </ScrollArea>
                </PopoverContent>
              </Popover>

              {/* Selected workflow codes as badges */}
              {formData.workflow_codes.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {formData.workflow_codes.map((code) => {
                    const workflow = availableWorkflows?.find((w) => w.code === code)
                    return (
                      <Badge
                        key={code}
                        variant="secondary"
                        className="text-xs pr-1 flex items-center gap-1"
                      >
                        <span className="font-mono">{code}</span>
                        {workflow && (
                          <span className="text-muted-foreground max-w-[100px] truncate">
                            - {tw(workflowNameKey(workflow.code), workflow.name_es)}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => handleRemoveWorkflowCode(code)}
                          className="ml-1 rounded-full hover:bg-muted p-0.5"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    )
                  })}
                </div>
              )}

              {/* Mapping coverage status */}
              {formData.workflow_codes.length > 0 && (
                <div className="mt-3 p-3 bg-muted/50 rounded-md border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{t('mappingCoverage')}</span>
                    {(() => {
                      const coverage = calculateMappingCoverage(formData.workflow_codes, workflowMappings)
                      const badgeClass = coverage.covered === coverage.total
                        ? 'bg-green-100 text-green-700'
                        : coverage.covered > 0
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-red-100 text-red-700'
                      return (
                        <Badge variant="outline" className={`text-xs ${badgeClass}`}>
                          {coverage.covered}/{coverage.total}
                        </Badge>
                      )
                    })()}
                  </div>
                  <div className="space-y-1">
                    {formData.workflow_codes.map((code) => {
                      const mapping = findMatchingMapping(code, workflowMappings)
                      return (
                        <div key={code} className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            {mapping ? (
                              <CheckCircle2 className="h-3 w-3 text-green-600" />
                            ) : (
                              <AlertCircle className="h-3 w-3 text-amber-500" />
                            )}
                            <span className="font-mono">{code}</span>
                          </div>
                          {mapping ? (
                            <span className="text-muted-foreground">
                              → {mapping.menu_group_id}
                            </span>
                          ) : (
                            <Link
                              href={`/${locale}/dashboard/admin/workflow-mappings/new?pattern=${encodeURIComponent(code.split('_')[0] + '_%')}`}
                              className="text-primary hover:underline flex items-center gap-1"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {t('createMapping')}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
              />
              <Label htmlFor="is_active">{t('fieldActive')}</Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {(createMutation.isPending || updateMutation.isPending) && (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              )}
              {selectedEntity ? t('saveChanges') : tCommon('create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteEntity')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteDescription', { name: selectedEntity?.name || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && <RefreshCw className="h-4 w-4 mr-2 animate-spin" />}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
