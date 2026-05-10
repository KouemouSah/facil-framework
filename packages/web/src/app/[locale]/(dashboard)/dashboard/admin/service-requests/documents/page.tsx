'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { useSearchParams } from 'next/navigation'
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
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  FileCheck,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  GripVertical,
  CheckCircle,
  XCircle,
  ArrowUp,
  ArrowDown,
} from 'lucide-react'
import {
  useWorkflows,
  useDocumentRequirements,
  useAddDocumentRequirement,
  useUpdateDocumentRequirement,
  useRemoveDocumentRequirement,
  useReorderDocuments,
} from '@/modules/service-requests-admin'
import type {
  DocumentRequirement,
  DocumentRequirementCreate,
  DocumentRequirementUpdate,
  DocumentConditionType,
  DocumentReorderItem,
} from '@/modules/service-requests-admin'
import { DOCUMENT_CONDITION_TYPES } from '@/modules/service-requests-admin'

export default function DocumentsPage() {
  const t = useTranslations('admin.serviceRequests.documents')
  const tCommon = useTranslations('common')
  const searchParams = useSearchParams()
  const workflowFromUrl = searchParams.get('workflow')

  // State
  const [selectedWorkflowCode, setSelectedWorkflowCode] = useState<string>(workflowFromUrl || '')
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<DocumentRequirement | null>(null)

  // Form state
  const [formData, setFormData] = useState<DocumentRequirementCreate>({
    document_code: '',
    document_name_es: '',
    condition_type: 'always',
    is_required: true,
    display_order: 0,
    instructions_es: '',
    extraction_schema_key: '',
    is_active: true,
  })

  // Set workflow from URL on mount
  useEffect(() => {
    if (workflowFromUrl) {
      setSelectedWorkflowCode(workflowFromUrl)
    }
  }, [workflowFromUrl])

  // Queries
  const { data: workflows, isLoading: isLoadingWorkflows } = useWorkflows()
  const {
    data: documents,
    isLoading: isLoadingDocuments,
    error,
    refetch,
  } = useDocumentRequirements(selectedWorkflowCode)

  // Mutations
  const addMutation = useAddDocumentRequirement()
  const updateMutation = useUpdateDocumentRequirement()
  const removeMutation = useRemoveDocumentRequirement()
  const reorderMutation = useReorderDocuments()

  // Sort documents by display_order
  const sortedDocuments = [...(documents || [])].sort((a, b) => a.display_order - b.display_order)

  // Handlers
  const handleAddDocument = async () => {
    if (!selectedWorkflowCode) return

    try {
      await addMutation.mutateAsync({
        workflowCode: selectedWorkflowCode,
        data: {
          ...formData,
          display_order: documents?.length || 0,
        },
      })
      setIsCreateDialogOpen(false)
      resetForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleUpdateDocument = async () => {
    if (!selectedWorkflowCode || !selectedDocument) return

    try {
      const updateData: DocumentRequirementUpdate = {
        document_name_es: formData.document_name_es,
        condition_type: formData.condition_type,
        is_required: formData.is_required,
        instructions_es: formData.instructions_es,
        extraction_schema_key: formData.extraction_schema_key,
        is_active: formData.is_active,
      }
      await updateMutation.mutateAsync({
        workflowCode: selectedWorkflowCode,
        documentCode: selectedDocument.document_code,
        data: updateData,
      })
      setIsEditDialogOpen(false)
      resetForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleRemoveDocument = async () => {
    if (!selectedWorkflowCode || !selectedDocument) return

    try {
      await removeMutation.mutateAsync({
        workflowCode: selectedWorkflowCode,
        documentCode: selectedDocument.document_code,
      })
      setIsDeleteDialogOpen(false)
      setSelectedDocument(null)
    } catch {
      // Error handled by mutation
    }
  }

  const handleMoveUp = async (doc: DocumentRequirement) => {
    const currentIndex = sortedDocuments.findIndex((d) => d.id === doc.id)
    if (currentIndex <= 0) return

    const newOrder: DocumentReorderItem[] = sortedDocuments.map((d, i) => {
      if (i === currentIndex - 1) {
        return { document_code: d.document_code, display_order: currentIndex }
      }
      if (i === currentIndex) {
        return { document_code: d.document_code, display_order: currentIndex - 1 }
      }
      return { document_code: d.document_code, display_order: i }
    })

    await reorderMutation.mutateAsync({
      workflowCode: selectedWorkflowCode,
      order: newOrder,
    })
  }

  const handleMoveDown = async (doc: DocumentRequirement) => {
    const currentIndex = sortedDocuments.findIndex((d) => d.id === doc.id)
    if (currentIndex >= sortedDocuments.length - 1) return

    const newOrder: DocumentReorderItem[] = sortedDocuments.map((d, i) => {
      if (i === currentIndex) {
        return { document_code: d.document_code, display_order: currentIndex + 1 }
      }
      if (i === currentIndex + 1) {
        return { document_code: d.document_code, display_order: currentIndex }
      }
      return { document_code: d.document_code, display_order: i }
    })

    await reorderMutation.mutateAsync({
      workflowCode: selectedWorkflowCode,
      order: newOrder,
    })
  }

  const openEditDialog = (doc: DocumentRequirement) => {
    setSelectedDocument(doc)
    setFormData({
      document_code: doc.document_code,
      document_name_es: doc.document_name_es,
      condition_type: doc.condition_type as DocumentConditionType,
      is_required: doc.is_required,
      display_order: doc.display_order,
      instructions_es: doc.instructions_es || '',
      extraction_schema_key: doc.extraction_schema_key || '',
      is_active: doc.is_active,
    })
    setIsEditDialogOpen(true)
  }

  const openDeleteDialog = (doc: DocumentRequirement) => {
    setSelectedDocument(doc)
    setIsDeleteDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      document_code: '',
      document_name_es: '',
      condition_type: 'always',
      is_required: true,
      display_order: 0,
      instructions_es: '',
      extraction_schema_key: '',
      is_active: true,
    })
    setSelectedDocument(null)
  }

  const getConditionBadge = (type: string) => {
    switch (type) {
      case 'always':
        return <Badge variant="default">{t('conditionAlways')}</Badge>
      case 'if_solicitud_type':
        return <Badge variant="secondary">{t('conditionSolicitud')}</Badge>
      case 'if_form_field':
        return <Badge variant="outline">{t('conditionFormField')}</Badge>
      case 'if_document_exists':
        return <Badge variant="outline">{t('conditionDocExists')}</Badge>
      default:
        return <Badge variant="outline">{type}</Badge>
    }
  }

  // Render loading state
  if (isLoadingWorkflows) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
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
      </div>

      {/* Workflow Selector */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCheck className="h-5 w-5" />
            {t('selectWorkflow')}
          </CardTitle>
          <CardDescription>{t('selectWorkflowDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Select value={selectedWorkflowCode} onValueChange={setSelectedWorkflowCode}>
              <SelectTrigger className="w-full max-w-md">
                <SelectValue placeholder={t('selectWorkflowPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                {workflows?.map((wf) => (
                  <SelectItem key={wf.code} value={wf.code}>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{wf.code}</span>
                      <span className="text-muted-foreground">- {wf.name_es}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedWorkflowCode && (
              <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
                <DialogTrigger asChild>
                  <Button onClick={() => resetForm()}>
                    <Plus className="mr-2 h-4 w-4" />
                    {t('addDocument')}
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-lg">
                  <DialogHeader>
                    <DialogTitle>{t('addDocument')}</DialogTitle>
                    <DialogDescription>{t('addDocumentDescription')}</DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                      <Label htmlFor="doc_code">{t('documentCode')}</Label>
                      <Input
                        id="doc_code"
                        value={formData.document_code}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            document_code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_'),
                          })
                        }
                        placeholder="DIP_ORIGINAL"
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="doc_name">{t('documentName')}</Label>
                      <Input
                        id="doc_name"
                        value={formData.document_name_es}
                        onChange={(e) => setFormData({ ...formData, document_name_es: e.target.value })}
                        placeholder="Documento de Identidad Personal"
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="condition_type">{t('conditionType')}</Label>
                      <Select
                        value={formData.condition_type}
                        onValueChange={(value) =>
                          setFormData({ ...formData, condition_type: value as DocumentConditionType })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {DOCUMENT_CONDITION_TYPES.map((type) => (
                            <SelectItem key={type.value} value={type.value}>
                              {type.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="extraction_schema">{t('extractionSchema')}</Label>
                      <Input
                        id="extraction_schema"
                        value={formData.extraction_schema_key || ''}
                        onChange={(e) => setFormData({ ...formData, extraction_schema_key: e.target.value })}
                        placeholder="dip_gq"
                      />
                      <p className="text-xs text-muted-foreground">{t('extractionSchemaHint')}</p>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="instructions">{t('instructions')}</Label>
                      <Textarea
                        id="instructions"
                        value={formData.instructions_es || ''}
                        onChange={(e) => setFormData({ ...formData, instructions_es: e.target.value })}
                        rows={2}
                        placeholder="Escanear ambas caras del documento..."
                      />
                    </div>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="is_required">{t('isRequired')}</Label>
                        <Switch
                          id="is_required"
                          checked={formData.is_required}
                          onCheckedChange={(checked) => setFormData({ ...formData, is_required: checked })}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <Label htmlFor="is_active_doc">{t('isActive')}</Label>
                        <Switch
                          id="is_active_doc"
                          checked={formData.is_active}
                          onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                        />
                      </div>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                      {tCommon('cancel')}
                    </Button>
                    <Button
                      onClick={handleAddDocument}
                      disabled={!formData.document_code || !formData.document_name_es || addMutation.isPending}
                    >
                      {addMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      {tCommon('add')}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Documents List */}
      {selectedWorkflowCode && (
        <Card>
          <CardHeader>
            <CardTitle>{t('documentsList')}</CardTitle>
            <CardDescription>
              {t('documentsCount', { count: documents?.length || 0 })}
              {' - '}
              {t('dragToReorder')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingDocuments ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="h-5 w-5" />
                <span>{error instanceof Error ? error.message : 'Error loading documents'}</span>
                <Button variant="outline" size="sm" onClick={() => refetch()}>
                  {tCommon('retry')}
                </Button>
              </div>
            ) : sortedDocuments.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">{t('noDocuments')}</div>
            ) : (
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[50px]">{t('order')}</TableHead>
                      <TableHead>{t('documentCode')}</TableHead>
                      <TableHead>{t('documentName')}</TableHead>
                      <TableHead>{t('condition')}</TableHead>
                      <TableHead>{t('schema')}</TableHead>
                      <TableHead className="text-center">{t('required')}</TableHead>
                      <TableHead className="text-center">{t('status')}</TableHead>
                      <TableHead className="text-right">{t('actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedDocuments.map((doc, index) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <GripVertical className="h-4 w-4 text-muted-foreground" />
                            <div className="flex flex-col gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-5 w-5"
                                onClick={() => handleMoveUp(doc)}
                                disabled={index === 0 || reorderMutation.isPending}
                              >
                                <ArrowUp className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-5 w-5"
                                onClick={() => handleMoveDown(doc)}
                                disabled={index === sortedDocuments.length - 1 || reorderMutation.isPending}
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
                        <TableCell>{getConditionBadge(doc.condition_type)}</TableCell>
                        <TableCell>
                          {doc.extraction_schema_key ? (
                            <Badge variant="outline" className="font-mono text-xs">
                              {doc.extraction_schema_key}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
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
                            <Button variant="ghost" size="icon" onClick={() => openEditDialog(doc)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => openDeleteDialog(doc)}
                              className="text-destructive hover:text-destructive"
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
      )}

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('editDocument')}</DialogTitle>
            <DialogDescription>{t('editDocumentDescription')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>{t('documentCode')}</Label>
              <Input value={formData.document_code} disabled className="bg-muted" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-name">{t('documentName')}</Label>
              <Input
                id="edit-name"
                value={formData.document_name_es}
                onChange={(e) => setFormData({ ...formData, document_name_es: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-condition">{t('conditionType')}</Label>
              <Select
                value={formData.condition_type}
                onValueChange={(value) =>
                  setFormData({ ...formData, condition_type: value as DocumentConditionType })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOCUMENT_CONDITION_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-schema">{t('extractionSchema')}</Label>
              <Input
                id="edit-schema"
                value={formData.extraction_schema_key || ''}
                onChange={(e) => setFormData({ ...formData, extraction_schema_key: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-instructions">{t('instructions')}</Label>
              <Textarea
                id="edit-instructions"
                value={formData.instructions_es || ''}
                onChange={(e) => setFormData({ ...formData, instructions_es: e.target.value })}
                rows={2}
              />
            </div>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label htmlFor="edit-required">{t('isRequired')}</Label>
                <Switch
                  id="edit-required"
                  checked={formData.is_required}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_required: checked })}
                />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="edit-active">{t('isActive')}</Label>
                <Switch
                  id="edit-active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button onClick={handleUpdateDocument} disabled={!formData.document_name_es || updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {tCommon('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteConfirmDescription', { name: selectedDocument?.document_name_es })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveDocument}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {removeMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
