/**
 * AssignmentForm Component
 * Form for creating/editing assignments
 *
 * @module assignments-admin/components
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * - Migration 053: item_id, item_type (not declaration_id)
 * - Migration 054: agent_profile_id (not assignee_id)
 * - priority_level is integer 1-10 (not string)
 */

'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2 } from 'lucide-react'
import type {
  Assignment,
  ManualAssignmentRequest,
  AssignmentStatus,
  ItemType,
  PriorityLevel,
} from '../types'

interface AssignmentFormProps {
  initialData?: Assignment
  onSubmit: (data: ManualAssignmentRequest) => Promise<void>
  onCancel: () => void
  isLoading?: boolean
  isEditMode?: boolean
}

// Valid item types from database
const itemTypes: ItemType[] = ['tax_declaration', 'service_request', 'service_payment', 'other']

// Valid statuses from assignment_status_enum (for edit mode)
const statuses: AssignmentStatus[] = [
  'assigned',
  'in_progress',
  'pending_review',
  'completed',
  'reassigned',
  'cancelled',
  'rejected',
]

/**
 * Get priority label based on numeric level (1-10)
 */
function getPriorityLabel(level: PriorityLevel): string {
  if (level <= 3) return 'low'
  if (level <= 6) return 'medium'
  if (level <= 8) return 'high'
  return 'urgent'
}

export function AssignmentForm({
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
  isEditMode = false,
}: AssignmentFormProps) {
  const t = useTranslations('assignments')

  const [formData, setFormData] = useState({
    item_id: initialData?.item_id || '',
    item_type: initialData?.item_type || 'tax_declaration' as ItemType,
    agent_profile_id: initialData?.agent_profile_id || '',
    priority_level: initialData?.priority_level || 5,
    status: initialData?.status || 'assigned' as AssignmentStatus,
    notes: initialData?.notes || '',
    deadline_days: 7,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSubmit({
      item_id: formData.item_id,
      item_type: formData.item_type,
      agent_profile_id: formData.agent_profile_id,
      priority_level: formData.priority_level,
      notes: formData.notes || undefined,
      deadline_days: formData.deadline_days,
    })
  }

  const handleChange = <K extends keyof typeof formData>(
    field: K,
    value: typeof formData[K]
  ) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {!isEditMode && (
        <>
          {/* Item ID */}
          <div className="space-y-2">
            <Label htmlFor="item_id">{t('form.itemId')}</Label>
            <Input
              id="item_id"
              value={formData.item_id}
              onChange={(e) => handleChange('item_id', e.target.value)}
              placeholder={t('form.itemIdPlaceholder')}
              required
            />
          </div>

          {/* Item Type */}
          <div className="space-y-2">
            <Label htmlFor="item_type">{t('form.itemType')}</Label>
            <Select
              value={formData.item_type}
              onValueChange={(value) => handleChange('item_type', value as ItemType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {itemTypes.map((type) => (
                  <SelectItem key={type} value={type}>
                    {t(`itemType.${type}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Agent Profile ID */}
          <div className="space-y-2">
            <Label htmlFor="agent_profile_id">{t('form.agentProfileId')}</Label>
            <Input
              id="agent_profile_id"
              value={formData.agent_profile_id}
              onChange={(e) => handleChange('agent_profile_id', e.target.value)}
              placeholder={t('form.agentProfileIdPlaceholder')}
              required
            />
          </div>

          {/* Deadline Days */}
          <div className="space-y-2">
            <Label htmlFor="deadline_days">{t('form.deadlineDays')}</Label>
            <Input
              id="deadline_days"
              type="number"
              min={1}
              max={90}
              value={formData.deadline_days}
              onChange={(e) => handleChange('deadline_days', parseInt(e.target.value) || 7)}
            />
          </div>
        </>
      )}

      {isEditMode && (
        <div className="space-y-2">
          <Label htmlFor="status">{t('form.status')}</Label>
          <Select
            value={formData.status}
            onValueChange={(value) => handleChange('status', value as AssignmentStatus)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statuses.map((status) => (
                <SelectItem key={status} value={status}>
                  {t(`status.${status}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Priority Level (1-10) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="priority_level">{t('form.priorityLevel')}</Label>
          <span className="text-sm text-muted-foreground">
            {formData.priority_level} - {t(`priority.${getPriorityLabel(formData.priority_level)}`)}
          </span>
        </div>
        <input
          type="range"
          id="priority_level"
          min={1}
          max={10}
          step={1}
          value={formData.priority_level}
          onChange={(e) => handleChange('priority_level', parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{t('priority.low')}</span>
          <span>{t('priority.medium')}</span>
          <span>{t('priority.high')}</span>
          <span>{t('priority.urgent')}</span>
        </div>
      </div>

      {/* Notes */}
      <div className="space-y-2">
        <Label htmlFor="notes">{t('form.notes')}</Label>
        <Textarea
          id="notes"
          value={formData.notes}
          onChange={(e) => handleChange('notes', e.target.value)}
          placeholder={t('form.notesPlaceholder')}
          rows={3}
        />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('form.cancel')}
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {isEditMode ? t('form.update') : t('form.create')}
        </Button>
      </div>
    </form>
  )
}
