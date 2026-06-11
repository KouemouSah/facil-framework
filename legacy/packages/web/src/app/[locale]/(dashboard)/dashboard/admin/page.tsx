'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  StatsCards,
  QuickActions,
  OperationalOverview,
  SystemStatusBar,
} from '@/modules/admin/components'

export default function AdminDashboard() {
  const t = useTranslations('admin')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t('pageTitle')}</h1>
        <p className="text-gray-600 mt-2">{t('pageSubtitle')}</p>
      </div>

      {/* Stats Cards (original — untouched) */}
      <StatsCards />

      {/* Quick Actions (original — untouched) */}
      <QuickActions />

      {/* Charts Grid — replaces Actividad Reciente + Estado del Sistema */}
      <OperationalOverview />

      {/* System Status — compact single-line bar */}
      <SystemStatusBar />
    </div>
  )
}
