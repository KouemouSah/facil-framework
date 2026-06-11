'use client'

import React, { useEffect, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { RefreshCw, AlertTriangle, Activity } from 'lucide-react'
import auditLogsApi from '@/modules/audit-logs-admin/services/api'
import type { AuditLog } from '@/modules/audit-logs-admin/types'

export default function RecentActivity() {
  const t = useTranslations('admin.dashboard')
  const locale = useLocale()
  const [activities, setActivities] = useState<AuditLog[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchActivities = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await auditLogsApi.getAll({
          page: 1,
          page_size: 5,
        })
        setActivities(response.items || [])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error fetching activities')
      } finally {
        setIsLoading(false)
      }
    }

    fetchActivities()
  }, [])

  const getActionColor = (action: string) => {
    const actionLower = action.toLowerCase()
    if (actionLower.includes('create') || actionLower.includes('register') || actionLower.includes('submitted')) {
      return 'bg-green-100 text-green-800'
    }
    if (actionLower.includes('update') || actionLower.includes('modify') || actionLower.includes('approved')) {
      return 'bg-blue-100 text-blue-800'
    }
    if (actionLower.includes('delete') || actionLower.includes('remove') || actionLower.includes('rejected')) {
      return 'bg-red-100 text-red-800'
    }
    if (actionLower.includes('grant') || actionLower.includes('permission')) {
      return 'bg-purple-100 text-purple-800'
    }
    if (actionLower.includes('login') || actionLower.includes('auth')) {
      return 'bg-yellow-100 text-yellow-800'
    }
    return 'bg-gray-100 text-gray-800'
  }

  const formatTimeAgo = (timestamp: string) => {
    try {
      const now = Date.now()
      const date = new Date(timestamp).getTime()
      const diffSec = Math.floor((now - date) / 1000)
      const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto', style: 'short' })
      if (diffSec < 60) return rtf.format(-diffSec, 'second')
      const diffMin = Math.floor(diffSec / 60)
      if (diffMin < 60) return rtf.format(-diffMin, 'minute')
      const diffHrs = Math.floor(diffMin / 60)
      if (diffHrs < 24) return rtf.format(-diffHrs, 'hour')
      const diffDays = Math.floor(diffHrs / 24)
      return rtf.format(-diffDays, 'day')
    } catch {
      return timestamp
    }
  }

  const getUserInitials = (userId: string | null) => {
    if (!userId) return '??'
    return userId.substring(0, 2).toUpperCase()
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>{t('recentActivityTitle')}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader><CardTitle>{t('recentActivityTitle')}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-destructive py-4">
            <AlertTriangle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (activities.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle>{t('recentActivityTitle')}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <Activity className="h-12 w-12 mb-4 opacity-50" />
            <p>{t('noRecentActivity')}</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader><CardTitle>{t('recentActivityTitle')}</CardTitle></CardHeader>
      <CardContent>
        <div className="space-y-4">
          {activities.map((activity) => (
            <div key={activity.id} className="flex items-start gap-4">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-primary/10 text-primary text-xs">
                  {getUserInitials(activity.user_id)}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate max-w-[120px]">
                    {activity.user_id ? `${activity.user_id.substring(0, 8)}...` : '-'}
                  </span>
                  <Badge variant="outline" className={getActionColor(activity.action)}>
                    {activity.action.replace(/_/g, ' ')}
                  </Badge>
                </div>
                <p className="text-xs text-gray-600">
                  {activity.entity_type && (
                    <>
                      <span className="font-mono">{activity.entity_type}</span>
                      {activity.entity_id && (
                        <span className="text-gray-400"> / {activity.entity_id.substring(0, 8)}...</span>
                      )}
                    </>
                  )}
                </p>
                <p className="text-xs text-gray-500">{formatTimeAgo(activity.created_at)}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
