/**
 * AssignmentCard Component
 * Displays a single assignment as a card
 *
 * @module assignments-admin/components
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * - Migration 053: item_id, item_type (not declaration_id)
 * - Migration 054: agent_profile_id, agent_name (not assignee_id/name)
 * - priority_level is integer 1-10 (not string)
 */

'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { User, Calendar, Edit, Trash2 } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { AssignmentStatusBadge } from './AssignmentStatusBadge'
import type { Assignment, PriorityLevel } from '../types'

interface AssignmentCardProps {
  assignment: Assignment
  onClick?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

/**
 * Get priority label and color based on numeric priority_level (1-10)
 * - 1-3: Low (gray)
 * - 4-6: Medium/Normal (blue)
 * - 7-8: High (orange)
 * - 9-10: Urgent/Critical (red)
 */
function getPriorityConfig(level: PriorityLevel): { label: string; color: string } {
  if (level <= 3) return { label: 'low', color: 'bg-gray-100 text-gray-800' }
  if (level <= 6) return { label: 'medium', color: 'bg-blue-100 text-blue-800' }
  if (level <= 8) return { label: 'high', color: 'bg-orange-100 text-orange-800' }
  return { label: 'urgent', color: 'bg-red-100 text-red-800' }
}

export function AssignmentCard({
  assignment,
  onClick,
  onEdit,
  onDelete,
}: AssignmentCardProps) {
  const t = useTranslations('assignments')
  const priorityConfig = getPriorityConfig(assignment.priority_level)

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <CardTitle className="text-base">
            {t('itemId')}: {assignment.item_id}
          </CardTitle>
          <AssignmentStatusBadge status={assignment.status} />
        </div>
        <span className="text-xs text-muted-foreground">
          {t(`itemType.${assignment.item_type}`)}
        </span>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <User className="h-4 w-4" />
          <span>{assignment.agent_name || t('noAgent')}</span>
        </div>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4" />
          <span>
            {new Date(assignment.assigned_at).toLocaleDateString('fr-FR')}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <Badge className={priorityConfig.color}>
            {t(`priority.${priorityConfig.label}`)} ({assignment.priority_level})
          </Badge>

          <div className="flex gap-1">
            {onEdit && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  onEdit()
                }}
              >
                <Edit className="h-4 w-4" />
              </Button>
            )}
            {onDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete()
                }}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            )}
          </div>
        </div>

        {assignment.notes && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {assignment.notes}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
