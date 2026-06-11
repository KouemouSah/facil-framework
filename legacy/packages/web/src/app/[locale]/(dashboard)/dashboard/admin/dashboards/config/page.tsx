'use client'

import React from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'

import { DashboardConfigsListPage } from '@/modules/dashboards-admin'

export default function AdminDashboardsConfigPage() {
  const t = useTranslations('admin.dashboards.config')
  const params = useParams()
  const locale = (params?.locale as string) || 'es'

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href={`/${locale}/dashboard/admin/dashboards`}
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition mb-2"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            {t('backToList')}
          </Link>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground mt-1">{t('subtitle')}</p>
        </div>
      </div>
      <DashboardConfigsListPage />
    </div>
  )
}
