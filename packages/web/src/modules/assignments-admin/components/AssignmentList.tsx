/**
 * AssignmentList Component
 * Displays a grid of assignments
 *
 * @module assignments-admin/components
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * - Migration 053: item_id, item_type (not declaration_id)
 * - Migration 054: agent_profile_id, agent_name (not assignee_id/name)
 */

'use client'

import { useTranslations } from 'next-intl'
import { Loader2, AlertCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AssignmentCard } from './AssignmentCard'
import { useAssignments } from '../hooks/useAssignments'
import type { Assignment, AssignmentStatus } from '../types'

interface AssignmentListProps {
  filters?: {
    status?: AssignmentStatus
    agent_profile_id?: string
    search?: string
  }
  onSelect?: (assignment: Assignment) => void
  onEdit?: (assignment: Assignment) => void
  onDelete?: (assignment: Assignment) => void
}

export function AssignmentList({
  filters,
  onSelect,
  onEdit,
  onDelete,
}: AssignmentListProps) {
  const t = useTranslations('assignments')

  const { data, isLoading, error } = useAssignments({
    status: filters?.status,
    agent_profile_id: filters?.agent_profile_id,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">{t('loading')}</span>
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {t('errorLoading')}: {error.message}
        </AlertDescription>
      </Alert>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">{t('noAssignments')}</p>
      </div>
    )
  }

  // Filter by search if provided
  let filteredData = data
  if (filters?.search) {
    const searchLower = filters.search.toLowerCase()
    filteredData = data.filter(
      (assignment) =>
        assignment.item_id.toLowerCase().includes(searchLower) ||
        assignment.agent_name?.toLowerCase().includes(searchLower) ||
        assignment.notes?.toLowerCase().includes(searchLower)
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {filteredData.map((assignment) => (
        <AssignmentCard
          key={assignment.id}
          assignment={assignment}
          onClick={() => onSelect?.(assignment)}
          onEdit={() => onEdit?.(assignment)}
          onDelete={() => onDelete?.(assignment)}
        />
      ))}
    </div>
  )
}
