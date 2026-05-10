'use client'

import { useTranslations } from 'next-intl'
import { Loader2, AlertCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AuditLogItem } from './AuditLogItem'
import { useAuditLogs } from '../hooks/useAuditLogs'
import type { AuditLog } from '../types'

interface AuditLogListProps {
  filters?: {
    action?: string
    user_id?: string
    entity_type?: string
    search?: string
    start_date?: string
    end_date?: string
  }
  onSelect?: (log: AuditLog) => void
}

export function AuditLogList({ filters, onSelect }: AuditLogListProps) {
  const t = useTranslations('admin.auditLogs')

  const { data, isLoading, error } = useAuditLogs({
    action: filters?.action,
    user_id: filters?.user_id,
    entity_type: filters?.entity_type,
    search: filters?.search,
    start_date: filters?.start_date,
    end_date: filters?.end_date,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">Cargando...</span>
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {t('errorLoading')}: {error.message}
        </AlertDescription>
      </Alert>
    )
  }

  const items = data?.items || []

  if (items.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">{t('noLogs')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {items.map((log) => (
        <AuditLogItem
          key={log.id}
          log={log}
          onClick={() => onSelect?.(log)}
        />
      ))}
    </div>
  )
}
