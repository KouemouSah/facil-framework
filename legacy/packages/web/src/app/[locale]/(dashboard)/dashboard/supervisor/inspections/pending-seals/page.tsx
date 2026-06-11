'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import { ArrowLeft, ShieldAlert, CheckCircle2, XCircle, MapPin, Camera, Clock, AlertTriangle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '@/components/ui/dialog'
import { inspectionApi } from '@/modules/inspections/services/api'
import { fmtXAF } from '@/modules/inspections/utils/formatters'
import type { PendingSeal } from '@/modules/inspections/types'

export default function PendingSealsPage() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const [seals, setSeals] = useState<PendingSeal[]>([])
  const [loading, setLoading] = useState(true)
  const [actionSeal, setActionSeal] = useState<PendingSeal | null>(null)
  const [rejectNotes, setRejectNotes] = useState('')
  const [processing, setProcessing] = useState(false)
  const t = useTranslations('inspection')
  // Fix m5: Separate dialogs for approve/reject
  const [showApproveConfirm, setShowApproveConfirm] = useState(false)
  const [showRejectDialog, setShowRejectDialog] = useState(false)

  const fetchSeals = useCallback(async () => {
    try {
      setLoading(true)
      const data = await inspectionApi.getSupervisorDashboard()
      setSeals(data.pending_seals)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      console.error('Failed to fetch pending seals:', msg)
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { fetchSeals() }, [fetchSeals])

  const handleAction = useCallback(async (approved: boolean) => {
    if (!actionSeal) return
    try {
      setProcessing(true)
      await inspectionApi.approveSeal(actionSeal.id, {
        approved,
        notes: !approved ? rejectNotes : undefined,
      })
      setSeals(prev => prev.filter(s => s.id !== actionSeal.id))
      setActionSeal(null)
      setRejectNotes('')
      toast({
        title: approved ? 'Scellé aprobado' : 'Scellé rechazado',
        description: approved
          ? 'Empresa desactivada, licencia suspendida.'
          : 'El agente será notificado.',
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error'
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    } finally {
      setProcessing(false)
    }
  }, [actionSeal, rejectNotes, toast])

  const getTimeRemaining = (proposedAt: string) => {
    const deadline = new Date(new Date(proposedAt).getTime() + 24 * 60 * 60 * 1000)
    const now = new Date()
    const diff = deadline.getTime() - now.getTime()
    if (diff <= 0) return 'Auto-aprobación inminente'
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
    return `${hours}h ${minutes}m restantes`
  }

  return (
    <div className="flex flex-col gap-4 p-4 max-w-4xl mx-auto">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <ShieldAlert className="h-6 w-6 text-red-600" />
        <h1 className="text-xl font-bold">Scellés pendientes de aprobación</h1>
        <Badge variant="destructive" className="ml-auto">{seals.length}</Badge>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => <div key={i} className="h-32 bg-muted animate-pulse rounded-lg" />)}
        </div>
      ) : seals.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            <ShieldAlert className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p>Ningún scellé pendiente de aprobación.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {seals.map((seal) => (
            <Card key={seal.id} className="border-red-200">
              <CardContent className="p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-lg">{seal.company_name}</h3>
                    <p className="text-sm text-muted-foreground">NIF: {seal.company_nif}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-red-700 text-lg">
                      {fmtXAF(seal.unpaid_obligations_amount, locale)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {seal.unpaid_obligations_count} obligation(s) impayée(s)
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 text-sm">
                  <Badge variant="outline" className="text-red-600">
                    {seal.seal_reason ? t(`seal.reasons.${seal.seal_reason}`) : seal.seal_reason}
                  </Badge>
                  <span className="text-muted-foreground">
                    Agent: {seal.agent_name}
                  </span>
                  <span className="text-muted-foreground">
                    {new Date(seal.inspection_date).toLocaleDateString()}
                  </span>
                </div>

                {seal.seal_notes && (
                  <p className="text-sm bg-muted/50 p-2 rounded">{seal.seal_notes}</p>
                )}

                {/* Photos */}
                {seal.photos.length > 0 && (
                  <div className="flex gap-2">
                    <Camera className="h-4 w-4 text-muted-foreground mt-1" />
                    {seal.photos.map((url, i) => (
                      <div key={i} className="w-16 h-16 rounded border overflow-hidden">
                        <img src={url} alt={`Photo ${i + 1}`} className="w-full h-full object-cover" />
                      </div>
                    ))}
                  </div>
                )}

                {/* GPS */}
                {seal.gps_latitude && (
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {Number(seal.gps_latitude).toFixed(4)}, {Number(seal.gps_longitude).toFixed(4)}
                  </div>
                )}

                {/* Auto-approve countdown */}
                {seal.seal_proposed_at && (
                  <div className="flex items-center gap-1 text-xs text-orange-600">
                    <Clock className="h-3 w-3" />
                    {getTimeRemaining(seal.seal_proposed_at)}
                  </div>
                )}

                {/* Fix m5: Actions with proper confirmation */}
                <div className="flex gap-2 pt-2">
                  <Button
                    className="flex-1 gap-1 min-h-[44px]"
                    onClick={() => {
                      setActionSeal(seal)
                      setShowApproveConfirm(true)
                    }}
                    disabled={processing}
                  >
                    <CheckCircle2 className="h-4 w-4" /> Aprobar
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1 gap-1 min-h-[44px]"
                    onClick={() => {
                      setActionSeal(seal)
                      setShowRejectDialog(true)
                    }}
                    disabled={processing}
                  >
                    <XCircle className="h-4 w-4" /> Rechazar
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Fix m5: Approve confirmation dialog */}
      <Dialog open={showApproveConfirm} onOpenChange={setShowApproveConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              Confirmar scellé — {actionSeal?.company_name}
            </DialogTitle>
            <DialogDescription>
              Esta acción desactivará la empresa y suspenderá su licencia comercial.
              El propietario será notificado por email y SMS.
            </DialogDescription>
          </DialogHeader>
          <div className="bg-red-50 p-3 rounded text-sm space-y-1">
            <p><strong>Empresa:</strong> {actionSeal?.company_name} ({actionSeal?.company_nif})</p>
            <p><strong>{t('seal.reason')}:</strong> {actionSeal?.seal_reason ? t(`seal.reasons.${actionSeal.seal_reason}`) : ''}</p>
            <p><strong>Impago:</strong> {fmtXAF(actionSeal?.unpaid_obligations_amount ?? 0, locale)}</p>
            <p><strong>Agente:</strong> {actionSeal?.agent_name}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApproveConfirm(false)}>Cancelar</Button>
            <Button
              variant="destructive"
              onClick={async () => {
                setShowApproveConfirm(false)
                await handleAction(true)
              }}
              disabled={processing}
            >
              Confirmar aprobación del scellé
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rechazar scellé — {actionSeal?.company_name}</DialogTitle>
            <DialogDescription>
              Explique el motivo del rechazo. El agente será notificado.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label>Motivo del rechazo</Label>
            <Textarea
              value={rejectNotes}
              onChange={e => setRejectNotes(e.target.value)}
              placeholder="Motivo..."
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowRejectDialog(false); setRejectNotes('') }}>Cancelar</Button>
            <Button
              variant="destructive"
              onClick={async () => {
                setShowRejectDialog(false)
                await handleAction(false)
                setRejectNotes('')
              }}
              disabled={!rejectNotes.trim() || processing}
            >
              Confirmar rechazo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
