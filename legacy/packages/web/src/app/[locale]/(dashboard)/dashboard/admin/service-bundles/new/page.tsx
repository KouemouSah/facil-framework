"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import {
  ArrowLeft, ArrowRight, Check, Package, MapPin, Search,
  Plus, Trash2, Loader2, FileText, Copy,
} from "lucide-react"
import { bundleApi, bundleAdminApi } from "@/modules/fiscal-services/services/bundle-api"
import { formatXAF } from "@/core/utils/format"
import type { CommerceZone, FiscalServiceOption } from "@/types/service-bundle"

interface PendingItem {
  service: FiscalServiceOption
  amount: number
  isFixed: boolean
}

const STEPS = [
  { key: "info", icon: Package },
  { key: "services", icon: FileText },
  { key: "review", icon: Check },
] as const

export default function NewBundlePage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.serviceBundles")
  const basePath = `/${locale}/dashboard/admin/service-bundles`

  // Wizard state
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)

  // Step 1: Basic info
  const [form, setForm] = useState({
    bundleCode: "", commerceType: "", nameEs: "", descriptionEs: "",
    legalReference: "", installmentEligible: false,
    maxInstallments: 1, installmentFrequency: "monthly",
  })

  // Step 2: Services selection
  const [zones, setZones] = useState<CommerceZone[]>([])
  const [selectedZone, setSelectedZone] = useState("")
  const [pendingItems, setPendingItems] = useState<PendingItem[]>([])
  const [serviceSearch, setServiceSearch] = useState("")
  const [serviceResults, setServiceResults] = useState<FiscalServiceOption[]>([])
  const [serviceSearching, setServiceSearching] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [addAmount, setAddAmount] = useState("")
  const [addFixed, setAddFixed] = useState(false)
  const [addService, setAddService] = useState<FiscalServiceOption | null>(null)
  const searchTimer = useRef<NodeJS.Timeout | null>(null)

  // Multi-zone copy
  const [copyToAllZones, setCopyToAllZones] = useState(false)
  const [copyProgress, setCopyProgress] = useState("")
  const [submitError, setSubmitError] = useState("")

  // Load zones
  useEffect(() => {
    bundleApi.listZones().then(z => {
      setZones(z)
      if (z.length > 0) setSelectedZone(z[0].id)
    }).catch(() => {})
  }, [])

  // Debounced service search
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!serviceSearch || serviceSearch.length < 2) { setServiceResults([]); return }
    searchTimer.current = setTimeout(async () => {
      setServiceSearching(true)
      try {
        const results = await bundleAdminApi.searchServices(serviceSearch)
        // Filter out already-added services
        const addedIds = new Set(pendingItems.map(i => i.service.id))
        setServiceResults(results.filter(r => !addedIds.has(r.id)))
      } catch { setServiceResults([]) }
      finally { setServiceSearching(false) }
    }, 300)
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current) }
  }, [serviceSearch, pendingItems])

  const handleAddService = () => {
    if (!addService || !addAmount) return
    setPendingItems(prev => [...prev, {
      service: addService,
      amount: parseFloat(addAmount),
      isFixed: addFixed,
    }])
    setAddService(null); setAddAmount(""); setAddFixed(false); setServiceSearch("")
  }

  const handleRemoveService = (idx: number) => {
    setPendingItems(prev => prev.filter((_, i) => i !== idx))
  }

  const totalAmount = pendingItems.reduce((sum, item) => sum + item.amount, 0)

  // Step 1 validation
  const step1Valid = form.bundleCode.length >= 2 && form.nameEs.length >= 3 && form.commerceType.length >= 2

  // Step 2 validation
  const step2Valid = pendingItems.length > 0

  // Submit: create bundle + bulk add items + optionally copy to all zones
  const handleSubmit = async () => {
    setSaving(true)
    setSubmitError("")
    let createdId = ""
    try {
      setCopyProgress(t("creatingBundle"))
      const created = await bundleAdminApi.createBundle({
        bundleCode: form.bundleCode,
        commerceType: form.commerceType,
        nameEs: form.nameEs,
        descriptionEs: form.descriptionEs || undefined,
        legalReference: form.legalReference || undefined,
        isActive: true,
        installmentEligible: form.installmentEligible,
        maxInstallments: form.maxInstallments,
        installmentFrequency: form.installmentFrequency,
      })
      createdId = created.id

      // Bulk add items for the selected zone (1 HTTP call)
      setCopyProgress(t("addingServices"))
      const selectedZoneObj = zones.find(z => z.id === selectedZone)
      const bulkItems = pendingItems.map(item => ({
        serviceCode: item.service.serviceCode,
        zoneCode: selectedZoneObj?.zoneCode ?? "",
        amount: item.amount,
        isFixedAcrossZones: item.isFixed,
        ministryId: item.service.ministryId ?? undefined,
      }))
      await bundleAdminApi.bulkImport(created.id, bulkItems)

      // Copy prices to all other zones (same prices as base zone)
      if (copyToAllZones && zones.length > 1) {
        const otherZones = zones.filter(z => z.id !== selectedZone)
        const failedZones: string[] = []
        for (let i = 0; i < otherZones.length; i++) {
          const targetZone = otherZones[i]
          setCopyProgress(`${t("copyingToZone")} ${targetZone.zoneCode} (${i + 1}/${otherZones.length})`)
          try {
            await bundleAdminApi.copyZonePrices(created.id, {
              sourceZoneId: selectedZone,
              targetZoneId: targetZone.id,
              multiplier: 1.0,
            })
          } catch {
            failedZones.push(targetZone.zoneCode)
          }
        }
        if (failedZones.length > 0) {
          setSubmitError(`${t("copyPartialError")}: ${failedZones.join(", ")}`)
          setCopyProgress("")
          setSaving(false)
          // Still navigate — bundle is created, user can fix missing zones in edit
          setTimeout(() => router.push(`${basePath}/${created.id}/edit`), 3000)
          return
        }
      }

      setCopyProgress("")
      router.push(`${basePath}/${created.id}/edit`)
    } catch (err) {
      console.error("Create failed:", err)
      setCopyProgress("")
      if (createdId) {
        setSubmitError(t("createPartialError"))
        setTimeout(() => router.push(`${basePath}/${createdId}/edit`), 3000)
      } else {
        setSubmitError(t("createError"))
      }
    } finally {
      setSaving(false)
    }
  }

  const selectedZoneObj = zones.find(z => z.id === selectedZone)

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push(basePath)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-xl font-bold">{t("createBundle")}</h1>
      </div>

      {/* Stepper */}
      <div className="flex items-center justify-center gap-2">
        {STEPS.map((s, i) => {
          const Icon = s.icon
          const isCompleted = i < step
          const isCurrent = i === step
          return (
            <div key={s.key} className="flex items-center gap-2">
              {i > 0 && <div className={`w-12 h-0.5 ${isCompleted ? "bg-primary" : "bg-muted"}`} />}
              <button
                onClick={() => { if (isCompleted) setStep(i) }}
                disabled={!isCompleted && !isCurrent}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  isCurrent ? "bg-primary text-primary-foreground" :
                  isCompleted ? "bg-primary/10 text-primary cursor-pointer hover:bg-primary/20" :
                  "bg-muted text-muted-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {i === 0 ? t("bundleData") : i === 1 ? t("services") : t("total")}
              </button>
            </div>
          )
        })}
      </div>

      {/* Step 1: Basic Info */}
      {step === 0 && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm">{t("bundleData")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 px-4 pb-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">{t("code")} *</Label>
                <Input
                  value={form.bundleCode}
                  onChange={(e) => setForm(f => ({ ...f, bundleCode: e.target.value.toUpperCase().replace(/\s/g, "_") }))}
                  className="h-8 text-sm font-mono"
                  placeholder="BARES_RESTAURANTES"
                />
              </div>
              <div>
                <Label className="text-xs">{t("commerceType")} *</Label>
                <Input
                  value={form.commerceType}
                  onChange={(e) => setForm(f => ({ ...f, commerceType: e.target.value }))}
                  className="h-8 text-sm"
                  placeholder="Bar / Restaurante"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">{t("nameEs")} *</Label>
              <Input
                value={form.nameEs}
                onChange={(e) => setForm(f => ({ ...f, nameEs: e.target.value }))}
                className="h-8 text-sm"
                placeholder="Licencia Comercial — Bares y Restaurantes"
              />
            </div>
            <div>
              <Label className="text-xs">{t("description")}</Label>
              <Textarea
                value={form.descriptionEs}
                onChange={(e) => setForm(f => ({ ...f, descriptionEs: e.target.value }))}
                className="text-sm min-h-[50px]"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">{t("legalReference")}</Label>
                <Input
                  value={form.legalReference}
                  onChange={(e) => setForm(f => ({ ...f, legalReference: e.target.value }))}
                  className="h-8 text-sm"
                  placeholder={t("legalReferencePlaceholder")}
                />
              </div>
              <div>
                <Label className="text-xs">{t("frequency")}</Label>
                <Select value={form.installmentFrequency} onValueChange={(v) => setForm(f => ({ ...f, installmentFrequency: v }))}>
                  <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">{t("monthly")}</SelectItem>
                    <SelectItem value="bi-monthly">{t("biMonthly")}</SelectItem>
                    <SelectItem value="quarterly">{t("quarterly")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <Switch checked={form.installmentEligible} onCheckedChange={(v) => setForm(f => ({ ...f, installmentEligible: v }))} />
                <Label className="text-xs">{t("allowInstallments")}</Label>
              </div>
              {form.installmentEligible && (
                <div className="flex items-center gap-2">
                  <Label className="text-xs">{t("maxInstallments")}</Label>
                  <Input type="number" min={2} max={12} value={form.maxInstallments}
                    onChange={(e) => setForm(f => ({ ...f, maxInstallments: parseInt(e.target.value) || 2 }))}
                    className="h-8 text-sm w-16" />
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <Button size="sm" onClick={() => setStep(1)} disabled={!step1Valid}>
                {t("services")} <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Add Services */}
      {step === 1 && (
        <Card>
          <CardHeader className="py-3 px-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">{t("servicesByZone")}</CardTitle>
              <div className="flex items-center gap-2">
                <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                <Select value={selectedZone} onValueChange={setSelectedZone}>
                  <SelectTrigger className="h-7 text-xs w-[200px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {zones.map(z => <SelectItem key={z.id} value={z.id}>{z.zoneCode} — {z.nameEs}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 px-4 pb-4">
            {/* Service Picker */}
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <Label className="text-xs">{t("selectService")}</Label>
                <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start h-8 text-sm font-normal">
                      {addService ? (
                        <span className="truncate"><span className="font-mono mr-1">{addService.serviceCode}</span>{addService.nameEs}</span>
                      ) : (
                        <span className="text-muted-foreground">{t("searchService")}</span>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[450px] p-2" align="start">
                    <div className="relative mb-2">
                      <Search className="absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
                      <Input value={serviceSearch} onChange={(e) => setServiceSearch(e.target.value)}
                        placeholder={t("searchService")} className="pl-8 h-8 text-sm" autoFocus />
                    </div>
                    <div className="max-h-[220px] overflow-y-auto">
                      {serviceSearching ? (
                        <div className="text-center py-3"><Loader2 className="h-4 w-4 animate-spin mx-auto" /></div>
                      ) : serviceResults.length === 0 ? (
                        <div className="text-center py-3 text-xs text-muted-foreground">
                          {serviceSearch.length >= 2 ? t("noServiceFound") : t("searchService")}
                        </div>
                      ) : serviceResults.map((svc) => (
                        <button key={svc.id}
                          className="w-full text-left px-2 py-1.5 hover:bg-muted rounded text-sm flex items-center gap-2"
                          onClick={() => { setAddService(svc); setPickerOpen(false) }}>
                          <span className="font-mono text-xs text-muted-foreground w-14 shrink-0">{svc.serviceCode}</span>
                          <span className="truncate flex-1">{svc.nameEs}</span>
                          {svc.ministryName && <span className="text-[10px] text-muted-foreground truncate max-w-[100px]">{svc.ministryName}</span>}
                        </button>
                      ))}
                    </div>
                  </PopoverContent>
                </Popover>
              </div>
              <div className="w-28">
                <Label className="text-xs">{t("amount")}</Label>
                <Input type="number" step="1" min="0" value={addAmount}
                  onChange={(e) => setAddAmount(e.target.value)}
                  className="h-8 text-sm" placeholder="50000" />
              </div>
              <div className="flex items-center gap-1 pb-0.5">
                <Switch checked={addFixed} onCheckedChange={setAddFixed} />
                <Label className="text-[10px]">F</Label>
              </div>
              <Button size="sm" className="h-8" onClick={handleAddService} disabled={!addService || !addAmount}>
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>

            {/* Added Services List */}
            {pendingItems.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[70px]">{t("serviceCode")}</TableHead>
                    <TableHead>{t("serviceName")}</TableHead>
                    <TableHead>{t("ministry")}</TableHead>
                    <TableHead className="w-[110px] text-right">{t("amount")}</TableHead>
                    <TableHead className="w-[40px]">{t("fixed")}</TableHead>
                    <TableHead className="w-[40px]" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingItems.map((item, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-mono text-xs">{item.service.serviceCode}</TableCell>
                      <TableCell className="text-sm">{item.service.nameEs}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{item.service.ministryName || "—"}</TableCell>
                      <TableCell className="text-right font-mono font-medium">{formatXAF(item.amount)}</TableCell>
                      <TableCell>{item.isFixed && <Badge variant="outline" className="text-xs">F</Badge>}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive" onClick={() => handleRemoveService(idx)}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="bg-muted/50 font-bold">
                    <TableCell colSpan={3} className="text-right">{t("totalTreasury")}</TableCell>
                    <TableCell className="text-right font-mono">{formatXAF(totalAmount)}</TableCell>
                    <TableCell colSpan={2} />
                  </TableRow>
                </TableBody>
              </Table>
            )}

            {pendingItems.length === 0 && (
              <div className="text-center py-8 text-sm text-muted-foreground">{t("noServicesInZone")}</div>
            )}

            <div className="flex justify-between pt-2">
              <Button variant="outline" size="sm" onClick={() => setStep(0)}>
                <ArrowLeft className="h-4 w-4 mr-1" /> {t("bundleData")}
              </Button>
              <Button size="sm" onClick={() => setStep(2)} disabled={!step2Valid}>
                {t("total")} <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Review & Create */}
      {step === 2 && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm">{t("total")} — {form.nameEs}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 px-4 pb-4">
            {/* Summary */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="space-y-1">
                <div className="flex justify-between"><span className="text-muted-foreground">{t("code")}:</span><span className="font-mono">{form.bundleCode}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">{t("commerceType")}:</span><span>{form.commerceType}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">{t("legalReference")}:</span><span>{form.legalReference || "—"}</span></div>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between"><span className="text-muted-foreground">{t("zones")}:</span><span>{selectedZoneObj?.zoneCode} ({selectedZoneObj?.nameEs})</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">{t("services")}:</span><span>{pendingItems.length}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">{t("payment")}:</span>
                  <span>{form.installmentEligible ? `${form.maxInstallments}x ${form.installmentFrequency}` : t("single")}</span>
                </div>
              </div>
            </div>

            {/* Items Preview */}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[70px]">{t("serviceCode")}</TableHead>
                  <TableHead>{t("serviceName")}</TableHead>
                  <TableHead>{t("ministry")}</TableHead>
                  <TableHead className="w-[120px] text-right">{t("amount")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingItems.map((item, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-mono text-xs">{item.service.serviceCode}</TableCell>
                    <TableCell className="text-sm">{item.service.nameEs}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{item.service.ministryName || "—"}</TableCell>
                    <TableCell className="text-right font-mono">{formatXAF(item.amount)}</TableCell>
                  </TableRow>
                ))}
                <TableRow className="bg-primary/5 font-bold text-primary">
                  <TableCell colSpan={3} className="text-right">{t("totalTreasury")}</TableCell>
                  <TableCell className="text-right font-mono text-lg">{formatXAF(totalAmount)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>

            {/* Multi-zone copy option */}
            <div className="flex items-center gap-3 p-3 rounded-md bg-muted/50 border">
              <Checkbox
                id="copyToAllZones"
                checked={copyToAllZones}
                onCheckedChange={(v) => setCopyToAllZones(!!v)}
              />
              <div className="flex-1">
                <label htmlFor="copyToAllZones" className="text-sm font-medium cursor-pointer flex items-center gap-1.5">
                  <Copy className="h-3.5 w-3.5" />
                  {t("copyToAllZones")}
                </label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t("copyToAllZonesHint")}
                </p>
              </div>
            </div>

            {copyProgress && (
              <div className="flex items-center gap-2 text-sm text-primary">
                <Loader2 className="h-4 w-4 animate-spin" />
                {copyProgress}
              </div>
            )}

            {submitError && (
              <div className="p-3 rounded-md bg-destructive/10 border border-destructive/30 text-sm text-destructive">
                {submitError}
              </div>
            )}

            <div className="flex justify-between pt-2">
              <Button variant="outline" size="sm" onClick={() => setStep(1)}>
                <ArrowLeft className="h-4 w-4 mr-1" /> {t("services")}
              </Button>
              <Button size="sm" onClick={handleSubmit} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Check className="h-4 w-4 mr-1" />}
                {t("createBundle")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
