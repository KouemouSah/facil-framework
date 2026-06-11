'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  ArrowLeft, Camera, MapPin, CheckCircle2, AlertTriangle,
  Lock, DollarSign, Save, FileText, Upload, XCircle,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '@/components/ui/dialog'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { inspectionApi } from '@/modules/inspections/services/api'
import { SignaturePad } from '@/modules/inspections/components/SignaturePad'
import { INSPECTION_STATUS_CONFIG, SEAL_REASONS, fmtXAF } from '@/modules/inspections/utils/formatters'
import type { Inspection, SealReason, LicenseObligation } from '@/modules/inspections/types'

export default function InspectPage() {
  const locale = useLocale()
  const router = useRouter()
  const searchParams = useSearchParams()
  const inspectionId = searchParams.get('id')
  const { toast } = useToast()
  const t = useTranslations('inspection')

  const [inspection, setInspection] = useState<Inspection | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Fix C3/C4: Store obligations fetched from verify API
  const [obligations, setObligations] = useState<LicenseObligation[]>([])
  const [selectedOblIds, setSelectedOblIds] = useState<string[]>([])

  // Form state
  const [activityConforme, setActivityConforme] = useState<boolean | null>(null)
  const [activityObserved, setActivityObserved] = useState('')
  const [notes, setNotes] = useState('')
  const [gps, setGps] = useState<{ lat: number; lng: number; accuracy: number } | null>(null)
  // Fix M5: Track uploaded photo URLs
  const [photoUrls, setPhotoUrls] = useState<string[]>([])
  // Fix F2: Signature state
  const [signatureDataUrl, setSignatureDataUrl] = useState<string | null>(null)

  // Dialogs
  const [showMedDialog, setShowMedDialog] = useState(false)
  const [showSealDialog, setShowSealDialog] = useState(false)
  const [showCollectDialog, setShowCollectDialog] = useState(false)
  // Fix m5: Confirmation dialog for complete
  const [showCompleteConfirm, setShowCompleteConfirm] = useState(false)
  const [medDeadline, setMedDeadline] = useState(72)
  const [sealReason, setSealReason] = useState<SealReason | ''>('')
  const [sealNotes, setSealNotes] = useState('')
  const [collectMethod, setCollectMethod] = useState<'cash' | 'mobile_money'>('cash')
  const [collectPhone, setCollectPhone] = useState('')

  const fetchInspection = useCallback(async () => {
    if (!inspectionId) return
    try {
      setLoading(true)
      const data = await inspectionApi.get(inspectionId)
      setInspection(data)
      setActivityConforme(data.activity_conforme ?? null)
      setActivityObserved(data.activity_observed ?? '')
      setNotes(data.notes ?? '')
      setPhotoUrls(data.photos || [])

      // Fix C3/C4: Fetch obligations from verify API using license_id
      // Fetch obligations for MED/Collect dialogs
      if (data.license_id) {
        try {
          const verif = await inspectionApi.verifyLicense({ license_id: data.license_id })
          setObligations(verif.obligations || [])
        } catch {
          // F6: Show warning if obligations can't load
          toast({
            title: 'Obligaciones no disponibles',
            description: 'No se pudieron cargar las obligaciones. MED y cobro no disponibles.',
            variant: 'destructive',
          })
        }
      }
    } catch {
      toast({ title: 'Error', description: 'Inspección no encontrada', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [inspectionId, toast])

  useEffect(() => { fetchInspection() }, [fetchInspection])

  // Auto-capture GPS
  useEffect(() => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      pos => setGps({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy }),
      () => { /* GPS unavailable */ },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }, [])

  // Computed: unpaid obligations
  const unpaidObligations = obligations.filter(o => o.status === 'pending' || o.status === 'overdue')
  const unpaidTotal = unpaidObligations.reduce((s, o) => s + o.amount + (o.penalty_amount || 0), 0)

  // Auto-select all unpaid when MED/Collect dialog opens
  useEffect(() => {
    if (showMedDialog || showCollectDialog) {
      setSelectedOblIds(unpaidObligations.map(o => o.id))
    }
  }, [showMedDialog, showCollectDialog]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = useCallback(async () => {
    if (!inspection) return
    try {
      setSaving(true)
      const data = await inspectionApi.update(inspection.id, {
        activity_conforme: activityConforme ?? undefined,
        activity_observed: activityObserved || undefined,
        notes: notes || undefined,
        gps_latitude: gps?.lat,
        gps_longitude: gps?.lng,
        gps_accuracy: gps?.accuracy,
        photos: photoUrls.length > 0 ? photoUrls : undefined,
        agent_signature: signatureDataUrl || undefined,
      })
      setInspection(data)
      toast({ title: 'Guardado', description: 'Inspección actualizada' })
    } catch {
      toast({ title: 'Error', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }, [inspection, activityConforme, activityObserved, notes, gps, photoUrls, toast])

  const handleComplete = useCallback(async () => {
    if (!inspection) return
    try {
      setSaving(true)
      // 1. Upload pending photos to Firebase first
      const finalPhotoUrls = await uploadPendingPhotos()

      // 2. Save all data (photos + signature + GPS + activity)
      await inspectionApi.update(inspection.id, {
        activity_conforme: activityConforme ?? undefined,
        activity_observed: activityObserved || undefined,
        notes: notes || undefined,
        gps_latitude: gps?.lat,
        gps_longitude: gps?.lng,
        gps_accuracy: gps?.accuracy,
        photos: finalPhotoUrls.length > 0 ? finalPhotoUrls : undefined,
        agent_signature: signatureDataUrl || undefined,
      })

      // 3. Complete inspection
      const data = await inspectionApi.complete(inspection.id, { notes })
      setInspection(data)
      setShowCompleteConfirm(false)
      toast({ title: t('inspect.completed'), description: `${t('inspect.result')}: ${data.result}` })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error'
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }, [inspection, activityConforme, activityObserved, notes, gps, photoUrls, toast])

  // Fix C3: MED with real obligation IDs
  const handleMED = useCallback(async () => {
    if (!inspection || selectedOblIds.length === 0) return
    try {
      setSaving(true)
      const data = await inspectionApi.miseEnDemeure(inspection.id, {
        obligation_ids: selectedOblIds,
        deadline_hours: medDeadline,
        notes: notes || undefined,
      })
      setInspection(data)
      setShowMedDialog(false)
      toast({ title: 'Mise en demeure emitida', description: `Plazo: ${medDeadline}h` })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error'
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }, [inspection, selectedOblIds, medDeadline, notes, toast])

  const handleSeal = useCallback(async () => {
    if (!inspection || !sealReason) return
    try {
      setSaving(true)
      const data = await inspectionApi.proposeSeal(inspection.id, {
        reason: sealReason,
        notes: sealNotes || undefined,
      })
      setInspection(data)
      setShowSealDialog(false)
      toast({ title: 'Scellé propuesto', description: 'Esperando aprobación del supervisor' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error'
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }, [inspection, sealReason, sealNotes, toast])

  // Fix C4: Collect with real obligation IDs and computed amount
  const handleCollect = useCallback(async () => {
    if (!inspection || selectedOblIds.length === 0) return
    const selectedTotal = unpaidObligations
      .filter(o => selectedOblIds.includes(o.id))
      .reduce((s, o) => s + o.amount + (o.penalty_amount || 0), 0)
    try {
      setSaving(true)
      const result = await inspectionApi.collectPayment(inspection.id, {
        obligation_ids: selectedOblIds,
        method: collectMethod,
        amount: selectedTotal,
        phone_number: collectMethod === 'mobile_money' ? collectPhone : undefined,
      })
      setShowCollectDialog(false)
      toast({
        title: collectMethod === 'cash' ? 'Cobro registrado' : 'Pago móvil iniciado',
        description: result.receipt_number ? `Recibo: ${result.receipt_number}` : undefined,
      })
      fetchInspection()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error'
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }, [inspection, selectedOblIds, unpaidObligations, collectMethod, collectPhone, toast, fetchInspection])

  // Photos: kept locally as File objects during capture, uploaded at validation
  const [pendingPhotos, setPendingPhotos] = useState<File[]>([])
  const [photoPreviewUrls, setPhotoPreviewUrls] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)

  const handlePhotoCapture = useCallback(async (file: File) => {
    if (pendingPhotos.length + photoUrls.length >= 10) {
      toast({ title: t('common.error'), description: 'Max 10 photos', variant: 'destructive' })
      return
    }

    // Compress if > 2MB
    let imageFile = file
    if (file.size > 2 * 1024 * 1024) {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      const img = new Image()
      const url = URL.createObjectURL(file)
      await new Promise<void>((resolve) => {
        img.onload = () => {
          const scale = Math.min(1, Math.sqrt((2 * 1024 * 1024) / file.size))
          canvas.width = img.width * scale
          canvas.height = img.height * scale
          ctx?.drawImage(img, 0, 0, canvas.width, canvas.height)
          URL.revokeObjectURL(url)
          resolve()
        }
        img.src = url
      })
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, 'image/jpeg', 0.8)
      )
      if (blob) {
        imageFile = new File([blob], file.name, { type: 'image/jpeg' })
      }
    }

    setPendingPhotos(prev => [...prev, imageFile])
    setPhotoPreviewUrls(prev => [...prev, URL.createObjectURL(imageFile)])
    toast({ title: t('inspect.photoCaptured'), description: `${(imageFile.size / 1024).toFixed(0)} KB` })
  }, [pendingPhotos, photoUrls, toast, t])

  const handleDeletePendingPhoto = useCallback((index: number) => {
    URL.revokeObjectURL(photoPreviewUrls[index])
    setPendingPhotos(prev => prev.filter((_, i) => i !== index))
    setPhotoPreviewUrls(prev => prev.filter((_, i) => i !== index))
  }, [photoPreviewUrls])

  // Upload all pending photos to Firebase (called during validation)
  const uploadPendingPhotos = useCallback(async (): Promise<string[]> => {
    if (!inspection || pendingPhotos.length === 0) return photoUrls
    setUploading(true)
    const uploadedUrls = [...photoUrls]
    try {
      for (const file of pendingPhotos) {
        const result = await inspectionApi.uploadPhoto(inspection.id, file)
        uploadedUrls.push(result.url)
      }
      setPendingPhotos([])
      setPhotoPreviewUrls([])
      setPhotoUrls(uploadedUrls)
      return uploadedUrls
    } catch {
      toast({ title: t('common.error'), description: 'Photo upload failed', variant: 'destructive' })
      throw new Error('Photo upload failed')
    } finally {
      setUploading(false)
    }
  }, [inspection, pendingPhotos, photoUrls, toast, t])

  if (loading || !inspection) {
    return (
      <div className="p-4 space-y-4">
        {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded-lg" />)}
      </div>
    )
  }

  const statusCfg = INSPECTION_STATUS_CONFIG[inspection.status]
  const isEditable = inspection.status === 'in_progress'

  return (
    <div className="flex flex-col gap-4 p-4 max-w-2xl mx-auto pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-lg font-bold">{inspection.company_name}</h1>
            <p className="text-xs text-muted-foreground">{inspection.company_nif}</p>
          </div>
        </div>
        <Badge className={`${statusCfg.bgColor} ${statusCfg.color}`}>
          {t(`status.${inspection.status}`)}
        </Badge>
      </div>

      {/* 1. Company info (readonly) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Empresa</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-1">
          <p><strong>{inspection.company_name}</strong></p>
          <p className="text-muted-foreground">NIF: {inspection.company_nif} | {inspection.entity_code}</p>
        </CardContent>
      </Card>

      {/* 2. Activity compliance */}
      {isEditable && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Conformidad de actividad</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Button
                variant={activityConforme === true ? 'default' : 'outline'}
                size="sm"
                className="flex-1 gap-1"
                onClick={() => setActivityConforme(true)}
              >
                <CheckCircle2 className="h-4 w-4" /> Conforme
              </Button>
              <Button
                variant={activityConforme === false ? 'destructive' : 'outline'}
                size="sm"
                className="flex-1 gap-1"
                onClick={() => setActivityConforme(false)}
              >
                <AlertTriangle className="h-4 w-4" /> No conforme
              </Button>
            </div>
            {activityConforme === false && (
              <div>
                <Label className="text-xs">Actividad constatada</Label>
                <Input
                  placeholder="Actividad real observada..."
                  value={activityObserved}
                  onChange={e => setActivityObserved(e.target.value)}
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 3. Obligations detail (from verify API) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center justify-between">
            <span>Obligaciones ({obligations.length})</span>
            {unpaidObligations.length > 0 && (
              <span className="text-red-600 font-medium">
                {unpaidObligations.length} impago(s) — {fmtXAF(unpaidTotal, locale)}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {obligations.length === 0 ? (
            <p className="text-sm text-muted-foreground">Cargando obligaciones...</p>
          ) : (
            obligations.map(obl => {
              const isPaid = obl.status === 'paid' || obl.status === 'completed'
              return (
                <div
                  key={obl.id}
                  className={`flex items-center justify-between p-2 rounded text-sm ${
                    isPaid ? 'bg-green-50' : 'bg-red-50'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {isPaid ? (
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                    <span className="truncate max-w-[200px]">
                      {obl.service_name || obl.fee_type}
                    </span>
                  </div>
                  <span className={`font-medium ${isPaid ? 'text-green-700' : 'text-red-700'}`}>
                    {fmtXAF(obl.amount + (obl.penalty_amount || 0), locale)}
                  </span>
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      {/* 4. Photos */}
      {isEditable && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-1">
              <Camera className="h-4 w-4" /> Fotos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 flex-wrap">
              {/* Already uploaded (Firebase URLs) */}
              {photoUrls.map((url, i) => (
                <div key={`uploaded-${i}`} className="w-20 h-20 rounded border overflow-hidden relative">
                  <img src={url} alt={`Photo ${i + 1}`} className="w-full h-full object-cover" />
                </div>
              ))}
              {/* Pending upload (local previews — uploaded at validation) */}
              {photoPreviewUrls.map((url, i) => (
                <div key={`pending-${i}`} className="w-20 h-20 rounded border-2 border-dashed border-amber-400 overflow-hidden relative">
                  <img src={url} alt={`Pending ${i + 1}`} className="w-full h-full object-cover opacity-80" />
                  <button
                    className="absolute top-0 right-0 bg-red-500 text-white rounded-bl p-0.5"
                    onClick={() => handleDeletePendingPhoto(i)}
                  >
                    <XCircle className="h-3 w-3" />
                  </button>
                  <span className="absolute bottom-0 left-0 right-0 bg-amber-400 text-[8px] text-center">
                    pendiente
                  </span>
                </div>
              ))}
              <label className={`w-20 h-20 rounded border border-dashed flex items-center justify-center cursor-pointer hover:bg-muted/50 min-h-[44px] min-w-[44px] ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
                {uploading ? (
                  <div className="h-5 w-5 border-2 border-muted-foreground border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Upload className="h-5 w-5 text-muted-foreground" />
                )}
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0]
                    if (file) await handlePhotoCapture(file)
                    e.target.value = ''
                  }}
                />
              </label>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 5. GPS */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-1">
            <MapPin className="h-4 w-4" /> GPS
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {gps ? (
            <span className="text-green-600">
              {gps.lat.toFixed(6)}, {gps.lng.toFixed(6)} (&#177;{gps.accuracy.toFixed(0)}m)
            </span>
          ) : (
            <span className="text-muted-foreground">Obteniendo ubicación...</span>
          )}
        </CardContent>
      </Card>

      {/* 6. Notes */}
      {isEditable && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-1">
              <FileText className="h-4 w-4" /> Notas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="Observaciones de la inspección..."
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
            />
          </CardContent>
        </Card>
      )}

      {/* 7. Signature — Fix F2: SignaturePad integrated */}
      {isEditable && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-1">
              <FileText className="h-4 w-4" /> {t('inspect.save')} — Firma
            </CardTitle>
          </CardHeader>
          <CardContent>
            {signatureDataUrl ? (
              <div className="flex flex-col items-center gap-2">
                <img
                  src={signatureDataUrl}
                  alt="Signature"
                  className="border rounded max-w-[300px] max-h-[120px]"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSignatureDataUrl(null)}
                  className="min-h-[44px]"
                >
                  Cambiar firma
                </Button>
              </div>
            ) : (
              <SignaturePad
                onSign={(dataUrl) => setSignatureDataUrl(dataUrl)}
                onClear={() => setSignatureDataUrl(null)}
              />
            )}
          </CardContent>
        </Card>
      )}

      {/* 8. Actions (sticky bottom) — Fix m3: z-40 to avoid dialog conflict */}
      {isEditable && (
        <div className="fixed bottom-0 left-0 right-0 bg-background border-t p-3 flex gap-2 z-40">
          <Button variant="outline" size="sm" onClick={handleSave} disabled={saving} className="gap-1 min-h-[44px]">
            <Save className="h-4 w-4" /> Guardar
          </Button>
          <Button
            size="sm"
            onClick={() => setShowCompleteConfirm(true)}
            disabled={saving || activityConforme === null}
            className="gap-1 flex-1 min-h-[44px]"
            title={activityConforme === null ? 'Primero marque la conformidad de actividad' : undefined}
          >
            <CheckCircle2 className="h-4 w-4" /> Validar
          </Button>
          {unpaidObligations.length > 0 && (
            <>
              <Button
                variant="outline"
                size="sm"
                className="gap-1 text-orange-600 border-orange-300 min-h-[44px]"
                onClick={() => setShowMedDialog(true)}
              >
                <AlertTriangle className="h-4 w-4" /> MED
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-1 text-green-600 border-green-300 min-h-[44px]"
                onClick={() => setShowCollectDialog(true)}
              >
                <DollarSign className="h-4 w-4" /> Cobrar
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-1 text-red-600 border-red-300 min-h-[44px]"
                onClick={() => setShowSealDialog(true)}
              >
                <Lock className="h-4 w-4" /> Sellar
              </Button>
            </>
          )}
        </div>
      )}

      {/* Fix m5: Complete confirmation dialog */}
      <AlertDialog open={showCompleteConfirm} onOpenChange={setShowCompleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Completar inspección</AlertDialogTitle>
            <AlertDialogDescription>
              Actividad: {activityConforme ? 'Conforme' : 'No conforme'}
              {' | '}
              Impagos: {unpaidObligations.length}
              {' | '}
              Resultado previsto: {activityConforme === false || unpaidObligations.length > 0 ? 'No conforme' : 'Conforme'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleComplete} disabled={saving}>
              Confirmar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* MED Dialog — Fix C3: real obligation selection */}
      <Dialog open={showMedDialog} onOpenChange={setShowMedDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mise en demeure</DialogTitle>
            <DialogDescription>
              Emitir un aviso formal con plazo para regularización.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Plazo (horas)</Label>
              <Select value={String(medDeadline)} onValueChange={v => setMedDeadline(Number(v))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="24">24 horas</SelectItem>
                  <SelectItem value="48">48 horas</SelectItem>
                  <SelectItem value="72">72 horas (defecto)</SelectItem>
                  <SelectItem value="168">7 días</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm mb-1 block">Obligaciones impagadas ({unpaidObligations.length})</Label>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {unpaidObligations.map(obl => (
                  <label key={obl.id} className="flex items-center gap-2 p-1.5 rounded bg-red-50 text-sm cursor-pointer">
                    <Checkbox
                      checked={selectedOblIds.includes(obl.id)}
                      onCheckedChange={(checked) => {
                        setSelectedOblIds(prev =>
                          checked ? [...prev, obl.id] : prev.filter(id => id !== obl.id)
                        )
                      }}
                    />
                    <span className="flex-1 truncate">{obl.service_name || obl.fee_type}</span>
                    <span className="text-red-700 font-medium">
                      {fmtXAF(obl.amount + (obl.penalty_amount || 0), locale)}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMedDialog(false)}>Cancelar</Button>
            <Button
              className="bg-orange-600 hover:bg-orange-700"
              onClick={handleMED}
              disabled={selectedOblIds.length === 0 || saving}
            >
              Emitir mise en demeure
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Seal Dialog */}
      <Dialog open={showSealDialog} onOpenChange={setShowSealDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Proponer scellé</DialogTitle>
            <DialogDescription>
              El scellé requiere la aprobación del supervisor.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Motivo</Label>
              <Select value={sealReason} onValueChange={v => setSealReason(v as SealReason)}>
                <SelectTrigger><SelectValue placeholder="Seleccionar motivo..." /></SelectTrigger>
                <SelectContent>
                  {SEAL_REASONS.map((key) => (
                    <SelectItem key={key} value={key}>{t(`seal.reasons.${key}`)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Notas</Label>
              <Textarea
                value={sealNotes}
                onChange={e => setSealNotes(e.target.value)}
                placeholder="Observaciones adicionales..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSealDialog(false)}>Cancelar</Button>
            <Button variant="destructive" onClick={handleSeal} disabled={!sealReason || saving}>
              Proponer scellé
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Collect Dialog — Fix C4: real obligation selection + computed amount */}
      <Dialog open={showCollectDialog} onOpenChange={setShowCollectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cobrar en terreno</DialogTitle>
            <DialogDescription>
              Seleccione las obligaciones a cobrar.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-sm mb-1 block">Obligaciones a cobrar</Label>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {unpaidObligations.map(obl => (
                  <label key={obl.id} className="flex items-center gap-2 p-1.5 rounded bg-muted/50 text-sm cursor-pointer">
                    <Checkbox
                      checked={selectedOblIds.includes(obl.id)}
                      onCheckedChange={(checked) => {
                        setSelectedOblIds(prev =>
                          checked ? [...prev, obl.id] : prev.filter(id => id !== obl.id)
                        )
                      }}
                    />
                    <span className="flex-1 truncate">{obl.service_name || obl.fee_type}</span>
                    <span className="font-medium">
                      {fmtXAF(obl.amount + (obl.penalty_amount || 0), locale)}
                    </span>
                  </label>
                ))}
              </div>
              <p className="text-sm font-medium mt-2">
                Total:{' '}
                {fmtXAF(
                  unpaidObligations
                    .filter(o => selectedOblIds.includes(o.id))
                    .reduce((s, o) => s + o.amount + (o.penalty_amount || 0), 0),
                  locale,
                )}
              </p>
            </div>
            <div>
              <Label>Método</Label>
              <Select value={collectMethod} onValueChange={v => setCollectMethod(v as 'cash' | 'mobile_money')}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="cash">Efectivo</SelectItem>
                  <SelectItem value="mobile_money">Mobile Money</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {collectMethod === 'mobile_money' && (
              <div>
                <Label>Teléfono</Label>
                <Input
                  placeholder="+240..."
                  value={collectPhone}
                  onChange={e => setCollectPhone(e.target.value)}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCollectDialog(false)}>Cancelar</Button>
            <Button
              onClick={handleCollect}
              className="bg-green-600 hover:bg-green-700"
              disabled={selectedOblIds.length === 0 || saving}
            >
              Confirmar cobro
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
