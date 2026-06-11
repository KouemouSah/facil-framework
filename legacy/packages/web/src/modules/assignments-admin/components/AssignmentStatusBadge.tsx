/**
 * AssignmentStatusBadge Component
 * Status badge for assignments
 *
 * @module assignments-admin/components
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * Status from assignment_status_enum (DATABASE_SCHEMA_REFERENCE.md):
 * assigned, in_progress, pending_review, completed, reassigned, cancelled, rejected
 */

'use client'

import { Badge } from '@/components/ui/badge'
import { useTranslations } from 'next-intl'
import type { AssignmentStatus } from '../types'

interface AssignmentStatusBadgeProps {
  status: AssignmentStatus
}

// Colors for each valid status from assignment_status_enum
const statusColors: Record<AssignmentStatus, string> = {
  assigned: 'bg-purple-500 hover:bg-purple-600',
  in_progress: 'bg-blue-500 hover:bg-blue-600',
  pending_review: 'bg-yellow-500 hover:bg-yellow-600',
  completed: 'bg-green-500 hover:bg-green-600',
  reassigned: 'bg-orange-500 hover:bg-orange-600',
  cancelled: 'bg-gray-500 hover:bg-gray-600',
  rejected: 'bg-red-500 hover:bg-red-600',
}

export function AssignmentStatusBadge({ status }: AssignmentStatusBadgeProps) {
  const t = useTranslations('assignments')

  return (
    <Badge className={statusColors[status]}>
      {t(`status.${status}`)}
    </Badge>
  )
}
