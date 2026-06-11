'use client'

/**
 * Supervisor Inspection Detail — Full report view
 *
 * Shows all inspection data: agent notes, activity comparison,
 * photos, GPS, seal status, payment, timeline.
 * Read-only for supervisors (actions handled in pending-seals page).
 */

import { useCallback, useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  ArrowLeft, Building2, User, Calendar, MapPin, Camera,
  FileText, CheckCircle2, XCircle, AlertTriangle, Clock,
  Shield, MessageSquare, Eye, RefreshCw,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { inspectionApi } from '@/modules/inspections/services/api'
import type { Inspection } from '@/modules/inspections/types'

const RESULT_CONFIG: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
  conforme: { color: 'bg-green-100 text-green-800', icon: CheckCircle2, label: 'Conforme' },
  non_conforme: { color: 'bg-red-100 text-red-800', icon: XCircle, label: 'Non conforme' },
  pending: { color: 'bg-yellow-100 text-yellow-800', icon: Clock, label: 'En attente' },
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  in_progress: { color: 'bg-blue-100 text-blue-800', label: 'En cours' },
  completed: { color: 'bg-green-100 text-green-800', label: 'Termine' },
  mise_en_demeure: { color: 'bg-orange-100 text-orange-800', label: 'Mise en demeure' },
  seal_proposed: { color: 'bg-purple-100 text-purple-800', label: 'Scelle propose' },
  seal_approved: { color: 'bg-emerald-100 text-emerald-800', label: 'Scelle approuve' },
  seal_rejected: { color: 'bg-red-100 text-red-800', label: 'Scelle rejete' },
  cancelled: { color: 'bg-gray-100 text-gray-800', label: 'Annule' },
}

export default function InspectionDetailPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const { toast } = useToast()
  const t = useTranslations('inspection')
  const inspectionId = params.id as string

  const [data, setData] = useState<Inspection | null>(null)
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const result = await inspectionApi.get(inspectionId)
      setData(result)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [inspectionId, toast, t])

  useEffect(() => { fetch() }, [fetch])

  if (loading) {
    return (
      <div className="space-y-4 p-4 max-w-5xl mx-auto">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <FileText className="h-12 w-12 mb-3 opacity-40" />
        <p>{t('detail.notFound')}</p>
        <Button variant="outline" className="mt-3" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-1" /> {t('common.back')}
        </Button>
      </div>
    )
  }

  const resultCfg = RESULT_CONFIG[data.result || 'pending'] || RESULT_CONFIG.pending
  const statusCfg = STATUS_CONFIG[data.status] || STATUS_CONFIG.in_progress
  const ResultIcon = resultCfg.icon
  const fmtDate = (d: string) => new Date(d).toLocaleDateString(locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ', { day: '2-digit', month: 'short', year: 'numeric' })

  return (
    <div className="space-y-4 p-4 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="h-8 w-8"
          onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold flex items-center gap-2 flex-wrap">
            <Building2 className="h-5 w-5 shrink-0" />
            <span className="truncate">{data.company_name || 'Inspection'}</span>
            <Badge className={`text-xs ${resultCfg.color}`}>
              <ResultIcon className="h-3 w-3 mr-1" />{resultCfg.label}
            </Badge>
            <Badge className={`text-xs ${statusCfg.color}`}>{statusCfg.label}</Badge>
          </h1>
          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
            {data.company_nif && <span className="font-mono">NIF: {data.company_nif}</span>}
            <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{fmtDate(data.inspection_date)}</span>
            <span className="flex items-center gap-1"><User className="h-3 w-3" />{data.agent_name || 'Agent'}</span>
            {data.entity_code && <span className="font-mono text-primary">{data.entity_code}</span>}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={fetch}>
          <RefreshCw className="h-3.5 w-3.5 mr-1" /> {t('common.refresh')}
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-3">
          <div className="text-xs text-muted-foreground">{t('detail.obligations')}</div>
          <p className="text-xl font-bold">{data.unpaid_obligations_count}/{data.total_obligations_count}</p>
          <p className="text-xs text-muted-foreground">{t('detail.unpaid')}</p>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-muted-foreground">{t('detail.amount')}</div>
          <p className="text-xl font-bold text-red-700">{Number(data.unpaid_obligations_amount || 0).toLocaleString()} XAF</p>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-muted-foreground">{t('detail.payment')}</div>
          <p className="text-xl font-bold">{data.payment_collected ?
            <span className="text-green-700">{Number(data.payment_amount || 0).toLocaleString()} XAF</span> :
            <span className="text-muted-foreground">--</span>}
          </p>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-muted-foreground">GPS</div>
          <p className="text-sm font-mono">
            {data.gps_latitude && data.gps_longitude
              ? `${Number(data.gps_latitude).toFixed(4)}, ${Number(data.gps_longitude).toFixed(4)}`
              : '--'}
          </p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Notes + Activity (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          {/* Agent Notes */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                {t('detail.agentNotes')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.notes ? (
                <p className="text-sm whitespace-pre-wrap bg-muted/30 rounded-lg p-3">{data.notes}</p>
              ) : (
                <p className="text-sm text-muted-foreground italic">{t('detail.noNotes')}</p>
              )}
            </CardContent>
          </Card>

          {/* Activity Comparison */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Eye className="h-4 w-4" />
                {t('detail.activityComparison')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">{t('detail.declared')}</p>
                  <p className="text-sm font-medium bg-blue-50 dark:bg-blue-950/20 rounded p-2">
                    {data.activity_declared || '--'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">{t('detail.observed')}</p>
                  <p className="text-sm font-medium bg-amber-50 dark:bg-amber-950/20 rounded p-2">
                    {data.activity_observed || '--'}
                  </p>
                </div>
              </div>
              <div className="mt-2 flex items-center gap-2 text-xs">
                {data.activity_conforme === true && (
                  <Badge className="bg-green-100 text-green-800"><CheckCircle2 className="h-3 w-3 mr-1" />{t('detail.activityMatch')}</Badge>
                )}
                {data.activity_conforme === false && (
                  <Badge className="bg-red-100 text-red-800"><XCircle className="h-3 w-3 mr-1" />{t('detail.activityMismatch')}</Badge>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Seal Section */}
          {(data.seal_applied || data.seal_notes || data.seal_reason) && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  {t('detail.sealSection')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {data.seal_reason && <p className="text-sm"><span className="text-muted-foreground">{t('detail.sealReason')}:</span> {data.seal_reason}</p>}
                {data.seal_notes && <p className="text-sm bg-muted/30 rounded p-2">{data.seal_notes}</p>}
                {data.seal_rejection_reason && <p className="text-sm text-red-600">{t('detail.rejectionReason')}: {data.seal_rejection_reason}</p>}
                {data.seal_approved_at && <p className="text-xs text-muted-foreground">{t('detail.approvedAt')}: {fmtDate(data.seal_approved_at)}</p>}
              </CardContent>
            </Card>
          )}

          {/* MED Section */}
          {data.mise_en_demeure_issued && (
            <Card className="border-orange-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-orange-700">
                  <AlertTriangle className="h-4 w-4" />
                  {t('detail.medSection')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.mise_en_demeure_deadline && (
                  <p className="text-sm">{t('detail.medDeadline')}: <strong>{fmtDate(data.mise_en_demeure_deadline)}</strong></p>
                )}
                {data.mise_en_demeure_obligations && data.mise_en_demeure_obligations.length > 0 && (
                  <p className="text-xs text-muted-foreground mt-1">{data.mise_en_demeure_obligations.length} {t('detail.medObligations')}</p>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Photos + GPS (1 col) */}
        <div className="space-y-4">
          {/* Photos */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Camera className="h-4 w-4" />
                {t('detail.photos')} ({data.photos.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.photos.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">{t('detail.noPhotos')}</p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {data.photos.map((url, i) => (
                    <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                      className="block aspect-square rounded-lg overflow-hidden border hover:ring-2 hover:ring-primary transition-all">
                      <img src={url} alt={`Photo ${i + 1}`} className="w-full h-full object-cover" />
                    </a>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* GPS Map placeholder */}
          {data.gps_latitude && data.gps_longitude && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <MapPin className="h-4 w-4" />
                  {t('detail.location')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-muted/30 rounded-lg p-3 text-center">
                  <p className="font-mono text-sm">
                    {Number(data.gps_latitude).toFixed(6)}, {Number(data.gps_longitude).toFixed(6)}
                  </p>
                  {data.gps_accuracy && (
                    <p className="text-xs text-muted-foreground mt-1">{t('detail.accuracy')}: {Number(data.gps_accuracy).toFixed(0)}m</p>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Timeline */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Clock className="h-4 w-4" />
                {t('detail.timeline')}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs space-y-1.5">
              <div className="flex justify-between"><span className="text-muted-foreground">{t('detail.created')}</span><span>{fmtDate(data.created_at)}</span></div>
              <Separator />
              <div className="flex justify-between"><span className="text-muted-foreground">{t('detail.updated')}</span><span>{fmtDate(data.updated_at)}</span></div>
              {data.seal_proposed_at && (<><Separator /><div className="flex justify-between"><span className="text-muted-foreground">{t('detail.sealProposed')}</span><span>{fmtDate(data.seal_proposed_at)}</span></div></>)}
              {data.seal_approved_at && (<><Separator /><div className="flex justify-between"><span className="text-muted-foreground">{t('detail.sealApproved')}</span><span>{fmtDate(data.seal_approved_at)}</span></div></>)}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
