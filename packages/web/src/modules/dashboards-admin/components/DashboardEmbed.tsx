'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertCircle, Construction, BarChart3, Activity, ExternalLink, Info,
} from 'lucide-react'
import type { DashboardReportEntry } from '../types'

const LOOKER_BASE = 'https://lookerstudio.google.com'

/**
 * Fallback Looker Studio URL builder — used only when the backend has not
 * pre-computed embed_url (legacy data, env-fallback path).
 */
function buildLookerEmbedUrl(reportId: string, pageId: string | null): string {
  const path = pageId
    ? `/embed/reporting/${reportId}/page/${pageId}`
    : `/embed/reporting/${reportId}`
  return `${LOOKER_BASE}${path}`
}

interface Props {
  report: DashboardReportEntry
}

/**
 * Renders the dashboard inside an iframe — works for BOTH Looker Studio and
 * Grafana via the backend-computed `embed_url` field.
 *
 * Provider-aware behaviour:
 *   - Backend has pre-built `embed_url` → use it directly (preferred path)
 *   - No embed_url AND provider=looker_studio AND looker_report_id → fallback build
 *   - No embed_url AND provider=grafana → "Grafana not configured" placeholder
 *   - Nothing usable → "Awaiting setup" placeholder
 */
export function DashboardEmbed({ report }: Props) {
  const t = useTranslations('admin.dashboards')

  // Compute the iframe URL with priority: embed_url > legacy fallback.
  let iframeUrl: string | null = null
  if (report.embed_url) {
    iframeUrl = report.embed_url
  } else if (report.provider === 'looker_studio' && report.looker_report_id) {
    iframeUrl = buildLookerEmbedUrl(report.looker_report_id, report.looker_page_id)
  }
  // For provider=grafana without embed_url, iframeUrl stays null — the
  // backend couldn't build a URL (GRAFANA_BASE_URL env var unset).

  if (!iframeUrl) {
    const isGrafanaUnset =
      report.provider === 'grafana' && !report.embed_url
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Construction className="h-5 w-5 text-amber-500" />
            {report.label}
            <Badge variant="outline" className="ml-2 font-mono text-xs">
              {report.provider}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>
              {isGrafanaUnset
                ? t('grafanaNotConfigured', { defaultValue: 'Grafana not configured' })
                : t('awaitingSetup')}
            </AlertTitle>
            <AlertDescription>
              {isGrafanaUnset
                ? t('grafanaNotConfiguredHelp', {
                    defaultValue:
                      'GRAFANA_BASE_URL is not set on the backend, or the dashboard UID is missing.',
                  })
                : t('awaitingSetupHelp', { id: report.dashboard_id })}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  const ProviderIcon = report.provider === 'grafana' ? Activity : BarChart3
  const providerLabel =
    report.provider === 'grafana' ? 'Grafana' : 'Looker Studio'

  // ---------------------------------------------------------------------
  // Grafana Cloud (Free tier) sends `frame-ancestors 'none'` + `X-Frame-
  // Options: deny`, which makes iframe embedding impossible regardless of
  // our frontend CSP allow-list. The setting is locked on Free tier
  // (PUT /api/admin/settings is silently rejected) and Public Dashboards
  // would expose sensitive payment/agent data without auth.
  //
  // Workaround: render an "Open in Grafana" CTA that opens the dashboard
  // in a new tab. The admin's existing Grafana session (SSO) handles auth
  // there. UX is one click vs zero, in exchange for: no broken iframes,
  // no public exposure, no paid plan upgrade ($8/mo).
  //
  // Looker Studio does NOT send frame-ancestors, so its iframe still works
  // — kept the iframe path for Looker dashboards (services catalog).
  // ---------------------------------------------------------------------
  if (report.provider === 'grafana') {
    return (
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{report.label}</h2>
            <p className="text-muted-foreground text-sm">{report.description}</p>
          </div>
          <Badge variant="outline" className="font-mono text-xs flex items-center gap-1">
            <ProviderIcon className="h-3 w-3" />
            {providerLabel}
          </Badge>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-5 w-5 text-primary" />
              {t('grafanaOpenTitle', { defaultValue: 'Open this dashboard in Grafana' })}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <Info className="h-4 w-4" />
              <AlertTitle>
                {t('grafanaIframeBlockedTitle', {
                  defaultValue: 'Embedded view not available',
                })}
              </AlertTitle>
              <AlertDescription>
                {t('grafanaIframeBlockedHelp', {
                  defaultValue:
                    'Grafana Cloud blocks iframe embedding for security (frame-ancestors policy). Click below to open the dashboard in a new tab — your Grafana session will authenticate you automatically.',
                })}
              </AlertDescription>
            </Alert>

            <div className="flex items-center gap-3">
              <Button asChild size="lg" className="gap-2">
                <a
                  href={iframeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="h-4 w-4" />
                  {t('grafanaOpenBtn', { defaultValue: 'Open in Grafana' })}
                </a>
              </Button>
              <span className="text-xs text-muted-foreground font-mono">
                {report.grafana_dashboard_uid}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{report.label}</h2>
          <p className="text-muted-foreground text-sm">{report.description}</p>
        </div>
        <Badge variant="outline" className="font-mono text-xs flex items-center gap-1">
          <ProviderIcon className="h-3 w-3" />
          {providerLabel}
        </Badge>
      </div>
      <div className="rounded-lg border bg-card overflow-hidden">
        <iframe
          src={iframeUrl}
          title={report.label}
          className="w-full min-h-[calc(100vh-12rem)] border-0"
          allow="fullscreen"
          // OWASP iframe sandbox — Looker Studio needs scripts + same-origin
          // for the React UI to work; we intentionally do not allow forms
          // or top-navigation. Grafana dashboards take the early-return
          // branch above (Grafana Cloud blocks iframes via CSP).
          sandbox="allow-scripts allow-same-origin allow-popups"
        />
      </div>
    </div>
  )
}
