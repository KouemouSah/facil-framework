'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { ChevronLeft, AlertCircle, Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { DashboardEmbed, useReportsConfig } from '@/modules/dashboards-admin'

export default function AdminDashboardEmbedPage() {
  const t = useTranslations('admin.dashboards')
  const params = useParams()
  const locale = (params?.locale as string) || 'es'
  const dashboardId = params?.id as string
  const { data, isLoading, error } = useReportsConfig()

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[calc(100vh-12rem)] w-full" />
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

  const report = data?.reports.find((r) => r.dashboard_id === dashboardId)

  if (!report) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{t('notFoundTitle')}</AlertTitle>
        <AlertDescription>
          {t('notFoundHelp', { id: dashboardId })}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <Button variant="ghost" asChild className="gap-1">
        <Link href={`/${locale}/dashboard/admin/dashboards`}>
          <ChevronLeft className="h-4 w-4" />
          {t('backToList')}
        </Link>
      </Button>
      <DashboardEmbed report={report} />
    </div>
  )
}
