'use client'

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  DollarSign,
  FileCheck,
  CalendarClock,
  Clock,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  ArrowUp,
  ArrowDown,
  GripVertical,
  Save,
  X,
  Boxes,
  Eye,
  MapPin,
  ExternalLink,
  ChevronDown,
  Tag,
} from 'lucide-react'
import {
  useWorkflow,
  useWorkflows,
  useUpdateWorkflow,
  useTariffs,
  useCreateTariff,
  useUpdateTariff,
  useDeleteTariff,
  useSupplements,
  useWorkflowSupplements,
  useAddWorkflowSupplement,
  useUpdateWorkflowSupplement,
  useRemoveWorkflowSupplement,
  useDocumentRequirements,
  useAddDocumentRequirement,
  useUpdateDocumentRequirement,
  useRemoveDocumentRequirement,
  useReorderDocuments,
  useSlotConfigs,
  useBlockedDates,
  useDelayRules,
  useCreateDelayRule,
  useUpdateDelayRule,
  useDeleteDelayRule,
  DOCUMENT_CONDITION_TYPES,
  TARIFF_TYPES,
  WORKFLOW_TYPES,
  PRIORITY_LABELS,
  DAY_OF_WEEK_LABELS,
  useExtractionSchemas,
} from '@/modules/service-requests-admin'
import type {
  WorkflowType,
  WorkflowUpdate,
  WorkflowTariff,
  WorkflowTariffCreate,
  WorkflowTariffUpdate,
  TariffType,
  WorkflowSupplementConfig,
  WorkflowSupplementConfigCreate,
  WorkflowSupplementConfigUpdate,
  DocumentRequirement,
  DocumentRequirementCreate,
  DocumentRequirementUpdate,
  DocumentConditionType,
  DocumentReorderItem,
  AppointmentPriority,
} from '@/modules/service-requests-admin'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'

export default function WorkflowDetailPage() {
  const t = useTranslations('admin.serviceRequests.workflows')
  const tTariffs = useTranslations('admin.serviceRequests.tariffs')
  const tDocs = useTranslations('admin.serviceRequests.documents')
  const tCommon = useTranslations('common')
  const { tw } = useWorkflowTranslations()
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()

  const workflowCode = params.code as string
  const locale = params.locale as string
  const initialTab = searchParams.get('tab') || 'info'
  const [activeTab, setActiveTab] = useState(initialTab)

  // Workflow data
  const { data: workflow, isLoading: loadingWorkflow, error: workflowError, refetch } = useWorkflow(workflowCode)
  const { data: allWorkflows } = useWorkflows()
  const updateWorkflowMutation = useUpdateWorkflow()

  // Calculate prev/next navigation
  const workflowCodes = allWorkflows?.map((w) => w.code) || []
  const currentIndex = workflowCodes.indexOf(workflowCode)
  const prevWorkflowCode = currentIndex > 0 ? workflowCodes[currentIndex - 1] : null
  const nextWorkflowCode = currentIndex >= 0 && currentIndex < workflowCodes.length - 1 ? workflowCodes[currentIndex + 1] : null
  const workflowPosition = currentIndex >= 0 ? `${currentIndex + 1} de ${workflowCodes.length}` : ''

  // Workflow edit state
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<Partial<WorkflowUpdate>>({})
  const [newTag, setNewTag] = useState('')

  // Page view mode: false = summary dashboard, true = tabbed editing
  const initialMode = searchParams.get('mode')
  const [isEditingPage, setIsEditingPage] = useState(initialMode === 'edit')

  // Collapsible sections in view mode
  const [docsExpanded, setDocsExpanded] = useState(false)

  // Tariffs data
  const { data: allTariffs, isLoading: loadingTariffs } = useTariffs({ workflow_code: workflowCode })
  const createTariffMutation = useCreateTariff()
  const updateTariffMutation = useUpdateTariff()
  const deleteTariffMutation = useDeleteTariff()

  // Tariff inline form state
  type TariffEditMode = 'none' | 'create' | 'edit'
  const [tariffEditMode, setTariffEditMode] = useState<TariffEditMode>('none')
  const [editingTariffId, setEditingTariffId] = useState<number | null>(null)
  const [isDeleteTariffDialogOpen, setIsDeleteTariffDialogOpen] = useState(false)
  const [tariffToDelete, setTariffToDelete] = useState<WorkflowTariff | null>(null)
  const [tariffForm, setTariffForm] = useState<WorkflowTariffCreate>({
    workflow_code: workflowCode,
    solicitud_type: 'expedicion',
    tariff_type: 'FIXED',
    amount: 0,
    percentage_rate: null,
    currency: 'XAF',
    legal_reference: '',
    effective_from: new Date().toISOString().split('T')[0],
    effective_to: null,
    is_active: true,
  })

  // Supplements data
  const { data: allSupplements } = useSupplements(true) // Get only active supplements
  const { data: workflowSupplements, isLoading: loadingSupplements } = useWorkflowSupplements(workflowCode)
  const addWorkflowSupplementMutation = useAddWorkflowSupplement()
  const updateWorkflowSupplementMutation = useUpdateWorkflowSupplement()
  const removeWorkflowSupplementMutation = useRemoveWorkflowSupplement()

  // Supplement inline form state
  type SupplementEditMode = 'none' | 'create' | 'edit'
  const [supplementEditMode, setSupplementEditMode] = useState<SupplementEditMode>('none')
  const [editingSupplementCode, setEditingSupplementCode] = useState<string | null>(null)
  const [isDeleteSupplementDialogOpen, setIsDeleteSupplementDialogOpen] = useState(false)
  const [supplementToDelete, setSupplementToDelete] = useState<WorkflowSupplementConfig | null>(null)
  const [supplementForm, setSupplementForm] = useState<WorkflowSupplementConfigCreate>({
    supplement_code: '',
    quantity_per_request: 1,
    is_required: false,
    is_active: true,
  })

  // Batch supplement additions for multi-add
  interface PendingSupplement {
    supplement_code: string
    supplement_name: string
    supplement_amount: number
    quantity_per_request: number
    is_required: boolean
  }
  const [pendingSupplements, setPendingSupplements] = useState<PendingSupplement[]>([])
  const [isSavingBatch, setIsSavingBatch] = useState(false)

  // Documents data
  const { data: documents, isLoading: loadingDocuments } = useDocumentRequirements(workflowCode)
  const addDocumentMutation = useAddDocumentRequirement()
  const updateDocumentMutation = useUpdateDocumentRequirement()
  const removeDocumentMutation = useRemoveDocumentRequirement()
  const reorderDocumentsMutation = useReorderDocuments()

  // Document inline form state
  type DocumentEditMode = 'none' | 'create' | 'edit'
  const [documentEditMode, setDocumentEditMode] = useState<DocumentEditMode>('none')
  const [editingDocumentCode, setEditingDocumentCode] = useState<string | null>(null)
  const [isDeleteDocDialogOpen, setIsDeleteDocDialogOpen] = useState(false)
  const [documentToDelete, setDocumentToDelete] = useState<DocumentRequirement | null>(null)
  const [docForm, setDocForm] = useState<DocumentRequirementCreate>({
    document_code: '',
    document_name_es: '',
    condition_type: 'always',
    is_required: true,
    display_order: 0,
    instructions_es: '',
    extraction_schema_key: '',
    is_active: true,
  })

  // Batch document additions for multi-add
  interface PendingDocument {
    document_code: string
    document_name_es: string
    condition_type: string
    is_required: boolean
    instructions_es: string
    extraction_schema_key: string
  }
  const [pendingDocuments, setPendingDocuments] = useState<PendingDocument[]>([])
  const [isSavingDocBatch, setIsSavingDocBatch] = useState(false)

  // Extraction schemas (for document OCR dropdown)
  const { data: extractionSchemas } = useExtractionSchemas()

  // Appointments data
  const { data: slotConfigs } = useSlotConfigs({ entity_code: workflow?.entity_code })
  const { data: blockedDates } = useBlockedDates({ entity_code: workflow?.entity_code })
  const { data: delayRules } = useDelayRules(workflowCode)
  
  // Delay rules mutations
  const createDelayRuleMutation = useCreateDelayRule()
  const updateDelayRuleMutation = useUpdateDelayRule()
  const deleteDelayRuleMutation = useDeleteDelayRule()
  
  // Delay rule form state
  const [isAddingDelayRule, setIsAddingDelayRule] = useState(false)
  const [editingDelayRule, setEditingDelayRule] = useState<string | null>(null)
  const [deleteDelayRuleId, setDeleteDelayRuleId] = useState<string | null>(null)
  const [delayRuleForm, setDelayRuleForm] = useState<{
    priority: AppointmentPriority
    delay_business_days: number
    is_active: boolean
  }>({
    priority: 'NORMAL',
    delay_business_days: 3,
    is_active: true,
  })

  // Update URL when tab changes
  const handleTabChange = (value: string) => {
    setActiveTab(value)
    const newUrl = `/${locale}/dashboard/admin/service-requests/workflows/${workflowCode}?tab=${value}`
    router.push(newUrl, { scroll: false })
  }

  // Initialize edit form when workflow loads
  useEffect(() => {
    if (workflow) {
      setEditForm({
        name_es: workflow.name_es,
        description_es: workflow.description_es,
        workflow_type: workflow.workflow_type,
        requires_agent_validation: workflow.requires_agent_validation,
        requires_appointment: workflow.requires_appointment,
        sla_hours: workflow.sla_hours,
        display_order: workflow.display_order,
        max_processing_days: workflow.max_processing_days,
        appointment_delay_days: workflow.appointment_delay_days,
        tags: workflow.tags,
        parent_workflow_code: workflow.parent_workflow_code,
        is_parent: workflow.is_parent,
        is_active: workflow.is_active,
      })
    }
  }, [workflow])

  // Handlers - Workflow
  const handleSaveWorkflow = async () => {
    try {
      await updateWorkflowMutation.mutateAsync({ code: workflowCode, data: editForm as WorkflowUpdate })
      setIsEditing(false)
    } catch {
      // Error handled by mutation
    }
  }

  // Handlers - Tariffs
  const resetTariffForm = () => {
    setTariffForm({
      workflow_code: workflowCode,
      solicitud_type: 'expedicion',
      tariff_type: 'FIXED',
      amount: 0,
      percentage_rate: null,
      currency: 'XAF',
      legal_reference: '',
      effective_from: new Date().toISOString().split('T')[0],
      effective_to: null,
      is_active: true,
    })
    setTariffEditMode('none')
    setEditingTariffId(null)
  }

  const startCreateTariff = () => {
    resetTariffForm()
    setTariffEditMode('create')
  }

  const startEditTariff = (tariff: WorkflowTariff) => {
    setTariffForm({
      workflow_code: tariff.workflow_code,
      solicitud_type: tariff.solicitud_type,
      tariff_type: tariff.tariff_type as TariffType,
      amount: tariff.amount,
      percentage_rate: tariff.percentage_rate,
      currency: tariff.currency,
      legal_reference: tariff.legal_reference || '',
      effective_from: tariff.effective_from,
      effective_to: tariff.effective_to,
      is_active: tariff.is_active,
    })
    setEditingTariffId(tariff.id)
    setTariffEditMode('edit')
  }

  const handleSaveTariff = async () => {
    try {
      if (tariffEditMode === 'create') {
        await createTariffMutation.mutateAsync({ ...tariffForm, workflow_code: workflowCode })
      } else if (tariffEditMode === 'edit' && editingTariffId) {
        const updateData: WorkflowTariffUpdate = {
          solicitud_type: tariffForm.solicitud_type,
          tariff_type: tariffForm.tariff_type as TariffType,
          amount: tariffForm.amount,
          percentage_rate: tariffForm.percentage_rate,
          currency: tariffForm.currency,
          legal_reference: tariffForm.legal_reference,
          effective_to: tariffForm.effective_to,
          is_active: tariffForm.is_active,
        }
        await updateTariffMutation.mutateAsync({ tariffId: editingTariffId, data: updateData })
      }
      resetTariffForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleDeleteTariff = async () => {
    if (!tariffToDelete) return
    try {
      await deleteTariffMutation.mutateAsync(tariffToDelete.id)
      setIsDeleteTariffDialogOpen(false)
      setTariffToDelete(null)
    } catch {
      // Error handled by mutation
    }
  }

  const isTariffSaving = createTariffMutation.isPending || updateTariffMutation.isPending

  // Handlers - Supplements
  const resetSupplementForm = () => {
    setSupplementForm({
      supplement_code: '',
      quantity_per_request: 1,
      is_required: false,
      is_active: true,
    })
    setSupplementEditMode('none')
    setEditingSupplementCode(null)
  }

  const startCreateSupplement = () => {
    resetSupplementForm()
    setSupplementEditMode('create')
  }

  const startEditSupplement = (config: WorkflowSupplementConfig) => {
    setSupplementForm({
      supplement_code: config.supplement_code,
      quantity_per_request: config.quantity_per_request,
      is_required: config.is_required,
      is_active: config.is_active,
    })
    setEditingSupplementCode(config.supplement_code)
    setSupplementEditMode('edit')
  }

  const handleSaveSupplement = async () => {
    try {
      if (supplementEditMode === 'create') {
        await addWorkflowSupplementMutation.mutateAsync({
          workflowCode,
          data: supplementForm,
        })
      } else if (supplementEditMode === 'edit' && editingSupplementCode) {
        const updateData: WorkflowSupplementConfigUpdate = {
          quantity_per_request: supplementForm.quantity_per_request,
          is_required: supplementForm.is_required,
          is_active: supplementForm.is_active,
        }
        await updateWorkflowSupplementMutation.mutateAsync({
          workflowCode,
          supplementCode: editingSupplementCode,
          data: updateData,
        })
      }
      resetSupplementForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleDeleteSupplement = async () => {
    if (!supplementToDelete) return
    try {
      await removeWorkflowSupplementMutation.mutateAsync({
        workflowCode,
        supplementCode: supplementToDelete.supplement_code,
      })
      setIsDeleteSupplementDialogOpen(false)
      setSupplementToDelete(null)
    } catch {
      // Error handled by mutation
    }
  }

  // Batch supplement handlers
  const addToPendingSupplements = () => {
    if (!supplementForm.supplement_code) return

    const selectedSupplement = allSupplements?.find(s => s.code === supplementForm.supplement_code)
    if (!selectedSupplement) return

    // Check if already in pending list
    if (pendingSupplements.find(p => p.supplement_code === supplementForm.supplement_code)) return

    setPendingSupplements([
      ...pendingSupplements,
      {
        supplement_code: selectedSupplement.code,
        supplement_name: selectedSupplement.name_es,
        supplement_amount: selectedSupplement.amount,
        quantity_per_request: supplementForm.quantity_per_request ?? 1,
        is_required: supplementForm.is_required ?? false,
      }
    ])

    // Reset form but keep in create mode
    setSupplementForm({
      supplement_code: '',
      quantity_per_request: 1,
      is_required: false,
      is_active: true,
    })
  }

  const removeFromPendingSupplements = (code: string) => {
    setPendingSupplements(pendingSupplements.filter(p => p.supplement_code !== code))
  }

  const pendingSupplementsTotal = pendingSupplements.reduce(
    (sum, p) => sum + (p.supplement_amount * p.quantity_per_request),
    0
  )

  const handleSaveBatchSupplements = async () => {
    if (pendingSupplements.length === 0) return

    setIsSavingBatch(true)
    try {
      // Save all pending supplements sequentially
      for (const pending of pendingSupplements) {
        await addWorkflowSupplementMutation.mutateAsync({
          workflowCode,
          data: {
            supplement_code: pending.supplement_code,
            quantity_per_request: pending.quantity_per_request,
            is_required: pending.is_required,
            is_active: true,
          },
        })
      }
      // Clear pending and reset form
      setPendingSupplements([])
      resetSupplementForm()
    } catch {
      // Error handled by mutation
    } finally {
      setIsSavingBatch(false)
    }
  }

  const cancelBatchSupplements = () => {
    setPendingSupplements([])
    resetSupplementForm()
  }

  // Get supplements available for adding (not already configured and not in pending)
  const pendingSupplementCodes = pendingSupplements.map(p => p.supplement_code)

  const isSupplementSaving = addWorkflowSupplementMutation.isPending || updateWorkflowSupplementMutation.isPending

  // Get available supplements (not already configured for this workflow and not in pending)
  const configuredSupplementCodes = workflowSupplements?.map((ws) => ws.supplement_code) || []
  const availableSupplements = allSupplements?.filter((s) =>
    !configuredSupplementCodes.includes(s.code) && !pendingSupplementCodes.includes(s.code)
  ) || []

  // Calculate cost totals (single tariff + supplements)
  const costTotals = useMemo(() => {
    const activeTariff = allTariffs?.find(t => t.is_active)
    const tariffAmount = activeTariff?.amount || 0
    const tariffType = activeTariff?.tariff_type || 'FIXED'

    const supplementsTotal = workflowSupplements?.reduce((sum, s) => {
      if (!s.is_active) return sum
      return sum + ((s.supplement_amount || 0) * s.quantity_per_request)
    }, 0) || 0

    return {
      tariff: tariffAmount,
      tariffType,
      supplements: supplementsTotal,
      total: tariffAmount + supplementsTotal,
    }
  }, [allTariffs, workflowSupplements])

  // Handlers - Documents
  const resetDocForm = () => {
    setDocForm({
      document_code: '',
      document_name_es: '',
      condition_type: 'always',
      is_required: true,
      display_order: 0,
      instructions_es: '',
      extraction_schema_key: '',
      is_active: true,
    })
    setDocumentEditMode('none')
    setEditingDocumentCode(null)
  }

  const startCreateDocument = () => {
    resetDocForm()
    setDocumentEditMode('create')
  }

  const startEditDocument = (doc: DocumentRequirement) => {
    setDocForm({
      document_code: doc.document_code,
      document_name_es: doc.document_name_es,
      condition_type: doc.condition_type as DocumentConditionType,
      is_required: doc.is_required,
      display_order: doc.display_order,
      instructions_es: doc.instructions_es || '',
      extraction_schema_key: doc.extraction_schema_key || '',
      is_active: doc.is_active,
    })
    setEditingDocumentCode(doc.document_code)
    setDocumentEditMode('edit')
  }

  const handleSaveDocument = async () => {
    try {
      if (documentEditMode === 'create') {
        await addDocumentMutation.mutateAsync({
          workflowCode,
          data: { ...docForm, display_order: documents?.length || 0 },
        })
      } else if (documentEditMode === 'edit' && editingDocumentCode) {
        const updateData: DocumentRequirementUpdate = {
          document_name_es: docForm.document_name_es,
          condition_type: docForm.condition_type,
          is_required: docForm.is_required,
          instructions_es: docForm.instructions_es,
          extraction_schema_key: docForm.extraction_schema_key,
          is_active: docForm.is_active,
        }
        await updateDocumentMutation.mutateAsync({
          workflowCode,
          documentCode: editingDocumentCode,
          data: updateData,
        })
      }
      resetDocForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleRemoveDocument = async () => {
    if (!documentToDelete) return
    try {
      await removeDocumentMutation.mutateAsync({
        workflowCode,
        documentCode: documentToDelete.document_code,
      })
      setIsDeleteDocDialogOpen(false)
      setDocumentToDelete(null)
    } catch {
      // Error handled by mutation
    }
  }

  const handleMoveDocument = async (doc: DocumentRequirement, direction: 'up' | 'down') => {
    const sortedDocs = [...(documents || [])].sort((a, b) => a.display_order - b.display_order)
    const currentIndex = sortedDocs.findIndex((d) => d.id === doc.id)
    if (direction === 'up' && currentIndex <= 0) return
    if (direction === 'down' && currentIndex >= sortedDocs.length - 1) return

    const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
    const newOrder: DocumentReorderItem[] = sortedDocs.map((d, i) => {
      if (i === currentIndex) return { document_code: d.document_code, display_order: targetIndex }
      if (i === targetIndex) return { document_code: d.document_code, display_order: currentIndex }
      return { document_code: d.document_code, display_order: i }
    })

    await reorderDocumentsMutation.mutateAsync({ workflowCode, order: newOrder })
  }

  // Batch document handlers
  const addToPendingDocuments = () => {
    if (!docForm.document_code || !docForm.document_name_es) return

    // Check if already in pending list or already exists
    if (pendingDocuments.find(p => p.document_code === docForm.document_code)) return
    if (documents?.find(d => d.document_code === docForm.document_code)) return

    setPendingDocuments([
      ...pendingDocuments,
      {
        document_code: docForm.document_code,
        document_name_es: docForm.document_name_es,
        condition_type: docForm.condition_type ?? 'always',
        is_required: docForm.is_required ?? true,
        instructions_es: docForm.instructions_es || '',
        extraction_schema_key: docForm.extraction_schema_key || '',
      }
    ])

    // Reset form but keep in create mode
    setDocForm({
      document_code: '',
      document_name_es: '',
      condition_type: 'always',
      is_required: true,
      display_order: 0,
      instructions_es: '',
      extraction_schema_key: '',
      is_active: true,
    })
  }

  const removeFromPendingDocuments = (code: string) => {
    setPendingDocuments(pendingDocuments.filter(p => p.document_code !== code))
  }

  const handleSaveBatchDocuments = async () => {
    if (pendingDocuments.length === 0) return

    setIsSavingDocBatch(true)
    try {
      const baseOrder = documents?.length || 0
      // Save all pending documents sequentially
      for (let i = 0; i < pendingDocuments.length; i++) {
        const pending = pendingDocuments[i]
        await addDocumentMutation.mutateAsync({
          workflowCode,
          data: {
            document_code: pending.document_code,
            document_name_es: pending.document_name_es,
            condition_type: pending.condition_type as DocumentConditionType,
            is_required: pending.is_required,
            instructions_es: pending.instructions_es,
            extraction_schema_key: pending.extraction_schema_key || null,
            display_order: baseOrder + i,
            is_active: true,
          },
        })
      }
      // Clear pending and reset form
      setPendingDocuments([])
      resetDocForm()
    } catch {
      // Error handled by mutation
    } finally {
      setIsSavingDocBatch(false)
    }
  }

  const cancelBatchDocuments = () => {
    setPendingDocuments([])
    resetDocForm()
  }

  const isDocumentSaving = addDocumentMutation.isPending || updateDocumentMutation.isPending

  // Helpers
  const formatCurrency = (amount: number, currency = 'XAF') => {
    return new Intl.NumberFormat('es-GQ', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
    }).format(amount)
  }

  const getTariffTypeBadge = (type: string) => {
    switch (type) {
      case 'FIXED': return <Badge variant="default">{tTariffs('typeFixed')}</Badge>
      case 'PERCENTAGE': return <Badge variant="secondary">{tTariffs('typePercentage')}</Badge>
      case 'NOTA_INGRESO': return <Badge variant="outline">{tTariffs('typeNotaIngreso')}</Badge>
      default: return <Badge variant="outline">{type}</Badge>
    }
  }

  const getConditionBadge = (type: string) => {
    switch (type) {
      case 'always': return <Badge variant="default">{tDocs('conditionAlways')}</Badge>
      case 'if_solicitud_type': return <Badge variant="secondary">{tDocs('conditionSolicitud')}</Badge>
      case 'if_form_field': return <Badge variant="outline">{tDocs('conditionFormField')}</Badge>
      default: return <Badge variant="outline">{type}</Badge>
    }
  }

  const sortedDocuments = [...(documents || [])].sort((a, b) => a.display_order - b.display_order)

  // Predefined workflow check - predefined workflows have tariffs/documents defined in Python code
  // is_generic = false means it's a predefined workflow from Python
  // is_generic = true means it's a dynamic workflow created via admin UI
  const isPredefined = workflow && workflow.is_generic === false

  // Loading state
  if (loadingWorkflow) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (workflowError || !workflow) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => router.push(`/${locale}/dashboard/admin/service-requests/workflows`)} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          {tCommon('back')}
        </Button>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>{workflowError instanceof Error ? workflowError.message : 'Workflow not found'}</span>
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
      {/* Navigation Header */}
      <div className="flex items-center justify-between border-b pb-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push(`/${locale}/dashboard/admin/service-requests/workflows`)}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Lista
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => prevWorkflowCode && router.push(`/${locale}/dashboard/admin/service-requests/workflows/${prevWorkflowCode}?tab=${activeTab}`)}
            disabled={!prevWorkflowCode}
          >
            <ChevronLeft className="h-4 w-4" />
            Anterior
          </Button>
          <span className="text-sm text-muted-foreground px-2 min-w-[80px] text-center">
            {workflowPosition}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => nextWorkflowCode && router.push(`/${locale}/dashboard/admin/service-requests/workflows/${nextWorkflowCode}?tab=${activeTab}`)}
            disabled={!nextWorkflowCode}
          >
            Siguiente
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Workflow Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight">{tw(workflowNameKey(workflow.code), workflow.name_es)}</h1>
            {isPredefined && (
              <Badge variant="outline" className="gap-1 bg-blue-50 text-blue-700 border-blue-200">
                <GitBranch className="h-3 w-3" />
                Predefinido
              </Badge>
            )}
            {workflow.is_active ? (
              <Badge variant="default" className="gap-1">
                <CheckCircle className="h-3 w-3" />
                Activo
              </Badge>
            ) : (
              <Badge variant="secondary" className="gap-1">
                <XCircle className="h-3 w-3" />
                Inactivo
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground">
            <code className="bg-muted px-2 py-0.5 rounded">{workflow.code}</code>
            {" - "}{workflow.entity_code} · {workflow.category}
          </p>
        </div>
        {!isEditingPage && !isPredefined && (
          <Button onClick={() => setIsEditingPage(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            Editar
          </Button>
        )}
        {!isEditingPage && isPredefined && (
          <div className="text-sm text-muted-foreground bg-blue-50 px-3 py-2 rounded-md border border-blue-200">
            Workflow predefinido (solo lectura)
          </div>
        )}
      </div>

      {/* Summary Dashboard (View Mode) */}
      {!isEditingPage && (
        <div className="space-y-6">
          {/* Info + Tariffs Row */}
          <div className="grid gap-6 md:grid-cols-2">
            {/* Info Summary */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <GitBranch className="h-5 w-5" />
                  Informacion
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="text-muted-foreground">Tipo:</div>
                  <div className="font-medium capitalize">{workflow.workflow_type.replace('_', ' ')}</div>
                  <div className="text-muted-foreground">Requiere Cita:</div>
                  <div className="font-medium">{workflow.requires_appointment ? 'Si' : 'No'}</div>
                  <div className="text-muted-foreground">Requiere Validacion:</div>
                  <div className="font-medium">{workflow.requires_agent_validation ? 'Si' : 'No'}</div>
                  <div className="text-muted-foreground">SLA:</div>
                  <div className="font-medium">{workflow.sla_hours}h</div>
                </div>
                {workflow.description_es && (
                  <p className="text-sm text-muted-foreground border-t pt-3">
                    {workflow.description_es}
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Tariffs & Supplements Summary (merged) */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <DollarSign className="h-5 w-5" />
                  Tarifas y Suplementos
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Tarifa Base */}
                <div className="flex items-center justify-between py-2 border-b">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Tarifa Base</span>
                    {allTariffs?.find(t => t.is_active) && (
                      getTariffTypeBadge(allTariffs.find(t => t.is_active)!.tariff_type)
                    )}
                  </div>
                  <span className="font-mono font-semibold text-lg">
                    {costTotals.tariff ? formatCurrency(costTotals.tariff) : '-'}
                  </span>
                </div>

                {/* Supplements list */}
                {(workflowSupplements?.filter(s => s.is_active).length || 0) > 0 ? (
                  <div className="space-y-1">
                    <span className="text-sm text-muted-foreground font-medium">Suplementos</span>
                    {workflowSupplements?.filter(s => s.is_active).map((s) => (
                      <div key={s.id} className="flex items-center justify-between py-1.5 text-sm">
                        <div className="flex items-center gap-2">
                          <span>{s.supplement_name}</span>
                          {s.is_required && <Badge variant="default" className="text-xs">Oblig.</Badge>}
                        </div>
                        <span className="font-mono">
                          {s.supplement_amount?.toLocaleString()} × {s.quantity_per_request} = {((s.supplement_amount || 0) * s.quantity_per_request).toLocaleString()} XAF
                        </span>
                      </div>
                    ))}
                    {costTotals.supplements > 0 && (
                      <div className="flex justify-end pt-1 text-sm text-muted-foreground">
                        Subtotal: {costTotals.supplements.toLocaleString()} XAF
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground py-1">Sin suplementos configurados</div>
                )}

                {/* Total */}
                <div className="flex items-center justify-between pt-3 border-t-2 border-primary/20">
                  <span className="font-semibold text-lg">COSTE TOTAL</span>
                  <span className="font-mono font-bold text-xl text-primary">
                    {costTotals.total ? formatCurrency(costTotals.total) : '-'}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Documents Summary - Collapsible 2-column */}
          <Card>
            <CardHeader
              className="pb-3 cursor-pointer select-none"
              onClick={() => setDocsExpanded(prev => !prev)}
            >
              <CardTitle className="flex items-center gap-2 text-lg">
                <FileCheck className="h-5 w-5" />
                Documentos Requeridos ({sortedDocuments?.length || 0})
                <ChevronDown
                  className={`h-4 w-4 ml-auto transition-transform duration-200 ${docsExpanded ? 'rotate-180' : ''}`}
                />
              </CardTitle>
            </CardHeader>
            {docsExpanded && (
              <CardContent>
                {sortedDocuments.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2">
                    {sortedDocuments.map((doc, index) => (
                      <div key={doc.id} className="flex items-center gap-3 py-1">
                        <span className="text-muted-foreground w-6 shrink-0">{index + 1}.</span>
                        <span className="flex-1 text-sm">{doc.document_name_es}</span>
                        {doc.is_required ? (
                          <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
                        ) : (
                          <span className="text-xs text-muted-foreground shrink-0">Opcional</span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-4">Sin documentos requeridos</p>
                )}
              </CardContent>
            )}
          </Card>

          {/* Appointments Summary */}
          {workflow.requires_appointment && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <CalendarClock className="h-5 w-5" />
                  Citas
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div className="p-3 bg-muted/30 rounded-lg">
                    <div className="text-2xl font-bold">{slotConfigs?.length || 0}</div>
                    <div className="text-sm text-muted-foreground">Horarios</div>
                  </div>
                  <div className="p-3 bg-muted/30 rounded-lg">
                    <div className="text-2xl font-bold">{blockedDates?.length || 0}</div>
                    <div className="text-sm text-muted-foreground">Fechas Bloqueadas</div>
                  </div>
                  <div className="p-3 bg-muted/30 rounded-lg">
                    <div className="text-2xl font-bold">{delayRules?.length || 0}</div>
                    <div className="text-sm text-muted-foreground">Reglas de Espera</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Tabs (Edit Mode) */}
      {isEditingPage && (
      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        <div className="flex items-center justify-between">
          <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
            <TabsTrigger value="info" className="gap-2">
              <GitBranch className="h-4 w-4" />
              <span className="hidden sm:inline">Informacion</span>
            </TabsTrigger>
            <TabsTrigger value="tariffs" className="gap-2">
              <DollarSign className="h-4 w-4" />
              <span className="hidden sm:inline">Tarifas y Suplementos</span>
            </TabsTrigger>
            <TabsTrigger value="documents" className="gap-2">
              <FileCheck className="h-4 w-4" />
              <span className="hidden sm:inline">Documentos</span>
            </TabsTrigger>
            <TabsTrigger value="appointments" className="gap-2">
              <CalendarClock className="h-4 w-4" />
              <span className="hidden sm:inline">Citas</span>
            </TabsTrigger>
          </TabsList>
          <Button variant="secondary" className="bg-primary/10 hover:bg-primary/20 text-primary" onClick={() => setIsEditingPage(false)}>
            <Eye className="mr-2 h-4 w-4" />
            Volver a Vista
          </Button>
        </div>

        {/* Info Tab */}
        <TabsContent value="info" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{t('workflowDetails')}</CardTitle>
                <CardDescription>{t('workflowDetailsDescription')}</CardDescription>
              </div>
              {!isEditing ? (
                <Button variant="outline" onClick={() => setIsEditing(true)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  {tCommon('edit')}
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setIsEditing(false)}>
                    {tCommon('cancel')}
                  </Button>
                  <Button onClick={handleSaveWorkflow} disabled={updateWorkflowMutation.isPending}>
                    {updateWorkflowMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    <Save className="mr-2 h-4 w-4" />
                    {tCommon('save')}
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Identity — always read-only */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>{t('code')}</Label>
                  <Input value={workflow.code} disabled className="bg-muted font-mono" />
                </div>
                <div className="space-y-2">
                  <Label>{t('entityCode')}</Label>
                  <Input value={workflow.entity_code} disabled className="bg-muted" />
                </div>
                <div className="space-y-2">
                  <Label>{t('category')}</Label>
                  <Input value={workflow.category} disabled className="bg-muted" />
                </div>
              </div>

              {/* Editable fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>{t('nameEs')}</Label>
                  {isEditing ? (
                    <Input
                      value={editForm.name_es || ''}
                      onChange={(e) => setEditForm({ ...editForm, name_es: e.target.value })}
                    />
                  ) : (
                    <Input value={workflow.name_es} disabled className="bg-muted" />
                  )}
                </div>
                <div className="space-y-2">
                  <Label>{t('type')}</Label>
                  {isEditing ? (
                    <Select
                      value={editForm.workflow_type || workflow.workflow_type}
                      onValueChange={(v) => setEditForm({ ...editForm, workflow_type: v as WorkflowType })}
                    >
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {WORKFLOW_TYPES.map((wt) => (
                          <SelectItem key={wt.value} value={wt.value}>{wt.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input value={workflow.workflow_type} disabled className="bg-muted" />
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t('descriptionEs')}</Label>
                {isEditing ? (
                  <Textarea
                    value={editForm.description_es || ''}
                    onChange={(e) => setEditForm({ ...editForm, description_es: e.target.value })}
                    rows={3}
                  />
                ) : (
                  <Textarea value={workflow.description_es || '-'} disabled className="bg-muted" rows={3} />
                )}
              </div>

              {isEditing && (
                <>
                  {/* Switches row */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <Label htmlFor="edit_requires_agent">Requiere validación de agente</Label>
                        <p className="text-xs text-muted-foreground">Un agente debe revisar la solicitud</p>
                      </div>
                      <Switch
                        id="edit_requires_agent"
                        checked={editForm.requires_agent_validation ?? workflow.requires_agent_validation}
                        onCheckedChange={(checked) => setEditForm({ ...editForm, requires_agent_validation: checked })}
                      />
                    </div>
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <Label htmlFor="edit_requires_appointment">Requiere cita</Label>
                        <p className="text-xs text-muted-foreground">El ciudadano debe agendar cita</p>
                      </div>
                      <Switch
                        id="edit_requires_appointment"
                        checked={editForm.requires_appointment ?? workflow.requires_appointment}
                        onCheckedChange={(checked) => setEditForm({ ...editForm, requires_appointment: checked })}
                      />
                    </div>
                  </div>

                  {/* Numeric fields */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="space-y-2">
                      <Label>SLA (horas)</Label>
                      <Input
                        type="number"
                        min={1}
                        max={720}
                        value={editForm.sla_hours ?? workflow.sla_hours}
                        onChange={(e) => setEditForm({ ...editForm, sla_hours: parseInt(e.target.value) || 48 })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Orden visualización</Label>
                      <Input
                        type="number"
                        min={0}
                        value={editForm.display_order ?? workflow.display_order}
                        onChange={(e) => setEditForm({ ...editForm, display_order: parseInt(e.target.value) || 0 })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Días máx. procesamiento</Label>
                      <Input
                        type="number"
                        min={1}
                        max={365}
                        value={editForm.max_processing_days ?? workflow.max_processing_days ?? ''}
                        onChange={(e) => setEditForm({ ...editForm, max_processing_days: e.target.value ? parseInt(e.target.value) : null })}
                        placeholder="Opcional"
                      />
                    </div>
                    {(editForm.requires_appointment ?? workflow.requires_appointment) && (
                      <div className="space-y-2">
                        <Label>Días anticip. cita</Label>
                        <Input
                          type="number"
                          min={0}
                          max={90}
                          value={editForm.appointment_delay_days ?? workflow.appointment_delay_days ?? ''}
                          onChange={(e) => setEditForm({ ...editForm, appointment_delay_days: e.target.value ? parseInt(e.target.value) : null })}
                          placeholder="Opcional"
                        />
                      </div>
                    )}
                  </div>

                  {/* Parent workflow + is_parent */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Workflow Padre</Label>
                      <Select
                        value={editForm.parent_workflow_code ?? workflow.parent_workflow_code ?? '_none'}
                        onValueChange={(v) => setEditForm({ ...editForm, parent_workflow_code: v === '_none' ? null : v })}
                        disabled={editForm.is_parent ?? workflow.is_parent}
                      >
                        <SelectTrigger><SelectValue placeholder="Ninguno" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="_none">Ninguno</SelectItem>
                          {allWorkflows?.filter(w => w.is_parent && w.code !== workflow.code).map((wf) => (
                            <SelectItem key={wf.code} value={wf.code}>{tw(workflowNameKey(wf.code), wf.name_es)}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <Label htmlFor="edit_is_parent">Es workflow padre</Label>
                        <p className="text-xs text-muted-foreground">Actúa como grupo para otros workflows</p>
                      </div>
                      <Switch
                        id="edit_is_parent"
                        checked={editForm.is_parent ?? workflow.is_parent ?? false}
                        onCheckedChange={(checked) => {
                          setEditForm({ ...editForm, is_parent: checked, ...(checked ? { parent_workflow_code: null } : {}) })
                        }}
                        disabled={!!(editForm.parent_workflow_code ?? workflow.parent_workflow_code)}
                      />
                    </div>
                  </div>

                  {/* Tags */}
                  <div className="space-y-2">
                    <Label>Etiquetas</Label>
                    <div className="flex gap-2">
                      <Input
                        value={newTag}
                        onChange={(e) => setNewTag(e.target.value)}
                        placeholder="Añadir etiqueta..."
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault()
                            const tag = newTag.trim().toLowerCase()
                            if (tag && !(editForm.tags ?? workflow.tags ?? []).includes(tag)) {
                              setEditForm({ ...editForm, tags: [...(editForm.tags ?? workflow.tags ?? []), tag] })
                              setNewTag('')
                            }
                          }
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={() => {
                          const tag = newTag.trim().toLowerCase()
                          if (tag && !(editForm.tags ?? workflow.tags ?? []).includes(tag)) {
                            setEditForm({ ...editForm, tags: [...(editForm.tags ?? workflow.tags ?? []), tag] })
                            setNewTag('')
                          }
                        }}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    {(editForm.tags ?? workflow.tags ?? []).length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {(editForm.tags ?? workflow.tags ?? []).map((tag) => (
                          <Badge key={tag} variant="secondary" className="gap-1">
                            <Tag className="h-3 w-3" />
                            {tag}
                            <button
                              type="button"
                              onClick={() => setEditForm({
                                ...editForm,
                                tags: (editForm.tags ?? workflow.tags ?? []).filter((t) => t !== tag),
                              })}
                              className="ml-1 hover:text-destructive"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Active toggle */}
                  <div className="flex items-center justify-between pt-4 border-t">
                    <Label htmlFor="is_active">{t('isActive')}</Label>
                    <Switch
                      id="is_active"
                      checked={editForm.is_active}
                      onCheckedChange={(checked) => setEditForm({ ...editForm, is_active: checked })}
                    />
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tariffs Tab */}
        <TabsContent value="tariffs" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5" />
                  {tTariffs('title')}
                </CardTitle>
                <CardDescription>
                  {tTariffs('total', { count: allTariffs?.length || 0 })}
                </CardDescription>
              </div>
              {tariffEditMode === 'none' && (
                <Button onClick={startCreateTariff}>
                  <Plus className="mr-2 h-4 w-4" />
                  {tTariffs('create')}
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Cost Summary */}
              {(allTariffs?.length || workflowSupplements?.length) && tariffEditMode === 'none' ? (
                <div className="border rounded-lg p-4 bg-muted/30 mb-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-3 text-sm">
                        <span className="text-muted-foreground">Tarifa Base:</span>
                        <span className="font-mono font-medium">{costTotals.tariff ? formatCurrency(costTotals.tariff) : '-'}</span>
                        {allTariffs?.find(t => t.is_active) && getTariffTypeBadge(allTariffs.find(t => t.is_active)!.tariff_type)}
                      </div>
                      {costTotals.supplements > 0 && (
                        <div className="flex items-center gap-3 text-sm">
                          <span className="text-muted-foreground">Suplementos:</span>
                          <span className="font-mono font-medium">{formatCurrency(costTotals.supplements)}</span>
                          <span className="text-muted-foreground text-xs">({workflowSupplements?.filter(s => s.is_active).length || 0} configurados)</span>
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">Coste Total</div>
                      <div className="font-mono font-bold text-xl text-primary">
                        {costTotals.total ? formatCurrency(costTotals.total) : '-'}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Inline Create/Edit Form */}
              {tariffEditMode !== 'none' && (
                <Card className="border-primary">
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg">
                      {tariffEditMode === 'create' ? tTariffs('create') : tTariffs('edit')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div className="space-y-2">
                        <Label>{tTariffs('solicitudType')}</Label>
                        <Select
                          value={tariffForm.solicitud_type}
                          onValueChange={(v) => setTariffForm({ ...tariffForm, solicitud_type: v })}
                        >
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="expedicion">Expedicion</SelectItem>
                            <SelectItem value="renovacion">Renovacion</SelectItem>
                            <SelectItem value="duplicado">Duplicado</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>{tTariffs('tariffType')}</Label>
                        <Select
                          value={tariffForm.tariff_type}
                          onValueChange={(v) => setTariffForm({ ...tariffForm, tariff_type: v as TariffType })}
                        >
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {TARIFF_TYPES.map((tt) => (
                              <SelectItem key={tt.value} value={tt.value}>{tt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>{tTariffs('amount')} (XAF)</Label>
                        <Input
                          type="number"
                          value={tariffForm.amount}
                          onChange={(e) => setTariffForm({ ...tariffForm, amount: parseFloat(e.target.value) || 0 })}
                          min={0}
                        />
                      </div>
                      {tariffForm.tariff_type === 'PERCENTAGE' && (
                        <div className="space-y-2">
                          <Label>{tTariffs('percentage')} (%)</Label>
                          <Input
                            type="number"
                            value={tariffForm.percentage_rate || ''}
                            onChange={(e) => setTariffForm({ ...tariffForm, percentage_rate: parseFloat(e.target.value) || null })}
                            min={0}
                            max={100}
                            step={0.01}
                          />
                        </div>
                      )}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label>{tTariffs('effectiveFrom')}</Label>
                        <Input
                          type="date"
                          value={tariffForm.effective_from}
                          onChange={(e) => setTariffForm({ ...tariffForm, effective_from: e.target.value })}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{tTariffs('effectiveTo')}</Label>
                        <Input
                          type="date"
                          value={tariffForm.effective_to || ''}
                          onChange={(e) => setTariffForm({ ...tariffForm, effective_to: e.target.value || null })}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{tTariffs('legalReference')}</Label>
                        <Input
                          value={tariffForm.legal_reference || ''}
                          onChange={(e) => setTariffForm({ ...tariffForm, legal_reference: e.target.value })}
                          placeholder="Ley XX/2024, Art. YY"
                        />
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-2">
                      <div className="flex items-center gap-2">
                        <Switch
                          id="tariff_is_active"
                          checked={tariffForm.is_active}
                          onCheckedChange={(checked) => setTariffForm({ ...tariffForm, is_active: checked })}
                        />
                        <Label htmlFor="tariff_is_active">{tTariffs('isActive')}</Label>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" onClick={resetTariffForm} disabled={isTariffSaving}>
                          <X className="mr-2 h-4 w-4" />
                          {tCommon('cancel')}
                        </Button>
                        <Button onClick={handleSaveTariff} disabled={!tariffForm.amount || isTariffSaving}>
                          {isTariffSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                          <Save className="mr-2 h-4 w-4" />
                          {tCommon('save')}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Tariffs Table */}
              {loadingTariffs ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (allTariffs?.length || 0) === 0 && tariffEditMode === 'none' ? (
                <div className="text-center text-muted-foreground py-8">
                  <DollarSign className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">{tTariffs('noTariffsFound')}</p>
                  <p className="text-sm mt-1">Use el boton &quot;Crear Tarifa&quot; de arriba para agregar una nueva tarifa</p>
                </div>
              ) : (allTariffs?.length || 0) > 0 && (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{tTariffs('solicitudType')}</TableHead>
                        <TableHead>{tTariffs('type')}</TableHead>
                        <TableHead className="text-right">{tTariffs('amount')}</TableHead>
                        <TableHead>{tTariffs('legalReference')}</TableHead>
                        <TableHead>{tTariffs('validity')}</TableHead>
                        <TableHead className="text-center">{tTariffs('status')}</TableHead>
                        <TableHead className="text-right">{tTariffs('actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {allTariffs?.map((tariff) => (
                        <TableRow key={tariff.id} className={editingTariffId === tariff.id ? 'bg-muted/50' : ''}>
                          <TableCell><Badge variant="outline" className="capitalize">{tariff.solicitud_type}</Badge></TableCell>
                          <TableCell>{getTariffTypeBadge(tariff.tariff_type)}</TableCell>
                          <TableCell className="text-right font-mono">
                            {tariff.tariff_type === 'PERCENTAGE' && tariff.percentage_rate
                              ? `${tariff.percentage_rate}%`
                              : formatCurrency(tariff.amount, tariff.currency)}
                          </TableCell>
                          <TableCell>
                            {tariff.legal_reference ? (
                              <span className="text-sm">{tariff.legal_reference}</span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="text-sm">
                              <div>{tariff.effective_from}</div>
                              {tariff.effective_to && <div className="text-muted-foreground">hasta {tariff.effective_to}</div>}
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            {tariff.is_active ? (
                              <CheckCircle className="h-5 w-5 text-green-500 mx-auto" />
                            ) : (
                              <XCircle className="h-5 w-5 text-red-500 mx-auto" />
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => startEditTariff(tariff)}
                                disabled={tariffEditMode !== 'none'}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => { setTariffToDelete(tariff); setIsDeleteTariffDialogOpen(true) }}
                                className="text-destructive hover:text-destructive"
                                disabled={tariffEditMode !== 'none'}
                              >
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

          {/* Delete Tariff Confirmation Dialog */}
          <AlertDialog open={isDeleteTariffDialogOpen} onOpenChange={setIsDeleteTariffDialogOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{tTariffs('deleteConfirmTitle')}</AlertDialogTitle>
                <AlertDialogDescription>
                  {tTariffs('deleteConfirmDescription', { workflow: tariffToDelete?.workflow_code })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDeleteTariff}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {deleteTariffMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {tCommon('delete')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {/* Supplements Section */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Boxes className="h-5 w-5" />
                  Suplementos
                </CardTitle>
                <CardDescription>
                  {workflowSupplements?.length || 0} suplementos configurados
                </CardDescription>
              </div>
              {supplementEditMode === 'none' && availableSupplements.length > 0 && (
                <Button onClick={startCreateSupplement}>
                  <Plus className="mr-2 h-4 w-4" />
                  Agregar Suplemento
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Inline Create/Edit Form */}
              {supplementEditMode !== 'none' && (
                <Card className="border-primary">
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg">
                      {supplementEditMode === 'create' ? 'Agregar Suplementos' : 'Editar Suplemento'}
                    </CardTitle>
                    {supplementEditMode === 'create' && (
                      <CardDescription>
                        Puede agregar varios suplementos antes de guardar
                      </CardDescription>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Input row for adding supplements */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                      {supplementEditMode === 'create' && (
                        <div className="space-y-2">
                          <Label>Suplemento</Label>
                          <Select
                            value={supplementForm.supplement_code}
                            onValueChange={(v) => setSupplementForm({ ...supplementForm, supplement_code: v })}
                          >
                            <SelectTrigger><SelectValue placeholder="Seleccionar suplemento" /></SelectTrigger>
                            <SelectContent>
                              {availableSupplements.map((s) => (
                                <SelectItem key={s.code} value={s.code}>
                                  {s.name_es} ({s.amount.toLocaleString()} XAF)
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                      {supplementEditMode === 'edit' && (
                        <div className="space-y-2">
                          <Label>Suplemento</Label>
                          <Input value={editingSupplementCode || ''} disabled className="bg-muted" />
                        </div>
                      )}
                      <div className="space-y-2">
                        <Label>Cantidad</Label>
                        <Input
                          type="number"
                          value={supplementForm.quantity_per_request}
                          onChange={(e) => setSupplementForm({ ...supplementForm, quantity_per_request: parseInt(e.target.value) || 1 })}
                          min={1}
                        />
                      </div>
                      <div className="flex items-center gap-2 pb-2">
                        <Switch
                          id="supplement_is_required"
                          checked={supplementForm.is_required}
                          onCheckedChange={(checked) => setSupplementForm({ ...supplementForm, is_required: checked })}
                        />
                        <Label htmlFor="supplement_is_required">Obligatorio</Label>
                      </div>
                      {supplementEditMode === 'create' ? (
                        <Button
                          variant="secondary"
                          onClick={addToPendingSupplements}
                          disabled={!supplementForm.supplement_code}
                        >
                          <Plus className="mr-2 h-4 w-4" />
                          Añadir
                        </Button>
                      ) : (
                        <div className="flex items-center gap-2 pb-2">
                          <Switch
                            id="supplement_is_active"
                            checked={supplementForm.is_active}
                            onCheckedChange={(checked) => setSupplementForm({ ...supplementForm, is_active: checked })}
                          />
                          <Label htmlFor="supplement_is_active">Activo</Label>
                        </div>
                      )}
                    </div>

                    {/* Pending supplements list (batch mode) */}
                    {supplementEditMode === 'create' && pendingSupplements.length > 0 && (
                      <div className="border rounded-md mt-4">
                        <div className="bg-muted/50 px-4 py-2 border-b">
                          <span className="text-sm font-medium">Suplementos pendientes ({pendingSupplements.length})</span>
                        </div>
                        <Table>
                          <TableBody>
                            {pendingSupplements.map((pending) => (
                              <TableRow key={pending.supplement_code}>
                                <TableCell className="font-medium">{pending.supplement_name}</TableCell>
                                <TableCell className="text-right font-mono text-sm">
                                  {pending.supplement_amount.toLocaleString()} XAF × {pending.quantity_per_request}
                                </TableCell>
                                <TableCell className="text-right font-mono font-semibold">
                                  = {(pending.supplement_amount * pending.quantity_per_request).toLocaleString()} XAF
                                </TableCell>
                                <TableCell className="text-center w-[80px]">
                                  {pending.is_required ? (
                                    <Badge variant="default" className="text-xs">Oblig.</Badge>
                                  ) : (
                                    <Badge variant="outline" className="text-xs">Opc.</Badge>
                                  )}
                                </TableCell>
                                <TableCell className="text-right w-[50px]">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => removeFromPendingSupplements(pending.supplement_code)}
                                    className="h-8 w-8 text-destructive hover:text-destructive"
                                  >
                                    <X className="h-4 w-4" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                            <TableRow className="bg-muted/30 font-semibold">
                              <TableCell colSpan={2} className="text-right">Total suplementos:</TableCell>
                              <TableCell className="text-right font-mono">
                                {pendingSupplementsTotal.toLocaleString()} XAF
                              </TableCell>
                              <TableCell colSpan={2}></TableCell>
                            </TableRow>
                          </TableBody>
                        </Table>
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex justify-end gap-2 pt-2 border-t">
                      {supplementEditMode === 'create' ? (
                        <>
                          <Button
                            variant="outline"
                            onClick={cancelBatchSupplements}
                            disabled={isSavingBatch}
                          >
                            <X className="mr-2 h-4 w-4" />
                            Cancelar
                          </Button>
                          <Button
                            onClick={handleSaveBatchSupplements}
                            disabled={pendingSupplements.length === 0 || isSavingBatch}
                          >
                            {isSavingBatch && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            <Save className="mr-2 h-4 w-4" />
                            Guardar Todo ({pendingSupplements.length})
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button variant="outline" onClick={resetSupplementForm} disabled={isSupplementSaving}>
                            <X className="mr-2 h-4 w-4" />
                            {tCommon('cancel')}
                          </Button>
                          <Button onClick={handleSaveSupplement} disabled={!supplementForm.supplement_code || isSupplementSaving}>
                            {isSupplementSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            <Save className="mr-2 h-4 w-4" />
                            {tCommon('save')}
                          </Button>
                        </>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Supplements Table */}
              {loadingSupplements ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (workflowSupplements?.length || 0) === 0 && supplementEditMode === 'none' ? (
                <div className="text-center text-muted-foreground py-8">
                  <Boxes className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">Sin suplementos configurados</p>
                  <p className="text-sm mt-1">
                    {availableSupplements.length > 0
                      ? 'Use el boton "Agregar Suplemento" de arriba para configurar suplementos'
                      : 'No hay suplementos disponibles para agregar'}
                  </p>
                </div>
              ) : (workflowSupplements?.length || 0) > 0 && (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Codigo</TableHead>
                        <TableHead>Nombre</TableHead>
                        <TableHead className="text-right">Monto</TableHead>
                        <TableHead className="text-center">Cantidad</TableHead>
                        <TableHead className="text-center">Obligatorio</TableHead>
                        <TableHead className="text-center">Estado</TableHead>
                        <TableHead className="text-right">Acciones</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {workflowSupplements?.map((config) => (
                        <TableRow key={config.id} className={editingSupplementCode === config.supplement_code ? 'bg-muted/50' : ''}>
                          <TableCell>
                            <code className="text-xs bg-muted px-2 py-1 rounded">{config.supplement_code}</code>
                          </TableCell>
                          <TableCell>{config.supplement_name || config.supplement_code}</TableCell>
                          <TableCell className="text-right font-mono">
                            {config.supplement_amount?.toLocaleString()} XAF
                          </TableCell>
                          <TableCell className="text-center">{config.quantity_per_request}</TableCell>
                          <TableCell className="text-center">
                            {config.is_required ? (
                              <Badge variant="default">Si</Badge>
                            ) : (
                              <Badge variant="outline">No</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {config.is_active ? (
                              <CheckCircle className="h-5 w-5 text-green-500 mx-auto" />
                            ) : (
                              <XCircle className="h-5 w-5 text-red-500 mx-auto" />
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => startEditSupplement(config)}
                                disabled={supplementEditMode !== 'none'}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => { setSupplementToDelete(config); setIsDeleteSupplementDialogOpen(true) }}
                                className="text-destructive hover:text-destructive"
                                disabled={supplementEditMode !== 'none'}
                              >
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

          {/* Delete Supplement Confirmation Dialog */}
          <AlertDialog open={isDeleteSupplementDialogOpen} onOpenChange={setIsDeleteSupplementDialogOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Eliminar Suplemento</AlertDialogTitle>
                <AlertDialogDescription>
                  Esta accion eliminara el suplemento &quot;{supplementToDelete?.supplement_code}&quot; de este workflow. Esta accion no se puede deshacer.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDeleteSupplement}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {removeWorkflowSupplementMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {tCommon('delete')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileCheck className="h-5 w-5" />
                  {tDocs('documentsList')}
                </CardTitle>
                <CardDescription>
                  {tDocs('documentsCount', { count: documents?.length || 0 })}
                </CardDescription>
              </div>
              {documentEditMode === 'none' && (
                <Button onClick={startCreateDocument}>
                  <Plus className="mr-2 h-4 w-4" />
                  {tDocs('addDocument')}
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Inline Create/Edit Form */}
              {documentEditMode !== 'none' && (
                <Card className="border-primary">
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg">
                      {documentEditMode === 'create' ? 'Agregar Documentos' : tDocs('editDocument')}
                    </CardTitle>
                    {documentEditMode === 'create' && (
                      <CardDescription>
                        Puede agregar varios documentos antes de guardar
                      </CardDescription>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{tDocs('documentCode')}</Label>
                        {documentEditMode === 'create' ? (
                          <Input
                            value={docForm.document_code}
                            onChange={(e) => setDocForm({ ...docForm, document_code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_') })}
                            placeholder="DIP_ORIGINAL"
                          />
                        ) : (
                          <Input value={docForm.document_code} disabled className="bg-muted" />
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label>{tDocs('documentName')}</Label>
                        <Input
                          value={docForm.document_name_es}
                          onChange={(e) => setDocForm({ ...docForm, document_name_es: e.target.value })}
                          placeholder="Documento de Identidad Personal"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{tDocs('conditionType')}</Label>
                        <Select
                          value={docForm.condition_type}
                          onValueChange={(v) => setDocForm({ ...docForm, condition_type: v as DocumentConditionType })}
                        >
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {DOCUMENT_CONDITION_TYPES.map((t) => (
                              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex items-center gap-2 pt-6">
                        <Switch
                          id="doc_is_required"
                          checked={docForm.is_required}
                          onCheckedChange={(checked) => setDocForm({ ...docForm, is_required: checked })}
                        />
                        <Label htmlFor="doc_is_required">{tDocs('isRequired')}</Label>
                      </div>
                    </div>
                    {/* OCR Schema + Instructions (both create and edit) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{tDocs('extractionSchema')}</Label>
                        <Select
                          value={docForm.extraction_schema_key || '_none'}
                          onValueChange={(v) => setDocForm({ ...docForm, extraction_schema_key: v === '_none' ? '' : v })}
                        >
                          <SelectTrigger><SelectValue placeholder="Sin esquema OCR" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="_none">Sin esquema (upload simple)</SelectItem>
                            {extractionSchemas?.map((s) => (
                              <SelectItem key={s.key} value={s.key}>
                                {s.name} (v{s.version})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>{tDocs('instructions')}</Label>
                        <Textarea
                          value={docForm.instructions_es || ''}
                          onChange={(e) => setDocForm({ ...docForm, instructions_es: e.target.value })}
                          rows={2}
                          placeholder="Instrucciones para el ciudadano..."
                        />
                      </div>
                    </div>

                    {/* Edit mode: is_active toggle */}
                    {documentEditMode === 'edit' && (
                      <div className="flex items-center gap-2">
                        <Switch
                          id="doc_is_active"
                          checked={docForm.is_active}
                          onCheckedChange={(checked) => setDocForm({ ...docForm, is_active: checked })}
                        />
                        <Label htmlFor="doc_is_active">{tDocs('isActive')}</Label>
                      </div>
                    )}

                    {documentEditMode === 'create' && (
                      <div className="flex justify-end">
                        <Button
                          variant="secondary"
                          onClick={addToPendingDocuments}
                          disabled={!docForm.document_code || !docForm.document_name_es}
                        >
                          <Plus className="mr-2 h-4 w-4" />
                          Añadir a lista
                        </Button>
                      </div>
                    )}

                    {/* Pending documents list (batch mode) */}
                    {documentEditMode === 'create' && pendingDocuments.length > 0 && (
                      <div className="border rounded-md mt-4">
                        <div className="bg-muted/50 px-4 py-2 border-b">
                          <span className="text-sm font-medium">Documentos pendientes ({pendingDocuments.length})</span>
                        </div>
                        <Table>
                          <TableBody>
                            {pendingDocuments.map((pending) => (
                              <TableRow key={pending.document_code}>
                                <TableCell>
                                  <code className="text-xs bg-muted px-2 py-1 rounded">{pending.document_code}</code>
                                </TableCell>
                                <TableCell className="font-medium">{pending.document_name_es}</TableCell>
                                <TableCell>
                                  {pending.extraction_schema_key ? (
                                    <Badge variant="secondary" className="text-xs">{pending.extraction_schema_key}</Badge>
                                  ) : (
                                    <span className="text-xs text-muted-foreground">—</span>
                                  )}
                                </TableCell>
                                <TableCell className="text-center w-[100px]">
                                  {pending.is_required ? (
                                    <Badge variant="default" className="text-xs">Obligatorio</Badge>
                                  ) : (
                                    <Badge variant="outline" className="text-xs">Opcional</Badge>
                                  )}
                                </TableCell>
                                <TableCell className="text-right w-[50px]">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => removeFromPendingDocuments(pending.document_code)}
                                    className="h-8 w-8 text-destructive hover:text-destructive"
                                  >
                                    <X className="h-4 w-4" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex justify-end gap-2 pt-2 border-t">
                      {documentEditMode === 'create' ? (
                        <>
                          <Button
                            variant="outline"
                            onClick={cancelBatchDocuments}
                            disabled={isSavingDocBatch}
                          >
                            <X className="mr-2 h-4 w-4" />
                            Cancelar
                          </Button>
                          <Button
                            onClick={handleSaveBatchDocuments}
                            disabled={pendingDocuments.length === 0 || isSavingDocBatch}
                          >
                            {isSavingDocBatch && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            <Save className="mr-2 h-4 w-4" />
                            Guardar Todo ({pendingDocuments.length})
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button variant="outline" onClick={resetDocForm} disabled={isDocumentSaving}>
                            <X className="mr-2 h-4 w-4" />
                            {tCommon('cancel')}
                          </Button>
                          <Button
                            onClick={handleSaveDocument}
                            disabled={!docForm.document_code || !docForm.document_name_es || isDocumentSaving}
                          >
                            {isDocumentSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            <Save className="mr-2 h-4 w-4" />
                            {tCommon('save')}
                          </Button>
                        </>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Documents Table */}
              {loadingDocuments ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : sortedDocuments.length === 0 && documentEditMode === 'none' ? (
                <div className="text-center text-muted-foreground py-8">
                  <FileCheck className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">{tDocs('noDocuments')}</p>
                  <p className="text-sm mt-1">Use el boton &quot;Agregar Documento&quot; de arriba para agregar un nuevo requisito</p>
                </div>
              ) : sortedDocuments.length > 0 && (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[50px]">{tDocs('order')}</TableHead>
                        <TableHead>{tDocs('documentCode')}</TableHead>
                        <TableHead>{tDocs('documentName')}</TableHead>
                        <TableHead>OCR</TableHead>
                        <TableHead>{tDocs('condition')}</TableHead>
                        <TableHead className="text-center">{tDocs('required')}</TableHead>
                        <TableHead className="text-center">{tDocs('status')}</TableHead>
                        <TableHead className="text-right">{tDocs('actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedDocuments.map((doc, index) => (
                        <TableRow key={doc.id} className={editingDocumentCode === doc.document_code ? 'bg-muted/50' : ''}>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <GripVertical className="h-4 w-4 text-muted-foreground" />
                              <div className="flex flex-col gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-5 w-5"
                                  onClick={() => handleMoveDocument(doc, 'up')}
                                  disabled={index === 0 || reorderDocumentsMutation.isPending || documentEditMode !== 'none'}
                                >
                                  <ArrowUp className="h-3 w-3" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-5 w-5"
                                  onClick={() => handleMoveDocument(doc, 'down')}
                                  disabled={index === sortedDocuments.length - 1 || reorderDocumentsMutation.isPending || documentEditMode !== 'none'}
                                >
                                  <ArrowDown className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <code className="text-xs bg-muted px-2 py-1 rounded">{doc.document_code}</code>
                          </TableCell>
                          <TableCell>
                            <div>
                              <div className="font-medium">{doc.document_name_es}</div>
                              {doc.instructions_es && (
                                <div className="text-xs text-muted-foreground truncate max-w-[200px]">
                                  {doc.instructions_es}
                                </div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            {doc.extraction_schema_key ? (
                              <Badge variant="secondary" className="text-xs font-mono">{doc.extraction_schema_key}</Badge>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TableCell>
                          <TableCell>{getConditionBadge(doc.condition_type)}</TableCell>
                          <TableCell className="text-center">
                            {doc.is_required ? (
                              <CheckCircle className="h-4 w-4 text-green-500 mx-auto" />
                            ) : (
                              <span className="text-muted-foreground">Opcional</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {doc.is_active ? (
                              <CheckCircle className="h-4 w-4 text-green-500 mx-auto" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-500 mx-auto" />
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => startEditDocument(doc)}
                                disabled={documentEditMode !== 'none'}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => { setDocumentToDelete(doc); setIsDeleteDocDialogOpen(true) }}
                                className="text-destructive hover:text-destructive"
                                disabled={documentEditMode !== 'none'}
                              >
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

          {/* Delete Document Dialog */}
          <AlertDialog open={isDeleteDocDialogOpen} onOpenChange={setIsDeleteDocDialogOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{tDocs('deleteConfirmTitle')}</AlertDialogTitle>
                <AlertDialogDescription>
                  {tDocs('deleteConfirmDescription', { name: documentToDelete?.document_name_es })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleRemoveDocument}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {removeDocumentMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {tCommon('delete')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </TabsContent>

        {/* Appointments Tab */}
        <TabsContent value="appointments" className="space-y-6">
          {/* Summary Cards */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* Slot Configs Summary */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <CalendarClock className="h-4 w-4" />
                      Horarios de Entidad
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Configurados para {workflow?.entity_code || 'la entidad'}
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => router.push(`/${locale}/dashboard/admin/service-requests/appointments/slots/new?entity=${workflow?.entity_code}`)}
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    Nuevo
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {slotConfigs && slotConfigs.length > 0 ? (
                  <div className="space-y-3">
                    {/* Group slots by location */}
                    {Object.entries(
                      slotConfigs.reduce((acc, slot) => {
                        const key = slot.location_name || 'Sin ubicacion'
                        if (!acc[key]) acc[key] = { city: slot.city, slots: [] }
                        acc[key].slots.push(slot)
                        return acc
                      }, {} as Record<string, { city: string | null | undefined; slots: typeof slotConfigs }>)
                    ).map(([locationName, { city, slots }]) => (
                      <div key={locationName} className="border rounded-md p-2">
                        <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                          <MapPin className="h-3 w-3" />
                          {locationName}
                          {city && <span className="text-muted-foreground">({city})</span>}
                        </div>
                        <div className="space-y-1">
                          {slots.map((slot) => (
                            <div key={slot.id} className="flex items-center justify-between py-0.5 text-sm">
                              <span>{DAY_OF_WEEK_LABELS[slot.day_of_week] || slot.day_of_week}</span>
                              <span className="text-muted-foreground font-mono text-xs">{slot.start_time} - {slot.end_time}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-sm text-muted-foreground mb-2">Sin horarios configurados</p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push(`/${locale}/dashboard/admin/service-requests/appointments/slots/new?entity=${workflow?.entity_code}`)}
                    >
                      <Plus className="mr-1 h-3 w-3" />
                      Configurar Horarios
                    </Button>
                  </div>
                )}
                {slotConfigs && slotConfigs.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <Button
                      variant="link"
                      size="sm"
                      className="text-xs p-0 h-auto"
                      onClick={() => router.push(`/${locale}/dashboard/admin/service-requests/appointments?tab=slots`)}
                    >
                      Ver todos los horarios
                      <ExternalLink className="ml-1 h-3 w-3" />
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Blocked Dates Summary */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <XCircle className="h-4 w-4" />
                  Fechas Bloqueadas
                </CardTitle>
                <CardDescription className="text-xs">
                  {blockedDates?.length || 0} fechas bloqueadas
                </CardDescription>
              </CardHeader>
              <CardContent>
                {blockedDates && blockedDates.length > 0 ? (
                  <div className="space-y-1 max-h-32 overflow-auto">
                    {blockedDates.map((blocked) => (
                      <div key={blocked.id} className="flex items-center justify-between py-1 text-sm">
                        <span>{blocked.blocked_date}</span>
                        <span className="text-xs text-muted-foreground">{blocked.reason || '-'}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Sin fechas bloqueadas</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Delay Rules - Full Management */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-5 w-5" />
                  Reglas de Espera
                </CardTitle>
                <CardDescription>
                  Dias minimos de anticipacion para reservar cita segun prioridad
                </CardDescription>
              </div>
              <Button onClick={() => setIsAddingDelayRule(true)} disabled={isAddingDelayRule}>
                <Plus className="mr-2 h-4 w-4" />
                Agregar Regla
              </Button>
            </CardHeader>
            <CardContent>
              {/* Add Form */}
              {isAddingDelayRule && (
                <Card className="mb-4 border-primary">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Nueva Regla de Espera</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="space-y-2">
                        <Label>Prioridad</Label>
                        <Select
                          value={delayRuleForm.priority}
                          onValueChange={(v) => setDelayRuleForm({...delayRuleForm, priority: v as AppointmentPriority})}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {Object.entries(PRIORITY_LABELS).map(([key, label]) => (
                              <SelectItem key={key} value={key}>{label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Dias de Espera</Label>
                        <Input
                          type="number"
                          min={0}
                          value={delayRuleForm.delay_business_days}
                          onChange={(e) => setDelayRuleForm({...delayRuleForm, delay_business_days: parseInt(e.target.value) || 0})}
                        />
                      </div>
                      <div className="flex items-end gap-2">
                        <Button
                          onClick={async () => {
                            await createDelayRuleMutation.mutateAsync({
                              workflow_code: workflowCode,
                              priority: delayRuleForm.priority,
                              delay_business_days: delayRuleForm.delay_business_days,
                              is_active: true,
                            })
                            setIsAddingDelayRule(false)
                            setDelayRuleForm({ priority: 'NORMAL', delay_business_days: 3, is_active: true })
                          }}
                          disabled={createDelayRuleMutation.isPending}
                        >
                          {createDelayRuleMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                          Guardar
                        </Button>
                        <Button variant="outline" onClick={() => setIsAddingDelayRule(false)}>
                          Cancelar
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Rules Table */}
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Prioridad</TableHead>
                      <TableHead>Dias de Espera</TableHead>
                      <TableHead>Estado</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {!delayRules || delayRules.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                          No hay reglas de espera configuradas
                        </TableCell>
                      </TableRow>
                    ) : (
                      delayRules.map((rule) => (
                        <TableRow key={rule.id}>
                          <TableCell>
                            <Badge variant="outline">{PRIORITY_LABELS[rule.priority as AppointmentPriority] || rule.priority}</Badge>
                          </TableCell>
                          <TableCell>
                            {editingDelayRule === rule.id ? (
                              <Input
                                type="number"
                                min={0}
                                className="w-20"
                                value={delayRuleForm.delay_business_days}
                                onChange={(e) => setDelayRuleForm({...delayRuleForm, delay_business_days: parseInt(e.target.value) || 0})}
                              />
                            ) : (
                              <span>{rule.delay_business_days} dias habiles</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {rule.is_active ? (
                              <CheckCircle className="h-4 w-4 text-green-500" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-500" />
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {editingDelayRule === rule.id ? (
                              <div className="flex justify-end gap-1">
                                <Button
                                  size="sm"
                                  onClick={async () => {
                                    await updateDelayRuleMutation.mutateAsync({
                                      ruleId: rule.id,
                                      data: { delay_business_days: delayRuleForm.delay_business_days }
                                    })
                                    setEditingDelayRule(null)
                                  }}
                                  disabled={updateDelayRuleMutation.isPending}
                                >
                                  {updateDelayRuleMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Guardar'}
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => setEditingDelayRule(null)}>
                                  Cancelar
                                </Button>
                              </div>
                            ) : (
                              <div className="flex justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => {
                                    setDelayRuleForm({ priority: rule.priority as AppointmentPriority, delay_business_days: rule.delay_business_days, is_active: rule.is_active })
                                    setEditingDelayRule(rule.id)
                                  }}
                                >
                                  <Pencil className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="text-destructive"
                                  onClick={() => setDeleteDelayRuleId(rule.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Delete Delay Rule Dialog */}
          <AlertDialog open={!!deleteDelayRuleId} onOpenChange={() => setDeleteDelayRuleId(null)}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Eliminar Regla de Espera</AlertDialogTitle>
                <AlertDialogDescription>
                  Esta accion no se puede deshacer. La regla sera eliminada permanentemente.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  onClick={async () => {
                    if (deleteDelayRuleId) {
                      await deleteDelayRuleMutation.mutateAsync(deleteDelayRuleId)
                      setDeleteDelayRuleId(null)
                    }
                  }}
                >
                  {deleteDelayRuleMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {tCommon('delete')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </TabsContent>
      </Tabs>
      )}
    </div>
  )
}
