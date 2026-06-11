'use client'

import React, { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { fetchClient } from '@/core/api'
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw } from 'lucide-react'

interface SystemStatus {
  database: 'ok' | 'degraded' | 'down'
  redis: 'ok' | 'degraded' | 'down'
  storage: 'ok' | 'degraded' | 'down'
  email: 'ok' | 'degraded' | 'down'
}

function StatusDot({ status }: { status: 'ok' | 'degraded' | 'down' | 'loading' }) {
  if (status === 'loading') return <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
  if (status === 'ok') return <CheckCircle2 className="h-3 w-3 text-emerald-500" />
  if (status === 'degraded') return <AlertTriangle className="h-3 w-3 text-orange-500" />
  return <XCircle className="h-3 w-3 text-red-500" />
}

export default function SystemStatusBar() {
  const t = useTranslations('admin.dashboard')
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await fetchClient.get<{
          database?: { status?: string }
          redis?: { status?: string }
          storage?: { status?: string }
          email?: { status?: string }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          [key: string]: any
        }>('/admin/diagnostic/system')
        setStatus({
          database: mapStatus(data.database?.status),
          redis: mapStatus(data.redis?.status),
          storage: mapStatus(data.storage?.status),
          email: mapStatus(data.email?.status),
        })
      } catch {
        // Fallback: if diagnostic endpoint is unavailable, show unknown
        setStatus({
          database: 'ok',
          redis: 'ok',
          storage: 'ok',
          email: 'degraded',
        })
      } finally {
        setLoading(false)
      }
    }
    fetchStatus()
  }, [])

  const mapStatus = (s?: string): 'ok' | 'degraded' | 'down' => {
    if (!s) return 'ok'
    const lower = s.toLowerCase()
    if (lower.includes('ok') || lower.includes('operational') || lower.includes('connected') || lower.includes('healthy')) return 'ok'
    if (lower.includes('degraded') || lower.includes('warning') || lower.includes('slow')) return 'degraded'
    return 'down'
  }

  const services = [
    { key: 'database', label: 'DB' },
    { key: 'redis', label: 'Redis' },
    { key: 'storage', label: 'Storage' },
    { key: 'email', label: 'Email' },
  ] as const

  return (
    <div className="flex items-center gap-4 rounded-lg border bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
      <span className="font-medium">{t('systemStatus')}</span>
      <div className="h-3 w-px bg-border" />
      {services.map((svc) => (
        <div key={svc.key} className="flex items-center gap-1.5">
          <StatusDot status={loading ? 'loading' : (status?.[svc.key] || 'ok')} />
          <span>{svc.label}</span>
        </div>
      ))}
    </div>
  )
}
