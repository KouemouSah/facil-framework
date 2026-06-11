'use client'

import { useCallback, useRef, useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import { ArrowLeft, QrCode, Search, Building2, CheckCircle2, XCircle, AlertTriangle, ClipboardCheck } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { inspectionApi } from '@/modules/inspections/services/api'
import { fmtXAF } from '@/modules/inspections/utils/formatters'
import type { LicenseVerification } from '@/modules/inspections/types'

export default function ScanPage() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')
  const [nifInput, setNifInput] = useState('')
  const [searching, setSearching] = useState(false)
  const [result, setResult] = useState<LicenseVerification | null>(null)
  const [creating, setCreating] = useState(false)
  // Fix m2: Debounce ref for search
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const scanIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const doSearch = useCallback(async (searchNif: string) => {
    if (!searchNif) return
    try {
      setSearching(true)
      setResult(null)
      const data = await inspectionApi.verifyLicense({ nif: searchNif })
      setResult(data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('scan.noLicense')
      toast({ title: t('scan.notFound'), description: msg, variant: 'destructive' })
    } finally {
      setSearching(false)
    }
  }, [toast])

  // Fix m2: Debounced search on input change
  useEffect(() => {
    return () => { if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current) }
  }, [])

  const handleSearch = useCallback((nif?: string) => {
    const searchNif = nif || nifInput.trim()
    if (!searchNif) return
    // If called directly (from QR or Enter), execute immediately
    if (nif) {
      doSearch(searchNif)
      return
    }
    // Debounce button clicks (400ms)
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current)
    searchTimeoutRef.current = setTimeout(() => doSearch(searchNif), 400)
  }, [nifInput, doSearch])

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
        setCameraActive(true)
        setCameraError('')

        // Dynamic import for QR scanning
        scanIntervalRef.current = setInterval(async () => {
          if (!videoRef.current) return
          const canvas = document.createElement('canvas')
          canvas.width = videoRef.current.videoWidth
          canvas.height = videoRef.current.videoHeight
          const ctx = canvas.getContext('2d')
          if (!ctx) return
          ctx.drawImage(videoRef.current, 0, 0)

          try {
            const { default: jsQR } = await import('jsqr')
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
            const code = jsQR(imageData.data, imageData.width, imageData.height)
            if (code?.data) {
              // QR found — extract NIF or license_id from URL
              const qrData = code.data
              let nif = ''

              // Try to extract NIF from QR data
              const nifMatch = qrData.match(/nif=([A-Z0-9-]+)/i)
              const lidMatch = qrData.match(/lid=([a-f0-9-]+)/i)

              if (nifMatch) {
                nif = nifMatch[1]
              } else if (lidMatch) {
                // Direct license ID lookup
                try {
                  const data = await inspectionApi.verifyLicense({ license_id: lidMatch[1] })
                  setResult(data)
                  stopCamera()
                  return
                } catch { /* ignore */ }
              } else if (/^[A-Z0-9-]{5,20}$/i.test(qrData)) {
                nif = qrData
              }

              if (nif) {
                stopCamera()
                setNifInput(nif)
                handleSearch(nif)
              }
            }
          } catch { /* jsQR not available, silently skip */ }
        }, 500)
      }
    } catch {
      setCameraError(t('scan.cameraError'))
    }
  }, [handleSearch]) // eslint-disable-line react-hooks/exhaustive-deps

  const stopCamera = useCallback(() => {
    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current)
      scanIntervalRef.current = null
    }
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream
      stream.getTracks().forEach(t => t.stop())
      videoRef.current.srcObject = null
    }
    setCameraActive(false)
  }, [])

  const handleStartInspection = useCallback(async () => {
    if (!result) return
    try {
      setCreating(true)
      const inspection = await inspectionApi.create({
        license_id: result.license_id,
        company_id: result.company_id,
      })
      router.push(`/${locale}/dashboard/agent/oms/field/inspect?id=${inspection.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast({ title: t('common.error'), description: msg, variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }, [result, locale, router, toast])

  const unpaidObligations = result?.obligations.filter(
    o => o.status === 'pending' || o.status === 'overdue'
  ) ?? []

  return (
    <div className="flex flex-col gap-4 p-4 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <QrCode className="h-6 w-6 text-blue-600" />
        <h1 className="text-xl font-bold">{t('scan.title')}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Scanner + Search */}
        <div className="flex flex-col gap-4">
          {/* Camera */}
          <Card>
            <CardContent className="p-4">
              {cameraActive ? (
                <div className="relative">
                  <video
                    ref={videoRef}
                    className="w-full rounded-lg aspect-square object-cover"
                    playsInline
                    muted
                  />
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="w-48 h-48 border-2 border-white/60 rounded-lg" />
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="absolute bottom-2 right-2"
                    onClick={stopCamera}
                  >
                    {t('scan.closeCamera')}
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  className="w-full h-32 flex flex-col gap-2"
                  onClick={startCamera}
                >
                  <QrCode className="h-8 w-8" />
                  <span>{t('scan.scanQr')}</span>
                </Button>
              )}
              {cameraError && (
                <p className="text-sm text-red-600 mt-2">{cameraError}</p>
              )}
            </CardContent>
          </Card>

          {/* Manual search */}
          <div className="flex items-center gap-2">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground px-2">{t('scan.orManual')}</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <div className="flex gap-2">
            <Input
              placeholder="NIF (GExxxxx) o N° Registro (PE-xxxxxx)"
              value={nifInput}
              onChange={e => setNifInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              className="flex-1"
            />
            <Button onClick={() => handleSearch()} disabled={searching}>
              <Search className="h-4 w-4 mr-1" />
              {searching ? t('scan.searching') : t('scan.search')}
            </Button>
          </div>
        </div>

        {/* Right: Result */}
        <div className="flex flex-col gap-4">
          {result ? (
            <>
              {/* Company info */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-gray-600" />
                    <CardTitle className="text-base">{t('inspect.company')}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-1">
                  <p className="font-semibold text-lg">{result.company_name}</p>
                  <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
                    <span>{result.company_nif}</span>
                    {result.forma_juridica && <span>| {result.forma_juridica}</span>}
                    {result.zone_code && <span>| Zona {result.zone_code}</span>}
                    {result.city_name && <span>| {result.city_name}</span>}
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant={result.license_status === 'complete' ? 'default' : 'destructive'}>
                      {result.license_status}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      Año fiscal {result.fiscal_year}
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Active MED warning */}
              {result.active_mise_en_demeure && (
                <Card className="border-orange-300 bg-orange-50">
                  <CardContent className="p-3 flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-orange-600 shrink-0" />
                    <span className="text-sm font-medium text-orange-800">
                      Mise en demeure activa — plazo hasta{' '}
                      {new Date(result.active_mise_en_demeure.mise_en_demeure_deadline as string).toLocaleDateString()}
                    </span>
                  </CardContent>
                </Card>
              )}

              {/* Obligations */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">
                    {t('inspect.obligations')} ({result.obligations.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1.5">
                  {result.obligations.map(obl => {
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
                  })}

                  {unpaidObligations.length > 0 && (
                    <>
                      <Separator className="my-2" />
                      <div className="flex justify-between font-medium text-sm">
                        <span className="text-red-700">{t('inspect.unpaidCount')}</span>
                        <span className="text-red-700">
                          {fmtXAF(
                            unpaidObligations.reduce((s, o) => s + o.amount + (o.penalty_amount || 0), 0),
                            locale,
                          )}
                        </span>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Previous inspections */}
              {result.previous_inspections.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Inspecciones previas</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    {result.previous_inspections.slice(0, 3).map(pi => (
                      <div key={pi.id} className="flex items-center justify-between text-xs p-1.5 rounded bg-muted/50">
                        <span>{new Date(pi.inspection_date).toLocaleDateString()}</span>
                        <Badge variant="outline" className="text-xs">{pi.status}</Badge>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Start inspection button */}
              <Button
                size="lg"
                className="w-full gap-2"
                onClick={handleStartInspection}
                disabled={creating}
              >
                <ClipboardCheck className="h-5 w-5" />
                {creating ? t('scan.creating') : t('scan.startInspection')}
              </Button>
            </>
          ) : (
            <Card className="flex items-center justify-center h-64">
              <CardContent className="text-center text-muted-foreground">
                <QrCode className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p>{t('scan.scanResult')}</p>
                <p className="text-xs mt-1">{t('scan.scanResultSub')}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
