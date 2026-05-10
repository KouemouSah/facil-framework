'use client'

import { useState, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DollarSign,
  Search,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  Receipt,
  TrendingUp,
  FileText,
  BarChart3,
} from 'lucide-react'
import {
  useWorkflows,
  useTariffs,
  useSupplements,
  WORKFLOW_CATEGORIES_MAP,
} from '@/modules/service-requests-admin'
import type {
  Workflow,
  WorkflowTariff,
} from '@/modules/service-requests-admin'
import { DataTablePagination, usePagination } from '@/modules/service-requests-admin/components'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'
import SupplementsTabContent from './components/SupplementsTabContent'

// Format currency
const formatCurrency = (amount: number, currency: string = 'XAF') => {
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
  }).format(amount)
}

// Interface for workflow with calculated tariff data
interface WorkflowTariffSummary {
  workflow: Workflow
  tariffs: {
    expedicion: { tariff: WorkflowTariff | null; total: number }
    renovacion: { tariff: WorkflowTariff | null; total: number }
    duplicado: { tariff: WorkflowTariff | null; total: number }
  }
  hasTariffs: boolean
}

export default function TariffsPage() {
  const t = useTranslations('admin.serviceRequests.tariffs')
  const tCommon = useTranslations('common')
  const { tw } = useWorkflowTranslations()
  const [activeTab, setActiveTab] = useState('overview')

  // State
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  // Pagination
  const {
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
    paginateData,
    getTotalPages,
    resetPage,
  } = usePagination(10)

  // Queries
  const { data: workflows, isLoading: loadingWorkflows } = useWorkflows()
  const { data: tariffs, isLoading: loadingTariffs, error, refetch } = useTariffs()
  const { data: supplements, isLoading: loadingSupplements } = useSupplements()

  const isLoading = loadingWorkflows || loadingTariffs || loadingSupplements

  // Calculate workflow summaries with tariffs
  const workflowSummaries: WorkflowTariffSummary[] = useMemo(() => {
    if (!workflows || !tariffs) return []

    return workflows.map((wf) => {
      const getTypeTariff = (type: string) => {
        const tariff = tariffs.find(
          (t) => t.workflow_code === wf.code && t.solicitud_type === type && t.is_active
        ) ?? null
        return {
          tariff,
          total: tariff?.amount || 0,
        }
      }

      const expedicion = getTypeTariff('expedicion')
      const renovacion = getTypeTariff('renovacion')
      const duplicado = getTypeTariff('duplicado')

      return {
        workflow: wf,
        tariffs: { expedicion, renovacion, duplicado },
        hasTariffs: !!(expedicion.tariff || renovacion.tariff || duplicado.tariff),
      }
    })
  }, [workflows, tariffs])

  // Calculate statistics
  const statistics = useMemo(() => {
    if (!workflows || !tariffs || !supplements) {
      return {
        totalWorkflows: 0,
        workflowsWithTariffs: 0,
        totalActiveTariffs: 0,
        totalActiveSupplements: 0,
        averageTariff: 0,
        totalTariffValue: 0,
      }
    }

    const activeTariffs = tariffs.filter((t) => t.is_active)
    const activeSupplements = supplements.filter((s) => s.is_active)
    const workflowsWithTariffs = new Set(activeTariffs.map((t) => t.workflow_code)).size
    const totalTariffValue = activeTariffs.reduce((sum, t) => sum + t.amount, 0)
    const averageTariff = activeTariffs.length > 0 ? totalTariffValue / activeTariffs.length : 0

    return {
      totalWorkflows: workflows.length,
      workflowsWithTariffs,
      totalActiveTariffs: activeTariffs.length,
      totalActiveSupplements: activeSupplements.length,
      averageTariff,
      totalTariffValue,
    }
  }, [workflows, tariffs, supplements])

  // Filter workflows
  const filteredSummaries = useMemo(() => {
    let result = workflowSummaries

    if (statusFilter === 'with_tariffs') {
      result = result.filter((ws) => ws.hasTariffs)
    } else if (statusFilter === 'without_tariffs') {
      result = result.filter((ws) => !ws.hasTariffs)
    }

    if (categoryFilter !== 'all') {
      result = result.filter((ws) => ws.workflow.category === categoryFilter)
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (ws) =>
          ws.workflow.code.toLowerCase().includes(query) ||
          ws.workflow.name_es.toLowerCase().includes(query) ||
          tw(workflowNameKey(ws.workflow.code), ws.workflow.name_es).toLowerCase().includes(query)
      )
    }

    return result
  }, [workflowSummaries, statusFilter, categoryFilter, searchQuery, tw])

  // Pagination
  const paginatedSummaries = paginateData(filteredSummaries)
  const totalPages = getTotalPages(filteredSummaries.length)

  // Handle filter changes
  const handleFilterChange = (setter: (value: string) => void, value: string) => {
    setter(value)
    resetPage()
  }

  // Get tariff display
  const getTariffDisplay = (tariff: WorkflowTariff | null) => {
    if (!tariff) return <span className="text-muted-foreground">-</span>

    const typeLabel = tariff.tariff_type === 'FIXED' ? 'Fijo' :
                      tariff.tariff_type === 'PERCENTAGE' ? '%' : 'RBC'
    const amount = tariff.tariff_type === 'PERCENTAGE'
      ? `${tariff.percentage_rate}%`
      : formatCurrency(tariff.amount)

    return (
      <div className="flex items-center justify-end gap-2">
        <Badge variant="outline" className="text-xs">{typeLabel}</Badge>
        <span className="font-mono">{amount}</span>
      </div>
    )
  }

  // Get category label
  const getCategoryLabel = (value: string) => {
    const cat = WORKFLOW_CATEGORIES_MAP.find((c) => c.value === value)
    return cat?.label || value
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
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
              <span>{error instanceof Error ? error.message : 'Error loading tariffs'}</span>
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
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground">{t('subtitle')}</p>
      </div>

      {/* Statistics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Workflows con Tarifas</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statistics.workflowsWithTariffs}</div>
            <p className="text-xs text-muted-foreground">
              de {statistics.totalWorkflows} workflows totales
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tarifas Activas</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statistics.totalActiveTariffs}</div>
            <p className="text-xs text-muted-foreground">
              Promedio: {formatCurrency(statistics.averageTariff)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Suplementos Activos</CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statistics.totalActiveSupplements}</div>
            <p className="text-xs text-muted-foreground">
              Configurados globalmente
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Valor Total Tarifas</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(statistics.totalTariffValue)}</div>
            <p className="text-xs text-muted-foreground">
              Suma de todas las tarifas activas
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            Vista por Workflow
          </TabsTrigger>
          <TabsTrigger value="supplements" className="gap-2">
            <Receipt className="h-4 w-4" />
            {t('tabs.supplements')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Tarifas por Workflow
              </CardTitle>
              <CardDescription>
                {filteredSummaries.length} de {workflowSummaries.length} workflows
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-4 mb-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar por código o nombre..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value)
                      resetPage()
                    }}
                    className="pl-9"
                  />
                </div>
                <Select
                  value={categoryFilter}
                  onValueChange={(v) => handleFilterChange(setCategoryFilter, v)}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Categoría" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas las categorías</SelectItem>
                    {WORKFLOW_CATEGORIES_MAP.map((cat) => (
                      <SelectItem key={cat.value} value={cat.value}>
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={statusFilter}
                  onValueChange={(v) => handleFilterChange(setStatusFilter, v)}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Estado" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    <SelectItem value="with_tariffs">Con tarifas</SelectItem>
                    <SelectItem value="without_tariffs">Sin tarifas</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[200px]">Workflow</TableHead>
                      <TableHead>Categoría</TableHead>
                      <TableHead className="text-right">Expedición</TableHead>
                      <TableHead className="text-right">Renovación</TableHead>
                      <TableHead className="text-right">Duplicado</TableHead>
                      <TableHead className="text-center">Estado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedSummaries.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                          No se encontraron workflows
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedSummaries.map((summary) => (
                        <TableRow key={summary.workflow.code} className="hover:bg-muted/50">
                          <TableCell>
                            <div>
                              <code className="text-sm bg-muted px-2 py-1 rounded">
                                {summary.workflow.code}
                              </code>
                              <div className="text-sm text-muted-foreground mt-1">
                                {tw(workflowNameKey(summary.workflow.code), summary.workflow.name_es)}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {getCategoryLabel(summary.workflow.category)}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            {getTariffDisplay(summary.tariffs.expedicion.tariff)}
                          </TableCell>
                          <TableCell className="text-right">
                            {getTariffDisplay(summary.tariffs.renovacion.tariff)}
                          </TableCell>
                          <TableCell className="text-right">
                            {getTariffDisplay(summary.tariffs.duplicado.tariff)}
                          </TableCell>
                          <TableCell className="text-center">
                            {summary.hasTariffs ? (
                              <CheckCircle className="h-5 w-5 text-green-500 mx-auto" />
                            ) : (
                              <XCircle className="h-5 w-5 text-red-500 mx-auto" />
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>

              <DataTablePagination
                currentPage={currentPage}
                totalPages={totalPages}
                totalItems={filteredSummaries.length}
                pageSize={pageSize}
                onPageChange={setCurrentPage}
                onPageSizeChange={setPageSize}
                pageSizeOptions={[10, 20, 30, 50]}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="supplements">
          <SupplementsTabContent />
        </TabsContent>
      </Tabs>
    </div>
  )
}