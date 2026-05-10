'use client'

/**
 * Notifications Page — Paginated list of all user notifications
 *
 * Features:
 * - Paginated (20 per page) with server-side data
 * - Filter by type (status_change, payment, appointment, agent)
 * - Expandable notification detail on click
 * - Link to related service request
 * - Humanized messages (no technical content)
 */

import { useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import Link from 'next/link'
import {
  Bell, ArrowRight, CheckCircle, MessageSquare,
  Calendar, XCircle, CreditCard, AlertTriangle, AlertCircle,
  ChevronLeft, ChevronRight, Filter, ExternalLink,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/core/api/client'

const PAGE_SIZE = 20

interface NotificationItem {
  id: string
  action: string
  title: string
  message: string | null
  performed_at: string
  performer_role: string
  is_new: boolean
  new_status: string | null
  request_id: string
}

interface NotificationsResponse {
  items: NotificationItem[]
  total: number
  total_unread: number
  page: number
  page_size: number
}

const NOTIFICATION_ICONS: Record<string, typeof Bell> = {
  status_change: ArrowRight,
  agent_action_taken: CheckCircle,
  comment_added: MessageSquare,
  cita_scheduled: Calendar,
  cita_rescheduled: Calendar,
  cita_cancelled: XCircle,
  payment_received: CreditCard,
  payment_failed: AlertTriangle,
  validation_failed: AlertCircle,
}

const NOTIFICATION_COLORS: Record<string, string> = {
  status_change: 'text-blue-500',
  agent_action_taken: 'text-green-500',
  comment_added: 'text-purple-500',
  cita_scheduled: 'text-teal-500',
  cita_rescheduled: 'text-orange-500',
  cita_cancelled: 'text-red-500',
  payment_received: 'text-green-600',
  payment_failed: 'text-red-600',
  validation_failed: 'text-amber-500',
}

const INTERNAL_PATTERNS = [
  /^retroactive fix/i,
  /^migration \d+/i,
  /^system cleanup/i,
  /^auto.?fix/i,
  /^debug:/i,
]

const HUMANIZE: Record<string, Record<string, string>> = {
  'Atomic wizard payment: cash': { es: 'Pago en efectivo registrado', fr: 'Paiement en especes enregistre', en: 'Cash payment registered' },
  'Atomic wizard payment: mobile_money': { es: 'Pago por dinero movil registrado', fr: 'Paiement mobile enregistre', en: 'Mobile money payment registered' },
  'Atomic wizard payment: card': { es: 'Pago con tarjeta registrado', fr: 'Paiement par carte enregistre', en: 'Card payment registered' },
  'Atomic wizard payment: bank_transfer': { es: 'Transferencia bancaria registrada', fr: 'Virement bancaire enregistre', en: 'Bank transfer registered' },
  'wizard.payment.cash': { es: 'Pago en efectivo registrado', fr: 'Paiement en especes enregistre', en: 'Cash payment registered' },
}

function humanize(msg: string | null | undefined, locale: string): string | null {
  if (!msg) return null
  if (INTERNAL_PATTERNS.some(p => p.test(msg))) return null
  const mapped = HUMANIZE[msg]
  if (mapped) return mapped[locale] || mapped['es'] || msg
  for (const [key, t] of Object.entries(HUMANIZE)) {
    if (msg.includes(key)) return t[locale] || t['es'] || msg
  }
  return msg
}

const TYPE_FILTERS = [
  { value: 'all', labelKey: 'filterAll' },
  { value: 'status_change', labelKey: 'filterStatus' },
  { value: 'payment', labelKey: 'filterPayment' },
  { value: 'appointment', labelKey: 'filterAppointment' },
  { value: 'agent', labelKey: 'filterAgent' },
]

export default function NotificationsPage() {
  const locale = useLocale()
  const t = useTranslations('notifications')

  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Server-side paginated fetch
  const actionParam = typeFilter === 'all' ? undefined : typeFilter
  const { data, isLoading } = useQuery<NotificationsResponse>({
    queryKey: ['citizen-notifications', page, typeFilter],
    queryFn: () => {
      const sp = new URLSearchParams()
      sp.set('page', String(page))
      sp.set('page_size', String(PAGE_SIZE))
      if (actionParam) sp.set('action_filter', actionParam)
      return apiClient.get<NotificationsResponse>(
        `/service-requests/notifications?${sp.toString()}`
      ).then(r => r.data)
    },
    staleTime: 30_000,
  })

  const pageItems = data?.items ?? []
  const totalCount = data?.total ?? 0
  const totalUnread = data?.total_unread ?? 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  // Extract request ID from title (format: "Action - SRV-2026-00012")
  const extractRequestRef = (title: string) => {
    const match = title.match(/SRV-\d{4}-\d+/)
    return match ? match[0] : null
  }

  if (isLoading) {
    return (
      <div className="space-y-4 p-4 max-w-4xl mx-auto">
        <h1 className="text-xl font-bold">{t('title')}</h1>
        {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-16 w-full" />)}
      </div>
    )
  }

  return (
    <div className="space-y-4 p-4 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Bell className="h-5 w-5" />
            {t('title')}
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {totalCount} {t('total')}
            {totalUnread > 0 && (
              <> &middot; <span className="text-blue-600 font-medium">{totalUnread} {t('unread')}</span></>
            )}
          </p>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(1) }}>
            <SelectTrigger className="w-[160px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPE_FILTERS.map(f => (
                <SelectItem key={f.value} value={f.value} className="text-xs">
                  {t(f.labelKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Notifications list */}
      {pageItems.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Bell className="h-12 w-12 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">{t('empty')}</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 divide-y">
            {pageItems.map((notif) => {
              const Icon = NOTIFICATION_ICONS[notif.action] || Bell
              const color = NOTIFICATION_COLORS[notif.action] || 'text-gray-500'
              const msg = humanize(notif.message, locale)
              const isExpanded = expandedId === notif.id
              const requestRef = extractRequestRef(notif.title)
              const requestId = (notif as NotificationItem).request_id

              return (
                <div
                  key={notif.id}
                  className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors hover:bg-muted/30 ${
                    notif.is_new ? 'bg-blue-50/50 dark:bg-blue-950/20' : ''
                  }`}
                  onClick={() => setExpandedId(isExpanded ? null : notif.id)}
                >
                  <Icon className={`h-5 w-5 mt-0.5 shrink-0 ${color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className={`text-sm font-medium ${isExpanded ? '' : 'truncate'}`}>
                        {notif.title}
                      </p>
                      {notif.is_new && (
                        <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />
                      )}
                    </div>
                    {msg && (
                      <p className={`text-sm text-muted-foreground mt-0.5 ${isExpanded ? '' : 'line-clamp-1'}`}>
                        {msg}
                      </p>
                    )}
                    {/* Expanded: link to request */}
                    {isExpanded && requestId && (
                      <Link
                        href={`/${locale}/dashboard/service-requests/${requestId}`}
                        className="inline-flex items-center gap-1 text-xs text-primary mt-2 hover:underline"
                        onClick={e => e.stopPropagation()}
                      >
                        <ExternalLink className="h-3 w-3" />
                        {t('viewRequest')} {requestRef || ''}
                      </Link>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap mt-0.5">
                    {new Date(notif.performed_at).toLocaleDateString(
                      locale === 'es' ? 'es-GQ' : locale === 'fr' ? 'fr-FR' : 'en-US',
                      { day: '2-digit', month: 'short' }
                    )}
                  </span>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{page}/{totalPages}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="icon" className="h-8 w-8"
              disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" className="h-8 w-8"
              disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
