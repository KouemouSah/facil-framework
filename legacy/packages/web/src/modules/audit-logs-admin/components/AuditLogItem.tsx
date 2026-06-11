'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { User, Globe, Monitor, ChevronRight } from 'lucide-react'
import { AuditActionBadge } from './AuditActionBadge'
import type { AuditLog } from '../types'

interface AuditLogItemProps {
  log: AuditLog
  onClick?: () => void
}

export function AuditLogItem({ log, onClick }: AuditLogItemProps) {
  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          <ChevronRight className="h-5 w-5 mt-0.5 text-muted-foreground" />

          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <AuditActionBadge action={log.action} />
              <span className="text-xs text-muted-foreground">
                {new Date(log.created_at).toLocaleString('es-GQ')}
              </span>
            </div>

            {log.user_id && (
              <div className="flex items-center gap-2 text-sm">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium font-mono text-xs">{log.user_id.substring(0, 12)}...</span>
              </div>
            )}

            {log.entity_type && (
              <div className="text-sm text-muted-foreground">
                <Badge variant="outline" className="text-xs">{log.entity_type}</Badge>
                {log.entity_id && (
                  <span className="ml-2 font-mono text-xs">{log.entity_id.substring(0, 12)}...</span>
                )}
              </div>
            )}

            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
              {log.ip_address && (
                <div className="flex items-center gap-1">
                  <Globe className="h-3 w-3" />
                  <span>{log.ip_address}</span>
                </div>
              )}
              {log.user_agent && (
                <div className="flex items-center gap-1">
                  <Monitor className="h-3 w-3" />
                  <span className="truncate max-w-[200px]">{log.user_agent}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
