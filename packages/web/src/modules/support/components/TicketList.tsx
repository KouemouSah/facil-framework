'use client'

import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { Eye, Plus } from 'lucide-react'
import type { SupportTicket } from '../types'

interface TicketListProps {
  tickets: SupportTicket[]
  isLoading: boolean
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
  onPageChange: (page: number) => void
  basePath: string
  showCreateButton?: boolean
  onCreateClick?: () => void
  locale: string
}

export function TicketList({
  tickets,
  isLoading,
  pagination,
  onPageChange,
  basePath,
  showCreateButton = true,
  onCreateClick,
  locale,
}: TicketListProps) {
  const t = useTranslations('support')
  const router = useRouter()

  const handleViewTicket = (ticketId: number) => {
    router.push(`${basePath}/${ticketId}`)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
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

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <Skeleton className="h-8 w-48" />
          {showCreateButton && <Skeleton className="h-10 w-32" />}
        </div>
        <div className="border rounded-md">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead><Skeleton className="h-4 w-20" /></TableHead>
                <TableHead><Skeleton className="h-4 w-32" /></TableHead>
                <TableHead><Skeleton className="h-4 w-16" /></TableHead>
                <TableHead><Skeleton className="h-4 w-16" /></TableHead>
                <TableHead><Skeleton className="h-4 w-24" /></TableHead>
                <TableHead><Skeleton className="h-4 w-16" /></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">
          {t('tickets')} ({pagination.total})
        </h2>
        {showCreateButton && (
          <Button onClick={onCreateClick}>
            <Plus className="w-4 h-4 mr-2" />
            {t('createTicket')}
          </Button>
        )}
      </div>

      {tickets.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {t('noTickets')}
        </div>
      ) : (
        <>
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('ticketNumber')}</TableHead>
                  <TableHead>{t('subject')}</TableHead>
                  <TableHead>{t('priority')}</TableHead>
                  <TableHead>{t('status')}</TableHead>
                  <TableHead>{t('createdAt')}</TableHead>
                  <TableHead className="w-[60px]">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tickets.map((ticket) => (
                  <TableRow key={ticket.id}>
                    <TableCell className="font-mono text-sm">
                      {ticket.ticketNumber}
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate">
                      {ticket.subject}
                    </TableCell>
                    <TableCell>
                      <Badge variant={getPriorityVariant(ticket.priority)}>
                        {t(`priorities.${ticket.priority}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusVariant(ticket.status)}>
                        {t(`statuses.${ticket.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(ticket.createdAt)}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleViewTicket(ticket.id)}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {pagination.totalPages > 1 && (
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    onClick={() => onPageChange(Math.max(1, pagination.page - 1))}
                    className={
                      pagination.page === 1
                        ? 'pointer-events-none opacity-50'
                        : 'cursor-pointer'
                    }
                  />
                </PaginationItem>
                {[...Array(pagination.totalPages)].map((_, i) => (
                  <PaginationItem key={i}>
                    <PaginationLink
                      onClick={() => onPageChange(i + 1)}
                      isActive={pagination.page === i + 1}
                      className="cursor-pointer"
                    >
                      {i + 1}
                    </PaginationLink>
                  </PaginationItem>
                ))}
                <PaginationItem>
                  <PaginationNext
                    onClick={() =>
                      onPageChange(Math.min(pagination.totalPages, pagination.page + 1))
                    }
                    className={
                      pagination.page === pagination.totalPages
                        ? 'pointer-events-none opacity-50'
                        : 'cursor-pointer'
                    }
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          )}
        </>
      )}
    </div>
  )
}

export default TicketList
