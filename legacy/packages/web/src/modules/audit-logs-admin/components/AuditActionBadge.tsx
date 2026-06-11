'use client'

import { Badge } from '@/components/ui/badge'

interface AuditActionBadgeProps {
  action: string
}

const actionColors: Record<string, string> = {
  payment_completed: 'bg-green-500 text-white',
  payment_failed: 'bg-red-500 text-white',
  request_submitted: 'bg-blue-500 text-white',
  request_approved: 'bg-green-600 text-white',
  request_rejected: 'bg-red-600 text-white',
  request_escalated: 'bg-orange-500 text-white',
  document_uploaded: 'bg-indigo-500 text-white',
  document_validated: 'bg-green-500 text-white',
  user_registered: 'bg-blue-500 text-white',
  user_verified: 'bg-green-500 text-white',
  sla_warning: 'bg-yellow-500 text-white',
  sla_breach: 'bg-red-500 text-white',
}

export function AuditActionBadge({ action }: AuditActionBadgeProps) {
  const colorClass = actionColors[action] || 'bg-gray-500 text-white'
  return (
    <Badge className={colorClass}>
      {action.replace(/_/g, ' ')}
    </Badge>
  )
}
