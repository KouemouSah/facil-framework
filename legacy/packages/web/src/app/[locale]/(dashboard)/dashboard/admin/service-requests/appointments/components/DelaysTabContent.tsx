'use client'

import { useState, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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
  DialogTrigger,
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
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Clock,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import {
  useWorkflows,
  useDelayRules,
  useCreateDelayRule,
  useUpdateDelayRule,
  useDeleteDelayRule,
} from '@/modules/service-requests-admin'
import type {
  AppointmentDelayRule,
  AppointmentDelayRuleCreate,
  AppointmentDelayRuleUpdate,
  AppointmentPriority,
} from '@/modules/service-requests-admin'
import { PRIORITY_LABELS } from '@/modules/service-requests-admin'
import { DataTablePagination, usePagination } from '@/modules/service-requests-admin/components'

export default function DelaysTabContent() {
  const t = useTranslations('admin.serviceRequests.appointments.delays')
  const tCommon = useTranslations('common')

  // State
  const [workflowFilter, setWorkflowFilter] = useState<string>('all')
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedRule, setSelectedRule] = useState<AppointmentDelayRule | null>(null)

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

  // Form state
  const [formData, setFormData] = useState<AppointmentDelayRuleCreate>({
    workflow_code: null,
    priority: 'NORMAL',
    delay_business_days: 3,
    is_active: true,
  })

  // Queries
  const { data: workflows } = useWorkflows()
  const {
    data: delayRules,
    isLoading,
    error,
    refetch,
  } = useDelayRules(workflowFilter === 'all' ? undefined : workflowFilter === 'default' ? undefined : workflowFilter)

  // Mutations
  const createMutation = useCreateDelayRule()
  const updateMutation = useUpdateDelayRule()
  const deleteMutation = useDeleteDelayRule()

  // Sort and filter rules: default first, then by workflow and priority
  const filteredRules = useMemo(() => {
    let result = [...(delayRules || [])]

    // Filter by workflow
    if (workflowFilter === 'default') {
      result = result.filter((r) => !r.workflow_code)
    } else if (workflowFilter !== 'all') {
      result = result.filter((r) => r.workflow_code === workflowFilter)
    }

    // Sort: default first, then by workflow and priority
    return result.sort((a, b) => {
      if (!a.workflow_code && b.workflow_code) return -1
      if (a.workflow_code && !b.workflow_code) return 1
      if (a.workflow_code && b.workflow_code) {
        if (a.workflow_code !== b.workflow_code) {
          return a.workflow_code.localeCompare(b.workflow_code)
        }
      }
      const priorityOrder = ['URGENT', 'HIGH', 'NORMAL', 'LOW']
      return priorityOrder.indexOf(a.priority) - priorityOrder.indexOf(b.priority)
    })
  }, [delayRules, workflowFilter])

  // Pagination
  const paginatedRules = paginateData(filteredRules)
  const totalPages = getTotalPages(filteredRules.length)

  // Handlers
  const handleCreateRule = async () => {
    try {
      await createMutation.mutateAsync(formData)
      setIsCreateDialogOpen(false)
      resetForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleUpdateRule = async () => {
    if (!selectedRule) return

    try {
      const updateData: AppointmentDelayRuleUpdate = {
        delay_business_days: formData.delay_business_days,
        is_active: formData.is_active,
      }
      await updateMutation.mutateAsync({ ruleId: selectedRule.id, data: updateData })
      setIsEditDialogOpen(false)
      setSelectedRule(null)
      resetForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleDeleteRule = async () => {
    if (!selectedRule) return

    try {
      await deleteMutation.mutateAsync(selectedRule.id)
      setIsDeleteDialogOpen(false)
      setSelectedRule(null)
    } catch {
      // Error handled by mutation
    }
  }

  const openEditDialog = (rule: AppointmentDelayRule) => {
    setSelectedRule(rule)
    setFormData({
      workflow_code: rule.workflow_code || null,
      priority: rule.priority as AppointmentPriority,
      delay_business_days: rule.delay_business_days,
      is_active: rule.is_active,
    })
    setIsEditDialogOpen(true)
  }

  const openDeleteDialog = (rule: AppointmentDelayRule) => {
    setSelectedRule(rule)
    setIsDeleteDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      workflow_code: null,
      priority: 'NORMAL',
      delay_business_days: 3,
      is_active: true,
    })
    setSelectedRule(null)
  }

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'URGENT':
        return <Badge variant="destructive">{PRIORITY_LABELS.URGENT}</Badge>
      case 'HIGH':
        return <Badge variant="default">{PRIORITY_LABELS.HIGH}</Badge>
      case 'NORMAL':
        return <Badge variant="secondary">{PRIORITY_LABELS.NORMAL}</Badge>
      case 'LOW':
        return <Badge variant="outline">{PRIORITY_LABELS.LOW}</Badge>
      default:
        return <Badge variant="outline">{priority}</Badge>
    }
  }

  // Render loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Render error state
  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : 'Error loading delay rules'}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            {tCommon('retry')}
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Actions Bar */}
      <div className="flex justify-end">
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => resetForm()}>
              <Plus className="mr-2 h-4 w-4" />
              {t('create')}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('create')}</DialogTitle>
              <DialogDescription>{t('createDescription')}</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="workflow">{t('workflow')}</Label>
                <Select
                  value={formData.workflow_code || 'default'}
                  onValueChange={(value) =>
                    setFormData({ ...formData, workflow_code: value === 'default' ? null : value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectWorkflow')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">{t('defaultAllWorkflows')}</SelectItem>
                    {workflows?.map((wf) => (
                      <SelectItem key={wf.code} value={wf.code}>
                        {wf.code} - {wf.name_es}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t('workflowHint')}</p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="priority">{t('priority')}</Label>
                <Select
                  value={formData.priority}
                  onValueChange={(value) =>
                    setFormData({ ...formData, priority: value as AppointmentPriority })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="URGENT">{PRIORITY_LABELS.URGENT}</SelectItem>
                    <SelectItem value="HIGH">{PRIORITY_LABELS.HIGH}</SelectItem>
                    <SelectItem value="NORMAL">{PRIORITY_LABELS.NORMAL}</SelectItem>
                    <SelectItem value="LOW">{PRIORITY_LABELS.LOW}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="days">{t('delayDays')}</Label>
                <Input
                  id="days"
                  type="number"
                  value={formData.delay_business_days}
                  onChange={(e) =>
                    setFormData({ ...formData, delay_business_days: parseInt(e.target.value) || 3 })
                  }
                  min={0}
                  max={30}
                />
                <p className="text-xs text-muted-foreground">{t('delayDaysHint')}</p>
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="is_active_rule">{t('isActive')}</Label>
                <Switch
                  id="is_active_rule"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                {tCommon('cancel')}
              </Button>
              <Button onClick={handleCreateRule} disabled={createMutation.isPending}>
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {tCommon('create')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Info Card */}
      <Card className="bg-muted/50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <Clock className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="space-y-1">
              <p className="text-sm font-medium">{t('infoTitle')}</p>
              <p className="text-sm text-muted-foreground">{t('infoDescription')}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Rules List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            {t('title')}
          </CardTitle>
          <CardDescription>{filteredRules.length} reglas de retraso</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-4">
            <Select
              value={workflowFilter}
              onValueChange={(v) => {
                setWorkflowFilter(v)
                resetPage()
              }}
            >
              <SelectTrigger className="w-[250px]">
                <SelectValue placeholder={t('filterByWorkflow')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allRules')}</SelectItem>
                <SelectItem value="default">{t('defaultOnly')}</SelectItem>
                {workflows?.map((wf) => (
                  <SelectItem key={wf.code} value={wf.code}>
                    {wf.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Rules Table */}
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('workflow')}</TableHead>
                  <TableHead>{t('priority')}</TableHead>
                  <TableHead className="text-center">{t('delayDays')}</TableHead>
                  <TableHead className="text-center">{t('status')}</TableHead>
                  <TableHead className="text-right">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedRules.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      {t('noRulesFound')}
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedRules.map((rule) => (
                    <TableRow key={rule.id}>
                      <TableCell>
                        {rule.workflow_code ? (
                          <code className="text-sm bg-muted px-2 py-1 rounded">{rule.workflow_code}</code>
                        ) : (
                          <Badge variant="default">{t('default')}</Badge>
                        )}
                      </TableCell>
                      <TableCell>{getPriorityBadge(rule.priority)}</TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-lg">{rule.delay_business_days}</span>
                        <span className="text-muted-foreground text-sm ml-1">{t('daysUnit')}</span>
                      </TableCell>
                      <TableCell className="text-center">
                        {rule.is_active ? (
                          <CheckCircle className="h-5 w-5 text-green-500 mx-auto" />
                        ) : (
                          <XCircle className="h-5 w-5 text-red-500 mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEditDialog(rule)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openDeleteDialog(rule)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <DataTablePagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={filteredRules.length}
            pageSize={pageSize}
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[10, 20, 30, 50]}
          />
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteConfirmDescription', {
                priority: PRIORITY_LABELS[selectedRule?.priority as AppointmentPriority] || selectedRule?.priority,
                workflow: selectedRule?.workflow_code || t('default'),
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteRule}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('edit')}</DialogTitle>
            <DialogDescription>{t('editDescription')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>{t('workflow')}</Label>
              <div className="p-2 bg-muted rounded-md text-sm">
                {selectedRule?.workflow_code ? (
                  <code>{selectedRule.workflow_code}</code>
                ) : (
                  <span>{t('defaultAllWorkflows')}</span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{t('workflowReadOnly')}</p>
            </div>
            <div className="grid gap-2">
              <Label>{t('priority')}</Label>
              <div className="p-2 bg-muted rounded-md text-sm">
                {PRIORITY_LABELS[formData.priority as AppointmentPriority] || formData.priority}
              </div>
              <p className="text-xs text-muted-foreground">{t('priorityReadOnly')}</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_days">{t('delayDays')}</Label>
              <Input
                id="edit_days"
                type="number"
                value={formData.delay_business_days}
                onChange={(e) =>
                  setFormData({ ...formData, delay_business_days: parseInt(e.target.value) || 0 })
                }
                min={0}
                max={30}
              />
              <p className="text-xs text-muted-foreground">{t('delayDaysHint')}</p>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="edit_is_active">{t('isActive')}</Label>
              <Switch
                id="edit_is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button onClick={handleUpdateRule} disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {tCommon('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
