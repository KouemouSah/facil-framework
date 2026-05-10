'use client'

/**
 * OMS Agent Escalations — Read-only view of obligations the agent has escalated.
 *
 * Shows escalated service_requests linked to bundle obligations.
 * No action buttons — supervisor handles resolution.
 * Pattern: mirrors treasury/escalations/page.tsx for OMS context.
 *
 * @route /[locale]/dashboard/agent/oms/escalations
 */

import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import {
  ArrowLeft, AlertTriangle, Clock, CheckCircle2, RefreshCw,
  Building2, Calendar,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import apiClient from '@/core/api/client'

interface EscalationItem {
  id: string
  reference: string
  workflowCode: string
  status: string
  escalationReason: string
  escalatedAt: string
  assignedToName: string | null
  escalationStatus: string
}

function fmtDate(d: string | null | undefined, locale = 'es-GQ'): string {
  if (!d) return '—'
  try { return new Date(d).toLocaleDateString(locale, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) }
  catch { return d }
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800',
  in_review: 'bg-blue-100 text-blue-800',
  resolved: 'bg-green-100 text-green-800',
  reassigned: 'bg-purple-100 text-purple-800',
}

export default function OmsEscalationsPage() {
  const t = useTranslations('oms')
  const locale = useLocale()
  const router = useRouter()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['oms-my-escalations'],
    queryFn: async () => {
      const { data: resp } = await apiClient.get('/agent/requests', {
        params: { escalated: true, page_size: 50 },
      })
      // Transform snake_case → camelCase
      const items = (resp.items || resp.requests || []).map((r: Record<string, unknown>) => ({
        id: r.id,
        reference: r.reference,
        workflowCode: r.workflow_code,
        status: r.status,
        escalationReason: r.escalation_reason || '',
        escalatedAt: r.escalated_at,
        assignedToName: r.assigned_to_name || null,
        escalationStatus: r.escalated ? (r.assigned_to ? 'in_review' : 'pending') : 'resolved',
      }))
      return items as EscalationItem[]
    },
    staleTime: 30_000,
  })

  const escalations = data ?? []
  const pendingCount = escalations.filter(e => e.escalationStatus === 'pending').length
  const _resolvedCount = escalations.filter(e => e.escalationStatus === 'resolved').length

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push(`/${locale}/dashboard/agent/oms`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            {t('escalations.myTitle', { defaultValue: 'Mis Escalaciones' })}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t('escalations.mySubtitle', { defaultValue: 'Obligaciones escaladas a su supervisor' })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pendingCount > 0 && (
            <Badge variant="destructive" className="text-xs">{pendingCount} {t('escalations.pending', { defaultValue: 'pendientes' })}</Badge>
          )}
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">{t('escalations.reference', { defaultValue: 'Referencia' })}</TableHead>
                <TableHead className="text-xs">{t('escalations.reason', { defaultValue: 'Motivo' })}</TableHead>
                <TableHead className="text-xs">{t('escalations.date', { defaultValue: 'Fecha' })}</TableHead>
                <TableHead className="text-xs">{t('escalations.assignedTo', { defaultValue: 'Asignado a' })}</TableHead>
                <TableHead className="text-xs">{t('escalations.status', { defaultValue: 'Estado' })}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow><TableCell colSpan={5} className="text-center py-8">...</TableCell></TableRow>
              ) : escalations.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-12 text-muted-foreground">
                    <CheckCircle2 className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p>{t('escalations.noEscalations', { defaultValue: 'No tiene escalaciones activas' })}</p>
                  </TableCell>
                </TableRow>
              ) : escalations.map(esc => (
                <TableRow key={esc.id}>
                  <TableCell className="text-xs">
                    <div className="flex items-center gap-1.5">
                      <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="font-mono font-medium">{esc.reference}</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">{esc.workflowCode}</span>
                  </TableCell>
                  <TableCell className="text-xs max-w-[200px] truncate">{esc.escalationReason || '—'}</TableCell>
                  <TableCell className="text-xs">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {fmtDate(esc.escalatedAt, locale)}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs">{esc.assignedToName || '—'}</TableCell>
                  <TableCell>
                    <Badge className={`text-[10px] ${STATUS_COLORS[esc.escalationStatus] || 'bg-gray-100'}`}>
                      {esc.escalationStatus === 'pending' && <Clock className="h-3 w-3 mr-1" />}
                      {esc.escalationStatus === 'in_review' && <AlertTriangle className="h-3 w-3 mr-1" />}
                      {esc.escalationStatus === 'resolved' && <CheckCircle2 className="h-3 w-3 mr-1" />}
                      {esc.escalationStatus}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
