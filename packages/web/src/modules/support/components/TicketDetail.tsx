'use client'

import { useTranslations } from 'next-intl'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ArrowLeft,
  Calendar,
  User,
  Tag,
  AlertCircle,
  CheckCircle,
  Clock,
  UserCheck,
} from 'lucide-react'
import type { SupportTicket, TicketStatus, TicketPriority } from '../types'
import { canUserCloseTicket } from '../types'

interface TicketDetailProps {
  ticket: SupportTicket | null
  isLoading: boolean
  isAdmin?: boolean
  onBack: () => void
  onClose: () => void
  onStatusChange?: (status: TicketStatus) => void
  onPriorityChange?: (priority: TicketPriority) => void
  onAssign?: (userId: string | null) => void
  users?: Array<{ id: string; name: string }>
  locale: string
}

export function TicketDetail({
  ticket,
  isLoading,
  isAdmin = false,
  onBack,
  onClose,
  onStatusChange,
  onPriorityChange,
  onAssign,
  users = [],
  locale,
}: TicketDetailProps) {
  const t = useTranslations('support')

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString(locale, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getPriorityVariant = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'destructive'
      case 'high':
        return 'default'
      case 'low':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'open':
        return 'default'
      case 'in_progress':
        return 'default'
      case 'pending_user':
        return 'secondary'
      case 'resolved':
        return 'default'
      case 'closed':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'open':
        return <AlertCircle className="h-4 w-4" />
      case 'in_progress':
        return <Clock className="h-4 w-4" />
      case 'resolved':
        return <CheckCircle className="h-4 w-4" />
      default:
        return null
    }
  }

  if (isLoading || !ticket) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const isClosed = ticket.status === 'closed'
  const canClose = !isAdmin && canUserCloseTicket(ticket)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{ticket.subject}</h1>
            <p className="text-muted-foreground font-mono">
              {ticket.ticketNumber}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={getStatusVariant(ticket.status)}>
            {getStatusIcon(ticket.status)}
            <span className="ml-1">{t(`statuses.${ticket.status}`)}</span>
          </Badge>
          <Badge variant={getPriorityVariant(ticket.priority)}>
            {t(`priorities.${ticket.priority}`)}
          </Badge>
        </div>
      </div>

      {/* Actions - Admin or User Close */}
      {(isAdmin || canClose) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('actions')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-4">
              {isAdmin && onStatusChange && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('status')}</label>
                  <Select
                    value={ticket.status}
                    onValueChange={(value) => onStatusChange(value as TicketStatus)}
                    disabled={isClosed}
                  >
                    <SelectTrigger className="w-[180px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="open">{t('statuses.open')}</SelectItem>
                      <SelectItem value="in_progress">
                        {t('statuses.in_progress')}
                      </SelectItem>
                      <SelectItem value="pending_user">
                        {t('statuses.pending_user')}
                      </SelectItem>
                      <SelectItem value="resolved">
                        {t('statuses.resolved')}
                      </SelectItem>
                      <SelectItem value="closed">
                        {t('statuses.closed')}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {isAdmin && onPriorityChange && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('priority')}</label>
                  <Select
                    value={ticket.priority}
                    onValueChange={(value) => onPriorityChange(value as TicketPriority)}
                    disabled={isClosed}
                  >
                    <SelectTrigger className="w-[180px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">{t('priorities.low')}</SelectItem>
                      <SelectItem value="normal">
                        {t('priorities.normal')}
                      </SelectItem>
                      <SelectItem value="high">{t('priorities.high')}</SelectItem>
                      <SelectItem value="urgent">
                        {t('priorities.urgent')}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {isAdmin && onAssign && users.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('assignTo')}</label>
                  <Select
                    value={ticket.assignedTo?.toString() || 'unassigned'}
                    onValueChange={(value) =>
                      onAssign(value === 'unassigned' ? null : value)
                    }
                    disabled={isClosed}
                  >
                    <SelectTrigger className="w-[200px]">
                      <SelectValue placeholder={t('selectAgent')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unassigned">
                        {t('unassigned')}
                      </SelectItem>
                      {users.map((user) => (
                        <SelectItem key={user.id} value={user.id.toString()}>
                          {user.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {(canClose || isAdmin) && !isClosed && (
                <div className="flex items-end">
                  <Button variant="outline" onClick={onClose}>
                    {t('closeTicket')}
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Ticket Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('ticketDetails')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Description */}
          <div>
            <h3 className="font-medium mb-2">{t('description')}</h3>
            <p className="text-muted-foreground whitespace-pre-wrap">
              {ticket.description}
            </p>
          </div>

          <Separator />

          {/* Metadata */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="font-medium">{t('createdAt')}</p>
                <p className="text-muted-foreground">
                  {formatDate(ticket.createdAt)}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="font-medium">{t('createdBy')}</p>
                <p className="text-muted-foreground">
                  {ticket.createdByName || ticket.createdByEmail || '-'}
                </p>
              </div>
            </div>

            {ticket.categoryName && (
              <div className="flex items-center gap-2">
                <Tag className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="font-medium">{t('category')}</p>
                  <p className="text-muted-foreground">{ticket.categoryName}</p>
                </div>
              </div>
            )}

            {ticket.assignedToName && (
              <div className="flex items-center gap-2">
                <UserCheck className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="font-medium">{t('assignedTo')}</p>
                  <p className="text-muted-foreground">{ticket.assignedToName}</p>
                </div>
              </div>
            )}

            {ticket.resolvedAt && (
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="font-medium">{t('resolvedAt')}</p>
                  <p className="text-muted-foreground">
                    {formatDate(ticket.resolvedAt)}
                  </p>
                </div>
              </div>
            )}

            {ticket.closedAt && (
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="font-medium">{t('closedAt')}</p>
                  <p className="text-muted-foreground">
                    {formatDate(ticket.closedAt)}
                  </p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default TicketDetail
