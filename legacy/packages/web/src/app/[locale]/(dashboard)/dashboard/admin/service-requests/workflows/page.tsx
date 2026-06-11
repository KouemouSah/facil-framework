'use client'

/**
 * Workflows Admin Page - Hierarchical View
 *
 * Displays workflows grouped by parent (PASAPORTE, RESIDENCIA, etc.)
 * with expandable/collapsible sections.
 *
 * Features:
 * - Hierarchical grouping by parent_workflow_code
 * - Read-only badge for predefined workflows (is_generic = false)
 * - Editable dynamic workflows (is_generic = true)
 * - Tariff display per workflow
 * - Search and filters
 *
 * @module dashboard/admin/service-requests/workflows
 */

import { useState, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter, useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
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
  GitBranch,
  Plus,
  Search,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  Calculator,
  Eye,
  Pencil,
  Trash2,
  ChevronRight,
  Lock,
  FileText,
  DollarSign,
  FolderOpen,
  Folder,
} from 'lucide-react'
import {
  useWorkflows,
  useTariffs,
  useDeleteWorkflow,
} from '@/modules/service-requests-admin'
import type {
  Workflow,
  WorkflowTariff,
} from '@/modules/service-requests-admin'
import { WORKFLOW_CATEGORIES_MAP } from '@/modules/service-requests-admin'
import { cn } from '@/lib/utils'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'

const formatCurrency = (amount: number, currency = 'XAF') => {
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

interface WorkflowWithTariffs extends Workflow {
  tariffsList: WorkflowTariff[]
}

/**
 * Business domain configuration for workflow grouping
 * Each domain has a code prefix, display name, icon color, and description
 */
interface WorkflowDomain {
  id: string
  prefixes: string[]  // Workflow code prefixes that belong to this domain
  name: string
  description: string
  icon: 'passport' | 'home' | 'car' | 'license' | 'contract' | 'public' | 'globe' | 'other'
  color: string  // Tailwind color class
}

const WORKFLOW_DOMAINS: WorkflowDomain[] = [
  {
    id: 'pasaporte',
    prefixes: ['PASAPORTE_'],
    name: 'Pasaportes',
    description: 'Solicitudes de pasaportes: nuevos, renovaciones, duplicados',
    icon: 'passport',
    color: 'blue',
  },
  {
    id: 'residencia',
    prefixes: ['RESIDENCIA_'],
    name: 'Permisos de Residencia',
    description: 'Permisos de residencia para extranjeros',
    icon: 'home',
    color: 'green',
  },
  {
    id: 'vehiculo',
    prefixes: ['VEHICULO_'],
    name: 'Vehículos',
    description: 'Matriculaciones, transferencias, ITV',
    icon: 'car',
    color: 'orange',
  },
  {
    id: 'conducir',
    prefixes: ['CONDUCIR_'],
    name: 'Licencias de Conducir',
    description: 'Certificados para conducir: nuevos, canjes, renovaciones',
    icon: 'license',
    color: 'purple',
  },
  {
    id: 'contrato',
    prefixes: ['CONTRATO_'],
    name: 'Contratos',
    description: 'Registro de contratos públicos y privados',
    icon: 'contract',
    color: 'amber',
  },
  {
    id: 'funcion_publica',
    prefixes: ['FP_'],
    name: 'Función Pública',
    description: 'Trámites de funcionarios públicos',
    icon: 'public',
    color: 'indigo',
  },
  {
    id: 'visado',
    prefixes: ['PRORROGA_', 'VISADO_', 'PERMANENCIA_', 'SALIDA_'],
    name: 'Visados y Permisos',
    description: 'Trámites de visados: prórrogas, alternativos, permanencias',
    icon: 'globe',
    color: 'cyan',
  },
  {
    id: 'otros',
    prefixes: [],  // Catch-all - workflows that don't match any predefined prefix
    name: 'Otros Trámites (Admin)',
    description: 'Workflows dinámicos creados via la interfaz de administración',
    icon: 'other',
    color: 'slate',
  },
]

/**
 * Get the domain for a workflow based on its code
 */
const getWorkflowDomain = (code: string): WorkflowDomain => {
  for (const domain of WORKFLOW_DOMAINS) {
    if (domain.prefixes.some(prefix => code.startsWith(prefix))) {
      return domain
    }
  }
  return WORKFLOW_DOMAINS[WORKFLOW_DOMAINS.length - 1] // 'otros'
}

/**
 * Get icon color classes for a domain
 */
const getDomainColorClasses = (color: string) => ({
  bg: `bg-${color}-100`,
  text: `text-${color}-700`,
  border: `border-${color}-200`,
  badgeBg: `bg-${color}-50`,
  badgeText: `text-${color}-600`,
})

interface WorkflowGroup {
  domain: WorkflowDomain
  workflows: WorkflowWithTariffs[]
  predefinedCount: number
  dynamicCount: number
}

export default function WorkflowsPage() {
  const t = useTranslations('admin.serviceRequests.workflows')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string

  // State
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(null)
  // Start with all groups expanded by default
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(WORKFLOW_DOMAINS.map(d => d.id))
  )

  // Workflow translations
  const { tw } = useWorkflowTranslations()

  // Mutations
  const deleteWorkflowMutation = useDeleteWorkflow()

  // Queries
  const { data: workflows, isLoading: loadingWorkflows, error: workflowsError, refetch } = useWorkflows()
  const { data: tariffs, isLoading: loadingTariffs } = useTariffs()

  const isLoading = loadingWorkflows || loadingTariffs

  // Build groups by business domain (métier)
  const workflowGroups = useMemo(() => {
    if (!workflows || !tariffs) return []

    // Filter out parent workflows (is_parent=true) - we only show actual workflows
    const actualWorkflows = workflows.filter((wf) => wf.is_parent !== true)

    // Map tariffs by workflow_code for quick lookup
    const tariffsByWorkflow = new Map<string, WorkflowTariff[]>()
    tariffs.forEach((t) => {
      if (!tariffsByWorkflow.has(t.workflow_code)) {
        tariffsByWorkflow.set(t.workflow_code, [])
      }
      tariffsByWorkflow.get(t.workflow_code)?.push(t)
    })

    // Group workflows by domain based on code prefix
    const groupsByDomain = new Map<string, WorkflowWithTariffs[]>()

    actualWorkflows.forEach((wf) => {
      const domain = getWorkflowDomain(wf.code)
      if (!groupsByDomain.has(domain.id)) {
        groupsByDomain.set(domain.id, [])
      }
      groupsByDomain.get(domain.id)?.push({
        ...wf,
        tariffsList: tariffsByWorkflow.get(wf.code) || [],
      })
    })

    // Create WorkflowGroup array from WORKFLOW_DOMAINS order
    const groups: WorkflowGroup[] = []

    WORKFLOW_DOMAINS.forEach((domain) => {
      const domainWorkflows = groupsByDomain.get(domain.id) || []
      if (domainWorkflows.length > 0) {
        // Sort workflows by display_order then by name
        domainWorkflows.sort((a, b) => {
          const orderDiff = (a.display_order || 0) - (b.display_order || 0)
          if (orderDiff !== 0) return orderDiff
          return tw(workflowNameKey(a.code), a.name_es).localeCompare(tw(workflowNameKey(b.code), b.name_es))
        })

        groups.push({
          domain,
          workflows: domainWorkflows,
          predefinedCount: domainWorkflows.filter((wf) => wf.is_generic === false).length,
          dynamicCount: domainWorkflows.filter((wf) => wf.is_generic === true).length,
        })
      }
    })

    return groups
  }, [workflows, tariffs, tw])

  // Filter groups based on search and filters
  const filteredGroups = useMemo(() => {
    return workflowGroups
      .map((group) => {
        let filteredWorkflows = group.workflows

        // Apply category filter
        if (categoryFilter !== 'all') {
          filteredWorkflows = filteredWorkflows.filter((wf) => wf.category === categoryFilter)
        }

        // Apply status filter
        if (statusFilter !== 'all') {
          const isActive = statusFilter === 'active'
          filteredWorkflows = filteredWorkflows.filter((wf) => wf.is_active === isActive)
        }

        // Apply source filter (predefined vs dynamic)
        if (sourceFilter !== 'all') {
          const isGeneric = sourceFilter === 'dynamic'
          filteredWorkflows = filteredWorkflows.filter((wf) => wf.is_generic === isGeneric)
        }

        // Apply search filter
        if (searchQuery) {
          const query = searchQuery.toLowerCase()
          filteredWorkflows = filteredWorkflows.filter(
            (wf) =>
              wf.code.toLowerCase().includes(query) ||
              wf.name_es.toLowerCase().includes(query) ||
              tw(workflowNameKey(wf.code), wf.name_es).toLowerCase().includes(query) ||
              wf.entity_code.toLowerCase().includes(query) ||
              (wf.tags && wf.tags.some((tag) => tag.toLowerCase().includes(query)))
          )
        }

        return {
          ...group,
          workflows: filteredWorkflows,
          predefinedCount: filteredWorkflows.filter((wf) => wf.is_generic === false).length,
          dynamicCount: filteredWorkflows.filter((wf) => wf.is_generic === true).length,
        }
      })
      .filter((group) => group.workflows.length > 0)
  }, [workflowGroups, categoryFilter, statusFilter, sourceFilter, searchQuery, tw])

  // Stats
  const totalWorkflows = workflows?.filter((wf) => wf.is_parent !== true).length || 0
  const predefinedCount = workflows?.filter((wf) => wf.is_parent !== true && wf.is_generic === false).length || 0
  const dynamicCount = workflows?.filter((wf) => wf.is_parent !== true && wf.is_generic === true).length || 0

  // Toggle group expansion
  const toggleGroup = (domainId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(domainId)) {
        next.delete(domainId)
      } else {
        next.add(domainId)
      }
      return next
    })
  }

  // Expand all groups
  const expandAllGroups = () => {
    const allIds = new Set(workflowGroups.map((g) => g.domain.id))
    setExpandedGroups(allIds)
  }

  // Collapse all groups
  const collapseAllGroups = () => {
    setExpandedGroups(new Set())
  }

  // Navigation
  const navigateToWorkflow = (code: string) => {
    router.push(`/${locale}/dashboard/admin/service-requests/workflows/${code}`)
  }

  const navigateToNewWorkflow = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/workflows/new`)
  }

  // Delete handling
  const handleDeleteClick = (e: React.MouseEvent, workflow: Workflow) => {
    e.stopPropagation()
    if (!workflow.is_generic) {
      // Cannot delete predefined workflows
      return
    }
    setWorkflowToDelete(workflow)
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!workflowToDelete) return
    await deleteWorkflowMutation.mutateAsync(workflowToDelete.code)
    setDeleteDialogOpen(false)
    setWorkflowToDelete(null)
  }

  // Render tariff info
  const renderTariffs = (tariffsList: WorkflowTariff[]) => {
    const activeTariffs = tariffsList.filter((t) => t.is_active)
    if (activeTariffs.length === 0) {
      return <span className="text-muted-foreground text-xs">Sin tarifas</span>
    }

    return (
      <div className="flex flex-wrap gap-1">
        {activeTariffs.slice(0, 3).map((tariff, idx) => {
          const isRBC = tariff.tariff_type === 'PERCENTAGE' || tariff.tariff_type === 'RBC'
          return (
            <Badge key={idx} variant="outline" className="text-xs">
              {tariff.solicitud_type?.substring(0, 3) || 'N/A'}:{' '}
              {isRBC ? (
                <span className="flex items-center gap-0.5">
                  <Calculator className="h-2.5 w-2.5" />
                  RBC
                </span>
              ) : (
                formatCurrency(tariff.amount)
              )}
            </Badge>
          )
        })}
        {activeTariffs.length > 3 && (
          <Badge variant="secondary" className="text-xs">
            +{activeTariffs.length - 3}
          </Badge>
        )}
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (workflowsError) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>{workflowsError instanceof Error ? workflowsError.message : 'Error loading workflows'}</span>
            </div>
            <Button variant="outline" className="mt-4" onClick={() => refetch()}>
              {tCommon('retry')}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
        <Button onClick={navigateToNewWorkflow}>
          <Plus className="mr-2 h-4 w-4" />
          {t('create')}
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Workflows</CardTitle>
            <GitBranch className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalWorkflows}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Predefinidos</CardTitle>
            <Lock className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{predefinedCount}</div>
            <p className="text-xs text-muted-foreground">Solo lectura</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Dinámicos</CardTitle>
            <Pencil className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{dynamicCount}</div>
            <p className="text-xs text-muted-foreground">Editables</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-5 w-5" />
                Workflows Agrupados
              </CardTitle>
              <CardDescription>
                {filteredGroups.reduce((acc, g) => acc + g.workflows.length, 0)} workflows en {filteredGroups.length} grupos por métier
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={expandAllGroups}>
                <FolderOpen className="h-4 w-4 mr-1" />
                Expandir
              </Button>
              <Button variant="outline" size="sm" onClick={collapseAllGroups}>
                <Folder className="h-4 w-4 mr-1" />
                Colapsar
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder={t('filterByCategory')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allCategories')}</SelectItem>
                {WORKFLOW_CATEGORIES_MAP.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    {cat.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder={t('filterByStatus')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allStatuses')}</SelectItem>
                <SelectItem value="active">{t('active')}</SelectItem>
                <SelectItem value="inactive">{t('inactive')}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Tipo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="predefined">Predefinidos</SelectItem>
                <SelectItem value="dynamic">Dinámicos</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Workflow List by Business Domain */}
          {filteredGroups.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <GitBranch className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('noWorkflowsFound')}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredGroups.map((group) => {
                const isExpanded = expandedGroups.has(group.domain.id)
                const colorClasses = getDomainColorClasses(group.domain.color)

                return (
                  <Collapsible
                    key={group.domain.id}
                    open={isExpanded}
                    onOpenChange={() => toggleGroup(group.domain.id)}
                    className={cn('border rounded-lg overflow-hidden', colorClasses.border)}
                  >
                    {/* Group Header - Domain */}
                    <CollapsibleTrigger asChild>
                      <div className={cn(
                        'flex items-center justify-between p-4 cursor-pointer transition-colors',
                        isExpanded ? colorClasses.bg : 'hover:bg-muted/50'
                      )}>
                        <div className="flex items-center gap-3">
                          <ChevronRight
                            className={cn(
                              'h-5 w-5 transition-transform duration-200',
                              colorClasses.text,
                              isExpanded && 'transform rotate-90'
                            )}
                          />
                          <div>
                            <div className="font-semibold text-lg flex items-center gap-2">
                              {group.domain.name}
                              <Badge variant="secondary" className="text-xs">
                                {group.workflows.length}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {group.domain.description}
                            </p>
                          </div>
                        </div>
                        {/* Stats badges */}
                        <div className="hidden md:flex gap-2">
                          {group.predefinedCount > 0 && (
                            <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
                              <Lock className="h-3 w-3 mr-1" />
                              {group.predefinedCount} predefinidos
                            </Badge>
                          )}
                          {group.dynamicCount > 0 && (
                            <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-200">
                              <Pencil className="h-3 w-3 mr-1" />
                              {group.dynamicCount} dinámicos
                            </Badge>
                          )}
                        </div>
                      </div>
                    </CollapsibleTrigger>

                    {/* Group Content - Workflows */}
                    <CollapsibleContent>
                      <div className="border-t bg-white">
                        {group.workflows.map((wf) => (
                          <div
                            key={wf.code}
                            className="flex items-center justify-between px-4 py-3 border-b last:border-b-0 hover:bg-muted/50 cursor-pointer transition-colors"
                            onClick={() => navigateToWorkflow(wf.code)}
                          >
                            {/* Left side: Info */}
                            <div className="flex items-center gap-4 flex-1 min-w-0">
                              {/* Indentation indicator */}
                              <div className="w-6 border-l-2 border-muted-foreground/30 h-8" />

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <code className="text-sm bg-muted px-2 py-0.5 rounded font-mono">
                                    {wf.code}
                                  </code>
                                  {/* Source type badge */}
                                  {wf.is_generic === false ? (
                                    <Badge variant="default" className="text-xs bg-blue-100 text-blue-700 hover:bg-blue-100">
                                      <Lock className="h-3 w-3 mr-1" />
                                      Predefinido
                                    </Badge>
                                  ) : (
                                    <Badge variant="secondary" className="text-xs">
                                      <Pencil className="h-3 w-3 mr-1" />
                                      Dinámico
                                    </Badge>
                                  )}
                                  {/* Status indicator */}
                                  {wf.is_active ? (
                                    <CheckCircle className="h-4 w-4 text-green-500" />
                                  ) : (
                                    <XCircle className="h-4 w-4 text-red-500" />
                                  )}
                                </div>
                                <div className="text-sm font-medium mt-1">{tw(workflowNameKey(wf.code), wf.name_es)}</div>
                                <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                                  <span>{wf.entity_code}</span>
                                  <span>•</span>
                                  <span className="flex items-center gap-1">
                                    <FileText className="h-3 w-3" />
                                    {wf.documents_count || 0} docs
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Middle: Tariffs */}
                            <div className="hidden lg:flex items-center gap-2 px-4">
                              <DollarSign className="h-4 w-4 text-muted-foreground" />
                              {renderTariffs(wf.tariffsList)}
                            </div>

                            {/* Right side: Actions */}
                            <div className="flex items-center gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  navigateToWorkflow(wf.code)
                                }}
                                title={tCommon('view')}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              {wf.is_generic && (
                                <>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      router.push(`/${locale}/dashboard/admin/service-requests/workflows/${wf.code}?mode=edit`)
                                    }}
                                    title={tCommon('edit')}
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                    onClick={(e) => handleDeleteClick(e, wf)}
                                    title={tCommon('delete')}
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteConfirmDescription', { code: workflowToDelete?.code || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleConfirmDelete}
              disabled={deleteWorkflowMutation.isPending}
            >
              {deleteWorkflowMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {tCommon('deleting')}
                </>
              ) : (
                tCommon('delete')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
