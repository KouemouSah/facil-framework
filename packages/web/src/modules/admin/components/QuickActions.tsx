/**
 * Quick Actions Component
 * Quick access buttons for common admin tasks with i18n support
 *
 * @module modules/admin/components
 * @author Claude Code
 * @date 2025-11-24
 */

'use client'

import React from 'react'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'
import { UserCog, ShieldPlus, KeyRound, FileText } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function QuickActions() {
  const locale = useLocale()
  const t = useTranslations('admin.dashboard')

  const quickActions = [
    {
      title: t('newAgent'),
      description: t('newAgentDesc'),
      icon: UserCog,
      href: `/${locale}/dashboard/admin/agents/new`,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: t('newRole'),
      description: t('newRoleDesc'),
      icon: ShieldPlus,
      href: `/${locale}/dashboard/admin/roles`,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      title: t('managePermissions'),
      description: t('managePermissionsDesc'),
      icon: KeyRound,
      href: `/${locale}/dashboard/admin/permissions`,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      title: t('auditLogs'),
      description: t('auditLogsDesc'),
      icon: FileText,
      href: `/${locale}/dashboard/admin/audit-logs`,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('quickActions')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickActions.map((action) => {
            const Icon = action.icon
            return (
              <Link key={action.title} href={action.href}>
                <div className="group cursor-pointer p-4 rounded-lg border-2 border-gray-200 hover:border-primary hover:shadow-md transition-all">
                  <div className={`inline-flex p-2 rounded-lg ${action.bgColor} mb-3`}>
                    <Icon className={`h-5 w-5 ${action.color}`} />
                  </div>
                  <h3 className="font-semibold text-sm mb-1">{action.title}</h3>
                  <p className="text-xs text-gray-600">{action.description}</p>
                </div>
              </Link>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
