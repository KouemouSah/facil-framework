/**
 * DashboardsListing — public landing page at /admin/dashboards.
 *
 * Mig 323 (2026-05-05):
 * - Reads BD-driven metadata from /reports-config (admin-RLS-aware)
 * - Groups cards by category (executive / finance / operations / ...)
 * - Card title uses the current locale (title_es / title_fr / title_en)
 * - Both providers (Looker + Grafana) marked ready when their respective
 *   ID is set (looker_report_id OR grafana_dashboard_uid).
 */

'use client'

import React from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useParams } from 'next/navigation'
import {
  AlertCircle, Activity, BarChart3, Construction, Lock, Settings,
} from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

import { useReportsConfig } from '../hooks/useReportsConfig'
import type {
  DashboardCategory, DashboardReportEntry, DashboardRlsMode,
} from '../types'

const RLS_BADGE_VARIANT: Record<DashboardRlsMode, 'default' | 'secondary' | 'outline'> = {
  public: 'outline',
  authenticated: 'outline',
  entity: 'default',
  agent_via_join: 'default',
  admin_only: 'secondary',
}

const CATEGORY_ORDER: DashboardCategory[] = [
  'executive', 'finance', 'operations', 'business', 'product', 'security',
]

/** Pick the title for the current locale, fallback to title_es. */
function titleForLocale(report: DashboardReportEntry, locale: string): string {
  if (locale.startsWith('fr') && report.title_fr) return report.title_fr
  if (locale.startsWith('en') && report.title_en) return report.title_en
  return report.title_es || report.label || report.dashboard_id
}

function descriptionForLocale(report: DashboardReportEntry, locale: string): string {
  if (locale.startsWith('fr')) return report.description_fr || report.description || ''
  if (locale.startsWith('en')) return report.description_en || report.description || ''
  return report.description_es || report.description || ''
}

function isReady(report: DashboardReportEntry): boolean {
  if (report.provider === 'grafana') return !!report.grafana_dashboard_uid
  return !!report.looker_report_id
}

function ReportCard({
  report, locale,
}: { report: DashboardReportEntry; locale: string }) {
  const t = useTranslations('admin.dashboards')
  const ready = isReady(report)
  const title = titleForLocale(report, locale)
  const description = descriptionForLocale(report, locale)
  const ProviderIcon = report.provider === 'grafana' ? Activity : BarChart3

  const card = (
    <Card className={ready ? 'transition hover:shadow-md cursor-pointer h-full' : 'opacity-70 h-full'}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 min-w-0">
            {ready ? (
              <ProviderIcon className="h-5 w-5 text-primary flex-shrink-0" />
            ) : (
              <Construction className="h-5 w-5 text-amber-500 flex-shrink-0" />
            )}
            <span className="truncate">{title}</span>
          </span>
          <Badge variant={RLS_BADGE_VARIANT[report.rls_mode]} className="flex-shrink-0">
            {t(`rls.${report.rls_mode}`, { defaultValue: report.rls_mode })}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground line-clamp-2">{description}</p>
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline" className="text-[10px] font-mono">
            {report.provider === 'grafana' ? 'Grafana' : 'Looker'}
          </Badge>
          <span className="font-mono text-[10px]">{report.default_time_range}</span>
        </div>
        {!ready && (
          <Link
            href={`/${locale}/dashboard/admin/dashboards/config`}
            className="mt-3 inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 underline"
          >
            <Settings className="h-3 w-3" />
            {t('awaitingSetup')}
          </Link>
        )}
      </CardContent>
    </Card>
  )

  if (!ready) return <div>{card}</div>

  // Grafana Cloud Free blocks iframe embedding (frame-ancestors 'none' +
  // X-Frame-Options: deny). Open the dashboard directly in a new tab
  // instead of going through an internal page that would also fail.
  // Looker Studio dashboards (services catalog) keep the internal route
  // because Looker allows iframe embedding.
  if (report.provider === 'grafana' && report.embed_url) {
    return (
      <a
        href={report.embed_url}
        target="_blank"
        rel="noopener noreferrer"
        title={report.embed_url}
      >
        {card}
      </a>
    )
  }
  return (
    <Link href={`/${locale}/dashboard/admin/dashboards/${report.dashboard_id}`}>
      {card}
    </Link>
  )
}

export function DashboardsListing() {
  const t = useTranslations('admin.dashboards')
  const params = useParams()
  const locale = (params?.locale as string) || 'es'
  const { data, isLoading, error } = useReportsConfig()

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((i) => <Skeleton key={i} className="h-44 w-full" />)}
      </div>
    )
  }

  if (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    if (status === 403) {
      return (
        <Alert variant="destructive">
          <Lock className="h-4 w-4" />
          <AlertTitle>{t('forbiddenTitle')}</AlertTitle>
          <AlertDescription>{t('forbiddenHelp')}</AlertDescription>
        </Alert>
      )
    }
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{t('errorTitle')}</AlertTitle>
        <AlertDescription>
          {(error as Error)?.message ?? t('errorGeneric')}
        </AlertDescription>
      </Alert>
    )
  }

  const reports = data?.reports ?? []

  if (reports.length === 0) {
    return (
      <Alert>
        <Construction className="h-4 w-4" />
        <AlertTitle>{t('emptyTitle')}</AlertTitle>
        <AlertDescription>{t('emptyHelp')}</AlertDescription>
      </Alert>
    )
  }

  // Group by category, with an "ungrouped" bucket for rows with category=null
  const grouped: Record<string, DashboardReportEntry[]> = {}
  for (const r of reports) {
    const cat = r.category ?? 'ungrouped'
    grouped[cat] = grouped[cat] ?? []
    grouped[cat].push(r)
  }

  // Determine ordering: known categories first (CATEGORY_ORDER), then ungrouped
  const orderedCats: string[] = [
    ...CATEGORY_ORDER.filter((c) => grouped[c]?.length > 0),
    ...(grouped.ungrouped?.length > 0 ? ['ungrouped'] : []),
  ]

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Link
          href={`/${locale}/dashboard/admin/dashboards/config`}
          className="inline-flex items-center gap-1.5 rounded-md border bg-card px-3 py-2 text-sm font-medium hover:bg-accent transition"
        >
          <Settings className="h-4 w-4" />
          {t('configureLink')}
        </Link>
      </div>

      {orderedCats.map((cat) => (
        <section key={cat} className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {t(`category.${cat}`, { defaultValue: cat })}
            <span className="ml-2 text-xs font-normal text-muted-foreground/70">
              ({grouped[cat].length})
            </span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {grouped[cat].map((report) => (
              <ReportCard
                key={report.dashboard_id}
                report={report}
                locale={locale}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
