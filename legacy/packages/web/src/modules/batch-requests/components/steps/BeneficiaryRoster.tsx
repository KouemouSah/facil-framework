'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import {
  Users,
  Plus,
  Upload,
  Trash2,
  Edit2,
  Check,
  X,
  Loader2,
  GripVertical,
} from 'lucide-react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
import { Badge } from '@/components/ui/badge'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import type { UseBatchSessionReturn } from '../../hooks/useBatchSession'
import type {
  BeneficiaryCreateRequest,
  SessionBeneficiary,
  BatchWorkflowOption,
  WorkflowSelectionField,
} from '../../types'
import { batchApi } from '../../services/batch-api'

interface BeneficiaryRosterProps {
  hook: UseBatchSessionReturn
}

const EMPTY_FORM: BeneficiaryCreateRequest = {
  beneficiaryName: '',
  beneficiaryIdentifier: '',
  beneficiaryIdentifierType: 'dip',
  beneficiaryEmail: '',
  beneficiaryPhone: '',
  conditions: {},
}

// ============================================================================
// SORTABLE ROW — each beneficiary row is draggable (F-022)
// ============================================================================

function SortableRow({
  ben,
  idx,
  onEdit,
  onDelete,
  t,
}: {
  ben: SessionBeneficiary
  idx: number
  onEdit: (ben: SessionBeneficiary) => void
  onDelete: (id: string) => void
  t: ReturnType<typeof useTranslations>
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: ben.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <TableRow ref={setNodeRef} style={style}>
      <TableCell className="w-8 px-1">
        <button
          className="cursor-grab active:cursor-grabbing touch-none p-1 text-gray-400 hover:text-gray-600"
          {...attributes}
          {...listeners}
          aria-label={t('beneficiary.dragToReorder')}
        >
          <GripVertical className="h-4 w-4" />
        </button>
      </TableCell>
      <TableCell className="text-gray-400 w-10">{idx + 1}</TableCell>
      <TableCell className="font-medium">{ben.name}</TableCell>
      <TableCell>
        {ben.identifier ? (
          <span className="text-sm">
            <span className="text-gray-400 uppercase text-xs">
              {ben.identifierType || 'ID'}:{' '}
            </span>
            {ben.identifier}
          </span>
        ) : (
          <span className="text-gray-300">&mdash;</span>
        )}
      </TableCell>
      <TableCell className="text-sm text-gray-600 hidden md:table-cell">
        {ben.email || '\u2014'}
      </TableCell>
      <TableCell className="text-sm text-gray-600 hidden md:table-cell">
        {ben.phone || '\u2014'}
      </TableCell>
      <TableCell>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => onEdit(ben)}
          >
            <Edit2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-red-500 hover:text-red-700"
            onClick={() => onDelete(ben.id)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

// ============================================================================
// CONDITION FIELD — renders a SELECTION step field (F-018)
// ============================================================================

function ConditionField({
  field,
  value,
  onChange,
  currentConditions,
}: {
  field: WorkflowSelectionField
  value: string
  onChange: (val: string) => void
  currentConditions: Record<string, string>
}) {
  // Check if this field has a parent condition that must be met
  if (field.condition) {
    const condEntries = Object.entries(field.condition)
    for (const [key, expected] of condEntries) {
      if (String(currentConditions[key] || '') !== String(expected)) {
        return null // Parent condition not met, hide this field
      }
    }
  }

  if (field.type === 'radio' && field.options.length <= 4) {
    return (
      <div className="space-y-2">
        <Label className="text-sm font-medium">{field.label_es}</Label>
        <RadioGroup value={value} onValueChange={onChange} className="flex flex-wrap gap-3">
          {field.options.map((opt) => (
            <div key={opt.value} className="flex items-center space-x-2">
              <RadioGroupItem value={opt.value} id={`cond-${field.key}-${opt.value}`} />
              <Label
                htmlFor={`cond-${field.key}-${opt.value}`}
                className="text-sm font-normal cursor-pointer"
              >
                {opt.label_es}
              </Label>
            </div>
          ))}
        </RadioGroup>
      </div>
    )
  }

  // Fallback: select dropdown
  return (
    <div className="space-y-1">
      <Label className="text-sm font-medium">{field.label_es}</Label>
      <select
        className="w-full border rounded-md px-3 py-2 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">—</option>
        {field.options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label_es}
          </option>
        ))}
      </select>
    </div>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function BeneficiaryRoster({ hook }: BeneficiaryRosterProps) {
  const {
    session,
    isSaving,
    addBeneficiary,
    updateBeneficiary,
    removeBeneficiary,
    reorderBeneficiary,
    importCsv,
  } = hook
  const t = useTranslations('batch')

  const [showAddDialog, setShowAddDialog] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState<BeneficiaryCreateRequest>({ ...EMPTY_FORM })
  const csvInputRef = useRef<HTMLInputElement>(null)

  const beneficiaries = session?.beneficiaries || []

  // F-018: Fetch workflow metadata to get selection fields
  const [workflows, setWorkflows] = useState<BatchWorkflowOption[]>([])
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const resp = await batchApi.getAvailableWorkflows()
        if (!cancelled) setWorkflows(resp.workflows)
      } catch (e) {
        console.error('[BeneficiaryRoster] Failed to load workflows:', e)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // Derive selection fields for current workflow
  const selectionFields: WorkflowSelectionField[] = useMemo(() => {
    if (!session || !workflows.length) return []
    const wf = workflows.find(
      (w) =>
        w.code === session.workflowCode ||
        w.all_workflow_codes.includes(session.workflowCode)
    )
    return wf?.selection_fields || []
  }, [session, workflows])

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  )

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = beneficiaries.findIndex((b) => b.id === active.id)
    const newIndex = beneficiaries.findIndex((b) => b.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return

    // Determine direction and number of moves
    const direction = newIndex < oldIndex ? 'up' : 'down'
    const moves = Math.abs(newIndex - oldIndex)
    for (let i = 0; i < moves; i++) {
      await reorderBeneficiary(String(active.id), direction)
    }
  }

  const handleAdd = async () => {
    if (!form.beneficiaryName.trim()) return
    const result = await addBeneficiary(form)
    if (result) {
      setForm({ ...EMPTY_FORM })
      setShowAddDialog(false)
    }
  }

  const handleEdit = async () => {
    if (!editingId || !form.beneficiaryName.trim()) return
    await updateBeneficiary(editingId, {
      beneficiaryName: form.beneficiaryName,
      beneficiaryIdentifier: form.beneficiaryIdentifier,
      beneficiaryIdentifierType: form.beneficiaryIdentifierType,
      beneficiaryEmail: form.beneficiaryEmail,
      beneficiaryPhone: form.beneficiaryPhone,
      conditions: form.conditions,
    })
    setEditingId(null)
    setShowAddDialog(false)
    setForm({ ...EMPTY_FORM })
  }

  const handleConfirmDelete = async () => {
    if (!deleteId) return
    await removeBeneficiary(deleteId)
    setDeleteId(null)
  }

  const startEdit = (ben: SessionBeneficiary) => {
    setEditingId(ben.id)
    setForm({
      beneficiaryName: ben.name,
      beneficiaryIdentifier: ben.identifier || '',
      beneficiaryIdentifierType: ben.identifierType || 'dip',
      beneficiaryEmail: ben.email || '',
      beneficiaryPhone: ben.phone || '',
      conditions: ben.conditions || {},
    })
    setShowAddDialog(true)
  }

  const handleCsvChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      await importCsv(file)
      if (csvInputRef.current) csvInputRef.current.value = ''
    }
  }

  const handleConditionChange = (key: string, value: string) => {
    setForm((prev) => ({
      ...prev,
      conditions: { ...(prev.conditions || {}), [key]: value },
    }))
  }

  return (
    <div className="space-y-4">
      {/* Hidden CSV input (ref-based, not imperative createElement) */}
      <input
        ref={csvInputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleCsvChange}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-semibold">{t('beneficiary.rosterTitle')}</h2>
          <Badge variant="secondary">{beneficiaries.length}</Badge>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => csvInputRef.current?.click()}
            disabled={isSaving}
          >
            <Upload className="h-4 w-4 mr-1" />
            {t('beneficiary.importCsv')}
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setEditingId(null)
              setForm({ ...EMPTY_FORM })
              setShowAddDialog(true)
            }}
            disabled={isSaving}
          >
            <Plus className="h-4 w-4 mr-1" />
            {t('beneficiary.add')}
          </Button>
        </div>
      </div>

      {beneficiaries.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <Users className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>{t('beneficiary.noBeneficiaries')}</p>
          <p className="text-sm mt-1">
            {t('beneficiary.addOrImport')}
          </p>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead className="w-10">#</TableHead>
                  <TableHead>{t('beneficiary.fullName')}</TableHead>
                  <TableHead>{t('beneficiary.identifierNumber')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('beneficiary.email')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('beneficiary.phone')}</TableHead>
                  <TableHead className="w-20">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <SortableContext
                items={beneficiaries.map((b) => b.id)}
                strategy={verticalListSortingStrategy}
              >
                <TableBody>
                  {beneficiaries.map((ben, idx) => (
                    <SortableRow
                      key={ben.id}
                      ben={ben}
                      idx={idx}
                      onEdit={startEdit}
                      onDelete={(id) => setDeleteId(id)}
                      t={t}
                    />
                  ))}
                </TableBody>
              </SortableContext>
            </Table>
          </DndContext>
        </div>
      )}

      {/* Add/Edit Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingId ? t('beneficiary.edit') : t('beneficiary.addTitle')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
            <div>
              <Label>{t('beneficiary.fullName')} *</Label>
              <Input
                value={form.beneficiaryName}
                onChange={(e) =>
                  setForm({ ...form, beneficiaryName: e.target.value })
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t('beneficiary.identifierType')}</Label>
                <Input
                  value={form.beneficiaryIdentifierType || ''}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      beneficiaryIdentifierType: e.target.value,
                    })
                  }
                  placeholder="dip, pasaporte, nie..."
                />
              </div>
              <div>
                <Label>{t('beneficiary.identifierNumber')}</Label>
                <Input
                  value={form.beneficiaryIdentifier || ''}
                  onChange={(e) =>
                    setForm({ ...form, beneficiaryIdentifier: e.target.value })
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t('beneficiary.email')}</Label>
                <Input
                  type="email"
                  value={form.beneficiaryEmail || ''}
                  onChange={(e) =>
                    setForm({ ...form, beneficiaryEmail: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>{t('beneficiary.phone')}</Label>
                <Input
                  value={form.beneficiaryPhone || ''}
                  onChange={(e) =>
                    setForm({ ...form, beneficiaryPhone: e.target.value })
                  }
                  placeholder="+240..."
                />
              </div>
            </div>

            {/* F-018: Dynamic condition fields from workflow SELECTION steps */}
            {selectionFields.length > 0 && (
              <div className="border-t pt-4 mt-2 space-y-3">
                <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
                  {t('beneficiary.conditionsTitle')}
                </p>
                {selectionFields.map((field) => (
                  <ConditionField
                    key={field.key}
                    field={field}
                    value={(form.conditions || {})[field.key] || ''}
                    onChange={(val) => handleConditionChange(field.key, val)}
                    currentConditions={form.conditions || {}}
                  />
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              <X className="h-4 w-4 mr-1" />
              {t('beneficiary.cancel')}
            </Button>
            <Button
              onClick={editingId ? handleEdit : handleAdd}
              disabled={!form.beneficiaryName.trim() || isSaving}
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <Check className="h-4 w-4 mr-1" />
              )}
              {editingId ? t('beneficiary.save') : t('beneficiary.add')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation dialog */}
      <AlertDialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('confirmDelete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {beneficiaries.find((b) => b.id === deleteId)?.name}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('beneficiary.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete}>
              <Trash2 className="h-4 w-4 mr-1" />
              {t('beneficiary.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
