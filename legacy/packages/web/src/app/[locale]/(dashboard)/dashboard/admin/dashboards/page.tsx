'use client'

import { useTranslations } from 'next-intl'
import { DashboardsListing } from '@/modules/dashboards-admin'

export default function AdminDashboardsLandingPage() {
  const t = useTranslations('admin.dashboards')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground">{t('subtitle')}</p>
      </div>
      <DashboardsListing />
    </div>
  )
}
