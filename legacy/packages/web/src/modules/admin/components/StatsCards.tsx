/**
 * Stats Cards Component
 * Display key metrics for admin dashboard with real backend data
 *
 * BACKEND INTEGRATION:
 * - Users stats: GET /api/v1/admin/users/stats (users-admin module)
 * - Audit stats: GET /api/v1/audit-logs/stats (audit-logs-admin module)
 * - Roles: GET /api/v1/roles (permissions-admin module)
 * - Permissions: GET /api/v1/permissions (permissions-admin module)
 *
 * @module modules/admin/components
 * @author Claude Code
 * @date 2025-11-27
 */

'use client'

import React, { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Users, Shield, Key, Activity, AlertTriangle, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import usersApi from '@/modules/users-admin/services/api'
import auditLogsApi from '@/modules/audit-logs-admin/services/api'
import { permissionsApi, rolesApi } from '@/modules/permissions-admin/services/api'

interface UserStats {
  // Backend returns snake_case, transformKeys converts to camelCase
  totalUsers?: number
  total_users?: number  // fallback
  activeUsers?: number
  active_users?: number  // fallback
  newUsersThisMonth?: number
  new_users_this_month?: number  // fallback
  usersByRole?: Record<string, number>
  users_by_role?: Record<string, number>  // fallback
  usersByStatus?: Record<string, number>
  users_by_status?: Record<string, number>  // fallback
}

interface AuditStats {
  total_logs: number
  by_action: Record<string, number>
  by_entity_type: Record<string, number>
}

export default function StatsCards() {
  const t = useTranslations('admin.dashboard')
  const [userStats, setUserStats] = useState<UserStats | null>(null)
  const [auditStats, setAuditStats] = useState<AuditStats | null>(null)
  const [totalRoles, setTotalRoles] = useState<number>(0)
  const [totalPermissions, setTotalPermissions] = useState<number>(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchStats = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Calculate 24h ago for activity filter
        const now = new Date()
        const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000)
        const startDate = twentyFourHoursAgo.toISOString()

        // Fetch all stats in parallel
        const [usersData, auditData, rolesData, permissionsData] = await Promise.allSettled([
          usersApi.getStats(),
          auditLogsApi.getStats({ start_date: startDate }), // Filter for last 24h
          rolesApi.getAll(),
          permissionsApi.getAll(),
        ])

        if (usersData.status === 'fulfilled') {
          const data = usersData.value as UserStats
          setUserStats({
            totalUsers: data.totalUsers ?? data.total_users ?? 0,
            activeUsers: data.activeUsers ?? data.active_users ?? 0,
            newUsersThisMonth: data.newUsersThisMonth ?? data.new_users_this_month ?? 0,
            usersByRole: data.usersByRole ?? data.users_by_role ?? {},
            usersByStatus: data.usersByStatus ?? data.users_by_status ?? {},
          })
        }

        if (auditData.status === 'fulfilled') {
          setAuditStats(auditData.value)
        }

        if (rolesData.status === 'fulfilled') {
          // rolesApi.getAll() returns Role[] array
          setTotalRoles(rolesData.value?.length ?? 0)
        }

        if (permissionsData.status === 'fulfilled') {
          // permissionsApi.getAll() returns Permission[] array
          setTotalPermissions(permissionsData.value?.length ?? 0)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error fetching stats')
      } finally {
        setIsLoading(false)
      }
    }

    fetchStats()
  }, [])

  // Calculate derived stats from real API data
  const totalUsersCount = userStats?.totalUsers ?? userStats?.total_users ?? 0
  const activeUsers = userStats?.activeUsers ?? userStats?.active_users ?? 0
  const activityCount = auditStats?.total_logs || 0

  const stats = [
    {
      name: t('totalUsersLabel'),
      value: totalUsersCount.toLocaleString(),
      change: activeUsers && totalUsersCount ? `${Math.round((activeUsers / totalUsersCount) * 100)}% activos` : '0%',
      changeType: 'positive' as const,
      icon: Users,
      description: t('vsLastMonth'),
    },
    {
      name: t('activeRolesLabel'),
      value: totalRoles.toString(),
      change: `${totalRoles} roles`,
      changeType: 'neutral' as const,
      icon: Shield,
      description: t('rolesDescription'),
    },
    {
      name: t('permissionsLabel'),
      value: totalPermissions.toString(),
      change: totalPermissions > 0 ? `${totalPermissions} permisos` : '0',
      changeType: 'neutral' as const,
      icon: Key,
      description: t('completeCatalog'),
    },
    {
      name: t('activity24hLabel'),
      value: activityCount.toLocaleString(),
      change: auditStats ? `${Object.keys(auditStats.by_action).length} types` : '0',
      changeType: 'neutral' as const,
      icon: Activity,
      description: t('actionsRecorded'),
    },
  ]

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="flex items-center justify-center h-24">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="col-span-full">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat) => {
        const Icon = stat.icon
        return (
          <Card key={stat.name}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-600">{stat.name}</p>
                  <p className="text-2xl font-bold text-gray-900 mt-2">{stat.value}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span
                      className={`text-xs font-medium ${
                        stat.changeType === 'positive'
                          ? 'text-green-600'
                          : 'text-gray-600'
                      }`}
                    >
                      {stat.change}
                    </span>
                    <span className="text-xs text-gray-500">{stat.description}</span>
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <div className="bg-primary/10 p-3 rounded-lg">
                    <Icon className="h-6 w-6 text-primary" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
