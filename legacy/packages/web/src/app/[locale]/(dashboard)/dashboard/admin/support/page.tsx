'use client'

import { useEffect, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TicketList, useSupport } from '@/modules/support'
import type { TicketStatus, TicketPriority } from '@/modules/support'

export default function AdminSupportPage() {
  const t = useTranslations('support')
  const locale = useLocale()

  const [statusFilter, setStatusFilter] = useState<TicketStatus | 'all'>('all')
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | 'all'>('all')

  const {
    tickets,
    isLoading,
    pagination,
    loadAllTickets,
  } = useSupport()

  useEffect(() => {
    const filters: { status?: TicketStatus; priority?: TicketPriority } = {}
    if (statusFilter !== 'all') filters.status = statusFilter
    if (priorityFilter !== 'all') filters.priority = priorityFilter
    loadAllTickets(1, 20, filters)
  }, [loadAllTickets, statusFilter, priorityFilter])

  const handlePageChange = (page: number) => {
    const filters: { status?: TicketStatus; priority?: TicketPriority } = {}
    if (statusFilter !== 'all') filters.status = statusFilter
    if (priorityFilter !== 'all') filters.priority = priorityFilter
    loadAllTickets(page, 20, filters)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('pageTitle')}</h1>
        <p className="text-muted-foreground mt-2">
          {t('manageTicket')}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('tickets')}</CardTitle>
          <CardDescription>{t('myRequestsDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('status')}</label>
              <Select
                value={statusFilter}
                onValueChange={(value) => setStatusFilter(value as TicketStatus | 'all')}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('tableStatus')}</SelectItem>
                  <SelectItem value="open">{t('statuses.open')}</SelectItem>
                  <SelectItem value="in_progress">{t('statuses.in_progress')}</SelectItem>
                  <SelectItem value="pending_user">{t('statuses.pending_user')}</SelectItem>
                  <SelectItem value="resolved">{t('statuses.resolved')}</SelectItem>
                  <SelectItem value="closed">{t('statuses.closed')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">{t('priority')}</label>
              <Select
                value={priorityFilter}
                onValueChange={(value) => setPriorityFilter(value as TicketPriority | 'all')}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('tablePriority')}</SelectItem>
                  <SelectItem value="low">{t('priorities.low')}</SelectItem>
                  <SelectItem value="normal">{t('priorities.normal')}</SelectItem>
                  <SelectItem value="high">{t('priorities.high')}</SelectItem>
                  <SelectItem value="urgent">{t('priorities.urgent')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <TicketList
            tickets={tickets}
            isLoading={isLoading}
            basePath={`/${locale}/dashboard/admin/support`}
            locale={locale}
            pagination={pagination}
            onPageChange={handlePageChange}
            showCreateButton={false}
          />
        </CardContent>
      </Card>
    </div>
  )
}
