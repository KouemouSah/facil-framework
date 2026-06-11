'use client'

/**
 * Citizen Dashboard Page
 * Service-request-centric dashboard with stats, recent activity, and notifications.
 *
 * All labels are dynamic (from backend or i18n) — no hardcoded Spanish strings.
 */

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  FileText,
  CreditCard,
  HelpCircle,
  Bell,
  Clock,
  DollarSign,
  FileCheck,
  AlertCircle,
  RefreshCw,
  ClipboardList,
  CalendarClock,
  CheckCircle,
  MessageSquare,
  Calendar,
  XCircle,
  AlertTriangle,
  ArrowRight,
  FileStack,
  Receipt,
} from 'lucide-react'
import { getAuthData } from '@/core/auth/storage'
import type { User } from '@/types/auth'
import { useLocale, useTranslations } from 'next-intl'
import { useDashboardData } from '@/modules/dashboard'
import { STATUS_BADGE_COLORS, PAYMENT_STATUS_COLORS } from '@/modules/service-requests/constants'
import { batchApi } from '@/modules/batch-requests/services/batch-api'
import type { BatchRequest } from '@/modules/batch-requests/types'

// ═══════════════════════════════════════════════════════════════
// NOTIFICATION STYLING (action type → icon + color)
// ═══════════════════════════════════════════════════════════════

const NOTIFICATION_ICONS: Record<string, typeof CheckCircle> = {
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

// ═══════════════════════════════════════════════════════════════
// HELPERS (locale-aware)
// ═══════════════════════════════════════════════════════════════

/** Format ISO date string using browser's Intl API */
function formatDate(dateStr: string, locale: string): string {
  try {
    const intlLocale = locale === 'es' ? 'es-GQ' : locale === 'fr' ? 'fr-FR' : 'en-US'
    return new Date(dateStr).toLocaleDateString(intlLocale, {
      day: '2-digit', month: '2-digit', year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function formatAmount(amount: number, locale: string = 'es'): string {
  const intlLocale = locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ';
  return amount.toLocaleString(intlLocale)
}

/** Locale-aware relative time using Intl.RelativeTimeFormat */
function timeAgo(dateStr: string, locale: string): string {
  try {
    const now = Date.now()
    const date = new Date(dateStr).getTime()
    const diffSec = Math.floor((now - date) / 1000)

    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto', style: 'short' })

    if (diffSec < 60) return rtf.format(-diffSec, 'second')
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return rtf.format(-diffMin, 'minute')
    const diffHrs = Math.floor(diffMin / 60)
    if (diffHrs < 24) return rtf.format(-diffHrs, 'hour')
    const diffDays = Math.floor(diffHrs / 24)
    if (diffDays < 7) return rtf.format(-diffDays, 'day')
    return formatDate(dateStr, locale)
  } catch {
    return dateStr
  }
}

/** Check if ISO date string is today */
function isToday(dateStr: string): boolean {
  const d = new Date(dateStr)
  const now = new Date()
  return d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
}

/** Check if ISO date string is tomorrow */
function isTomorrow(dateStr: string): boolean {
  const d = new Date(dateStr)
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  return d.getFullYear() === tomorrow.getFullYear() &&
    d.getMonth() === tomorrow.getMonth() &&
    d.getDate() === tomorrow.getDate()
}

/** Format appointment date in locale-aware long format */
function formatAppointmentDate(dateStr: string, locale: string): string {
  try {
    const intlLocale = locale === 'es' ? 'es-GQ' : locale === 'fr' ? 'fr-FR' : 'en-US'
    return new Date(dateStr).toLocaleDateString(intlLocale, {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

// ═══════════════════════════════════════════════════════════════
// NOTIFICATION HUMANIZATION — map technical messages to user-friendly
// ═══════════════════════════════════════════════════════════════

/** Technical messages generated by backend that are NOT useful to citizens */
const INTERNAL_MESSAGE_PATTERNS = [
  /^retroactive fix/i,
  /^migration \d+/i,
  /^system cleanup/i,
  /^auto.?fix/i,
  /^debug:/i,
]

/** Map technical message substrings to human-readable i18n keys */
const MESSAGE_HUMANIZE_MAP: Record<string, Record<string, string>> = {
  'Atomic wizard payment: cash': {
    es: 'Pago en efectivo registrado',
    fr: 'Paiement en especes enregistre',
    en: 'Cash payment registered',
  },
  'Atomic wizard payment: mobile_money': {
    es: 'Pago por dinero movil registrado',
    fr: 'Paiement mobile enregistre',
    en: 'Mobile money payment registered',
  },
  'Atomic wizard payment: card': {
    es: 'Pago con tarjeta registrado',
    fr: 'Paiement par carte enregistre',
    en: 'Card payment registered',
  },
  'Atomic wizard payment: bank_transfer': {
    es: 'Transferencia bancaria registrada',
    fr: 'Virement bancaire enregistre',
    en: 'Bank transfer registered',
  },
  'wizard.payment.cash': {
    es: 'Pago en efectivo registrado',
    fr: 'Paiement en especes enregistre',
    en: 'Cash payment registered',
  },
}

function humanizeNotificationMessage(
  message: string | null | undefined,
  locale: string
): string | null {
  if (!message) return null

  // Filter out internal/technical messages
  if (INTERNAL_MESSAGE_PATTERNS.some(p => p.test(message))) return null

  // Check exact match in humanize map
  const mapped = MESSAGE_HUMANIZE_MAP[message]
  if (mapped) return mapped[locale] || mapped['es'] || message

  // Check partial match (message contains technical key)
  for (const [key, translations] of Object.entries(MESSAGE_HUMANIZE_MAP)) {
    if (message.includes(key)) return translations[locale] || translations['es'] || message
  }

  // Passthrough — message is already human-readable
  return message
}

// ═══════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function DashboardPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('dashboard')
  const tStatus = useTranslations('statusLabels')
  const tBundle = useTranslations('bundleWorkflow')
  const [user, setUser] = useState<User | null>(null)

  const { stats, summary, isLoading, error, refetch } = useDashboardData()
  const [activeBatch, setActiveBatch] = useState<BatchRequest | null>(null)

  useEffect(() => {
    const authData = getAuthData()
    if (!authData) {
      router.push(`/${locale}/auth`)
      return
    }

    // Bug 4 fix (2026-05-06): the citizen dashboard must NOT render for
    // agent/admin roles — it shows "Nueva Solicitud", "Mis Solicitudes",
    // etc. which are citizen-only actions. Reported when supcomercio1
    // (supervisor MIN_COMERCIO) hit /dashboard via back-button and saw
    // citizen Quick Actions instead of an agent UI. Redirect by role
    // before any citizen UI is painted (returns null below until redirect
    // completes).
    const userRole = (authData.user.role || '').toLowerCase()
    if (userRole === 'admin') {
      router.replace(`/${locale}/dashboard/admin`)
      return
    }
    if (userRole === 'agent' || userRole.startsWith('supervisor_')) {
      router.replace(`/${locale}/dashboard/supervisor`)
      return
    }
    // Citizens, businesses, accountants → stay on this citizen dashboard

    const userData = {
      ...authData.user,
      is_active: authData.user.status === 'active',
      email_verified: authData.user.email_verified ?? false,
    }
    setUser(userData as User)

    // Fetch most recent active batch (lightweight, non-blocking)
    batchApi.listBatches({ status: 'IN_PROGRESS', pageSize: 1 })
      .then((res) => {
        if (res.batches.length > 0) setActiveBatch(res.batches[0])
      })
      .catch(() => { /* silent — batch teaser is optional */ })
  }, [router, locale])

  const hasData = summary !== null
  const hasRequests = hasData && summary.recentRequests.length > 0

  /** Get localized status label — tries i18n key, falls back to formatted string */
  const getStatusLabel = useMemo(() => {
    return (status: string) => {
      try {
        return tStatus(status)
      } catch {
        return status.replace(/_/g, ' ')
      }
    }
  }, [tStatus])

  /** Appointment time i18n label */
  const appointmentTimeLabel = useMemo(() => {
    return { es: 'a las', fr: 'à', en: 'at' }[locale] || 'at'
  }, [locale])

  if (!user) return null

  return (
    <div className="space-y-6">
      {/* ── Welcome ── */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
          {t('welcomeMessage', { name: user.first_name || user.email })}
        </h1>
        <p className="text-muted-foreground mt-2">
          {t('welcomeSubtitle')}
        </p>
      </div>

      {/* ── Action Required Banner ── */}
      {hasData && summary.actionRequired.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
            <div className="space-y-2 flex-1">
              <p className="font-medium text-amber-800 dark:text-amber-200">
                {t('actionRequired')}
              </p>
              <div className="space-y-1">
                {summary.actionRequired.map((ar) => (
                  <Link
                    key={ar.requestId}
                    href={`/${locale}/dashboard/service-requests/${ar.requestId}`}
                    className="flex items-center gap-2 text-sm text-amber-700 hover:text-amber-900 dark:text-amber-300 dark:hover:text-amber-100"
                  >
                    <span className="font-mono">{ar.reference}</span>
                    <span>—</span>
                    <span>{ar.message}</span>
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Quick Actions ── */}
      <div>
        <h2 className="text-xl font-semibold mb-4">{t('quickActions')}</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href={`/${locale}/dashboard/service-requests/new`}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {t('newServiceRequest')}
                </CardTitle>
                <ClipboardList className="h-5 w-5 text-primary" />
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {t('newServiceRequestDesc')}
                </p>
              </CardContent>
            </Link>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href={`/${locale}/dashboard/service-requests`}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {t('myRequests')}
                </CardTitle>
                <FileText className="h-5 w-5 text-primary" />
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {t('myRequestsDesc')}
                </p>
              </CardContent>
            </Link>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href={`/${locale}/dashboard/bundle-payment`}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {tBundle('payObligations')}
                </CardTitle>
                <Receipt className="h-5 w-5 text-primary" />
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {tBundle('payObligationsDesc')}
                </p>
              </CardContent>
            </Link>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href={`/${locale}/dashboard/support`}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {t('support')}
                </CardTitle>
                <HelpCircle className="h-5 w-5 text-primary" />
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {t('supportDesc')}
                </p>
              </CardContent>
            </Link>
          </Card>
        </div>
      </div>

      {/* ── Statistics ── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{t('statistics')}</h2>
          {error && (
            <Button variant="outline" size="sm" onClick={refetch} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              {t('retry')}
            </Button>
          )}
        </div>

        {error && (
          <div className="mb-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('activeRequests')}</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? <Skeleton className="h-8 w-16" /> : (
                <div className="text-2xl font-bold">{stats.active}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('completedRequests')}</CardTitle>
              <FileCheck className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? <Skeleton className="h-8 w-16" /> : (
                <div className="text-2xl font-bold">{stats.completed}</div>
              )}
            </CardContent>
          </Card>

          <Card className={stats.pendingAction > 0 ? 'border-amber-300 dark:border-amber-700' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('pendingAction')}</CardTitle>
              <AlertCircle className={`h-4 w-4 ${stats.pendingAction > 0 ? 'text-amber-500' : 'text-muted-foreground'}`} />
            </CardHeader>
            <CardContent>
              {isLoading ? <Skeleton className="h-8 w-16" /> : (
                <div className={`text-2xl font-bold ${stats.pendingAction > 0 ? 'text-amber-600' : ''}`}>
                  {stats.pendingAction}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('totalPaid')}</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? <Skeleton className="h-8 w-24" /> : (
                <div className="text-2xl font-bold">
                  {formatAmount(stats.totalPaid, locale)} <span className="text-sm font-normal text-muted-foreground">FCFA</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── Upcoming Appointment ── */}
      {hasData && summary.upcomingAppointment && (
        <Card className="border-teal-200 dark:border-teal-800 bg-teal-50/50 dark:bg-teal-950/30">
          <CardHeader className="flex flex-row items-center gap-3 pb-3">
            <CalendarClock className="h-5 w-5 text-teal-600" />
            <div className="flex-1">
              <CardTitle className="text-base">{t('upcomingAppointment')}</CardTitle>
            </div>
            {isToday(summary.upcomingAppointment.appointmentDate) && (
              <Badge className="bg-green-500">{t('today')}</Badge>
            )}
            {isTomorrow(summary.upcomingAppointment.appointmentDate) && (
              <Badge className="bg-blue-500">{t('tomorrow')}</Badge>
            )}
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  {summary.upcomingAppointment.workflowLabel}
                  {' — '}
                  <span className="font-mono text-muted-foreground">
                    {summary.upcomingAppointment.requestReference}
                  </span>
                </p>
                <p className="text-sm text-muted-foreground">
                  {formatAppointmentDate(summary.upcomingAppointment.appointmentDate, locale)}
                  {summary.upcomingAppointment.time && ` ${appointmentTimeLabel} ${summary.upcomingAppointment.time}`}
                  {summary.upcomingAppointment.location && ` — ${summary.upcomingAppointment.location}`}
                </p>
              </div>
              <Link href={`/${locale}/dashboard/service-requests/${summary.upcomingAppointment.requestId}`}>
                <Button variant="outline" size="sm">
                  {t('viewRequest')}
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Active Batch Teaser ── */}
      {activeBatch && (
        <Card className="border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/30">
          <CardHeader className="flex flex-row items-center gap-3 pb-3">
            <FileStack className="h-5 w-5 text-indigo-600" />
            <div className="flex-1">
              <CardTitle className="text-base">{t('batchRequests')}</CardTitle>
            </div>
            <Badge className="bg-indigo-100 text-indigo-700">
              {activeBatch.itemsCompleted}/{activeBatch.totalItems}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium font-mono">
                  {activeBatch.reference}
                </p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-indigo-100 rounded-full w-32">
                    <div
                      className="h-2 bg-indigo-500 rounded-full transition-all"
                      style={{ width: `${activeBatch.totalItems > 0 ? (activeBatch.itemsCompleted / activeBatch.totalItems) * 100 : 0}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {activeBatch.totalItems > 0
                      ? Math.round((activeBatch.itemsCompleted / activeBatch.totalItems) * 100)
                      : 0}%
                  </span>
                </div>
              </div>
              <Link href={`/${locale}/dashboard/batch-requests/${activeBatch.id}`}>
                <Button variant="outline" size="sm">
                  {t('viewBatch')}
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Tabs ── */}
      <div>
        <Tabs defaultValue="requests" className="space-y-4">
          <TabsList>
            <TabsTrigger value="requests">
              <ClipboardList className="h-4 w-4 mr-2" />
              {t('recentRequestsTab')}
            </TabsTrigger>
            <TabsTrigger value="payments">
              <CreditCard className="h-4 w-4 mr-2" />
              {t('recentPaymentsTab')}
            </TabsTrigger>
            <TabsTrigger value="notifications">
              <Bell className="h-4 w-4 mr-2" />
              {t('notificationsTab')}
              {stats.unreadNotifications > 0 && (
                <Badge variant="destructive" className="ml-2 text-xs px-1.5 py-0">
                  {stats.unreadNotifications}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* ── Solicitudes Recientes Tab ── */}
          <TabsContent value="requests" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('recentRequestsTab')}</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
                  </div>
                ) : !hasRequests ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <ClipboardList className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>{t('noRequests')}</p>
                    <p className="text-sm mt-1">{t('noRequestsDesc')}</p>
                    <Link href={`/${locale}/dashboard/service-requests/new`}>
                      <Button variant="outline" className="mt-4">
                        {t('startFirstRequest')}
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('reference')}</TableHead>
                        <TableHead>{t('workflow')}</TableHead>
                        <TableHead>{t('date')}</TableHead>
                        <TableHead>{t('status')}</TableHead>
                        <TableHead className="text-right">{t('amount')}</TableHead>
                        <TableHead className="text-right">{t('actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {summary!.recentRequests.map((req) => (
                        <TableRow key={req.id}>
                          <TableCell className="font-mono text-sm">{req.reference}</TableCell>
                          <TableCell className="text-sm">{req.workflowLabel}</TableCell>
                          <TableCell className="text-sm">{formatDate(req.createdAt, locale)}</TableCell>
                          <TableCell>
                            <Badge className={STATUS_BADGE_COLORS[req.status] || 'bg-gray-500'}>
                              {getStatusLabel(req.status)}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right text-sm">
                            {req.totalAmount ? `${formatAmount(req.totalAmount, locale)} FCFA` : '—'}
                          </TableCell>
                          <TableCell className="text-right">
                            <Link href={`/${locale}/dashboard/service-requests/${req.id}`}>
                              <Button variant="outline" size="sm">{t('view')}</Button>
                            </Link>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Pagos Recientes Tab ── */}
          <TabsContent value="payments" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('recentPaymentsTab')}</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
                  </div>
                ) : !hasData || summary.recentPayments.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <CreditCard className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>{t('noPayments')}</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('reference')}</TableHead>
                        <TableHead>{t('workflow')}</TableHead>
                        <TableHead>{t('amount')}</TableHead>
                        <TableHead>{t('date')}</TableHead>
                        <TableHead>{t('paymentMethod')}</TableHead>
                        <TableHead>{t('status')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {summary.recentPayments.map((pay) => (
                        <TableRow key={pay.id}>
                          <TableCell className="font-mono text-sm">{pay.requestReference}</TableCell>
                          <TableCell className="text-sm">{pay.workflowLabel}</TableCell>
                          <TableCell className="font-semibold text-sm">
                            {formatAmount(pay.amount, locale)} {pay.currency}
                          </TableCell>
                          <TableCell className="text-sm">{formatDate(pay.createdAt, locale)}</TableCell>
                          <TableCell className="text-sm capitalize">
                            {pay.paymentMethod?.replace(/_/g, ' ') || '—'}
                          </TableCell>
                          <TableCell>
                            <Badge className={PAYMENT_STATUS_COLORS[pay.status] || 'bg-gray-500'}>
                              {pay.status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Notificaciones Tab ── */}
          <TabsContent value="notifications" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('notificationsTab')}</CardTitle>
                {stats.unreadNotifications > 0 && (
                  <CardDescription>
                    {stats.unreadNotifications} {t('unread')}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
                  </div>
                ) : !hasData || summary.notifications.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>{t('noNotifications')}</p>
                    <p className="text-sm mt-1">{t('noNotificationsDesc')}</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {summary.notifications
                      .filter((notif) => {
                        // Filter out notifications with purely internal messages
                        const msg = humanizeNotificationMessage(notif.message, locale)
                        return notif.action !== 'status_change' || msg !== null || notif.newStatus
                      })
                      .map((notif) => {
                        const Icon = NOTIFICATION_ICONS[notif.action] || Bell
                        const color = NOTIFICATION_COLORS[notif.action] || 'text-gray-500'
                        const humanMsg = humanizeNotificationMessage(notif.message, locale)
                        return (
                          <div
                            key={notif.id}
                            className={`flex items-start gap-3 p-3 rounded-lg transition-colors ${
                              notif.isNew ? 'bg-blue-50/70 dark:bg-blue-950/30' : 'hover:bg-muted/50'
                            }`}
                          >
                            <Icon className={`h-5 w-5 mt-0.5 shrink-0 ${color}`} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <p className="text-sm font-medium truncate">{notif.title}</p>
                                {notif.isNew && (
                                  <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />
                                )}
                              </div>
                              {humanMsg && (
                                <p className="text-sm text-muted-foreground line-clamp-2 mt-0.5">
                                  {humanMsg}
                                </p>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground whitespace-nowrap mt-0.5">
                              {timeAgo(notif.performedAt, locale)}
                            </span>
                          </div>
                        )
                      })}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
