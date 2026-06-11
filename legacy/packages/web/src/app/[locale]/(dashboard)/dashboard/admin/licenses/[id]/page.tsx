"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  ArrowLeft, Pause, XCircle, RotateCcw, History, DollarSign,
  ListChecks, ChevronDown, ChevronUp, CheckCircle2, Clock,
  AlertTriangle, FileCheck, Banknote, Shield, RefreshCw,
  ChevronLeft, ChevronRight,
} from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { formatXAF } from "@/core/utils/format"
import { licenseApi, licenseAdminApi } from "@/modules/fiscal-services/services/license-api"
import type {
  LicenseResponse, ObligationResponse, ObligationStatus,
  ComplianceEventResponse, LicenseStatus, ComplianceEventType,
} from "@/types/commercial-license"
import type { FeeType } from "@/types/service-bundle"

const STATUS_COLORS: Record<LicenseStatus, string> = {
  open: "bg-blue-100 text-blue-800",
  partial: "bg-yellow-100 text-yellow-800",
  complete: "bg-green-100 text-green-800",
  overdue: "bg-red-100 text-red-800",
  suspended: "bg-gray-100 text-gray-800",
  closed: "bg-gray-200 text-gray-600",
}

const OBL_STATUS_COLORS: Record<ObligationStatus, string> = {
  pending: "bg-gray-100 text-gray-700",
  selected: "bg-blue-50 text-blue-700",
  payment_pending: "bg-amber-100 text-amber-800",
  paid: "bg-green-100 text-green-700",
  processing: "bg-blue-100 text-blue-800",
  completed: "bg-emerald-100 text-emerald-800",
  overdue: "bg-red-100 text-red-800",
  waived: "bg-yellow-100 text-yellow-700",
  cancelled: "bg-gray-200 text-gray-500",
}

const FEE_TYPE_STYLES: Record<FeeType, { bg: string; label: string }> = {
  tesoro: { bg: "bg-blue-50 border-blue-200", label: "feeTypeTesoro" },
  municipal: { bg: "bg-green-50 border-green-200", label: "feeTypeMunicipal" },
  chamber: { bg: "bg-amber-50 border-amber-200", label: "feeTypeChamber" },
}

const EVENT_ICONS: Partial<Record<ComplianceEventType, typeof CheckCircle2>> = {
  license_created: FileCheck,
  obligation_created: ListChecks,
  payment_initiated: Banknote,
  payment_validated: CheckCircle2,
  obligation_routed: RefreshCw,
  agent_approved: Shield,
  agent_rejected: XCircle,
  document_issued: FileCheck,
  obligation_completed: CheckCircle2,
  overdue_flagged: AlertTriangle,
  penalty_applied: AlertTriangle,
  license_completed: CheckCircle2,
  license_renewed: RotateCcw,
  license_suspended: Pause,
}

const EVENT_COLORS: Partial<Record<ComplianceEventType, string>> = {
  license_created: "text-blue-500",
  obligation_created: "text-blue-400",
  payment_initiated: "text-amber-500",
  payment_validated: "text-green-500",
  obligation_routed: "text-blue-600",
  agent_approved: "text-green-600",
  agent_rejected: "text-red-500",
  document_issued: "text-emerald-500",
  obligation_completed: "text-emerald-600",
  overdue_flagged: "text-red-500",
  penalty_applied: "text-red-600",
  license_completed: "text-green-700",
  license_renewed: "text-blue-700",
  license_suspended: "text-gray-500",
}

const EVENTS_PAGE_SIZE = 50

export default function LicenseDetailPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.licenses")
  const { toast } = useToast()
  const licenseId = params.id as string

  const [license, setLicense] = useState<LicenseResponse | null>(null)
  const [obligations, setObligations] = useState<ObligationResponse[]>([])
  const [events, setEvents] = useState<ComplianceEventResponse[]>([])
  const [eventsTotal, setEventsTotal] = useState(0)
  const [eventsPage, setEventsPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [expandedFeeTypes, setExpandedFeeTypes] = useState<Set<string>>(new Set(["tesoro", "municipal", "chamber"]))

  // Dialog states
  const [renewOpen, setRenewOpen] = useState(false)
  const [renewYear, setRenewYear] = useState(String(new Date().getFullYear() + 1))
  const [actionLoading, setActionLoading] = useState(false)

  // Load license + obligations
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [lic, oblRes] = await Promise.all([
        licenseApi.getLicense(licenseId),
        licenseApi.getObligations(licenseId, { pageSize: 500 }),
      ])
      setLicense(lic)
      setObligations(oblRes.items)
    } catch {
      toast({ variant: "destructive", title: t("loadError") })
    } finally {
      setLoading(false)
    }
  }, [licenseId, t, toast])

  useEffect(() => { loadData() }, [loadData])

  // Load events when tab changes
  const loadEvents = useCallback(async () => {
    try {
      const res = await licenseApi.getEvents(licenseId, { page: eventsPage, pageSize: EVENTS_PAGE_SIZE })
      setEvents(res.items)
      setEventsTotal(res.total)
    } catch {
      // silent — events are secondary
    }
  }, [licenseId, eventsPage])

  // Re-fetch events when page changes (initial load triggered by tab switch)
  useEffect(() => {
    if (eventsPage > 1) loadEvents()
  }, [eventsPage, loadEvents])

  // Group obligations by fee_type
  const grouped = obligations.reduce<Record<FeeType, ObligationResponse[]>>((acc, obl) => {
    const ft = obl.feeType as FeeType
    if (!acc[ft]) acc[ft] = []
    acc[ft].push(obl)
    return acc
  }, {} as Record<FeeType, ObligationResponse[]>)

  const toggleFeeType = (ft: string) => {
    setExpandedFeeTypes(prev => {
      const next = new Set(prev)
      next.has(ft) ? next.delete(ft) : next.add(ft)
      return next
    })
  }

  const oblStatusLabel = (status: ObligationStatus) => {
    const key = `oblStatus${status.split("_").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join("")}` as string
    try { return t(key as Parameters<typeof t>[0]) } catch { return status }
  }

  const eventLabel = (type: ComplianceEventType) => {
    const key = `event${type.split("_").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join("")}` as string
    try { return t(key as Parameters<typeof t>[0]) } catch { return type }
  }

  // Admin actions
  const handleStatusChange = async (newStatus: LicenseStatus) => {
    if (!license) return
    const confirmMsg = newStatus === "suspended" ? t("suspendConfirm") : t("closeConfirm")
    if (!window.confirm(confirmMsg)) return
    setActionLoading(true)
    try {
      await licenseAdminApi.updateLicense(licenseId, { status: newStatus })
      toast({ title: t("updateSuccess") })
      loadData()
    } catch {
      toast({ variant: "destructive", title: t("updateError") })
    } finally {
      setActionLoading(false)
    }
  }

  const handleRenew = async () => {
    setActionLoading(true)
    try {
      const newLic = await licenseAdminApi.renewLicense(licenseId, { fiscalYear: Number(renewYear) })
      toast({ title: t("renewSuccess") })
      setRenewOpen(false)
      router.push(`/${locale}/dashboard/admin/licenses/${newLic.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("updateError")
      toast({ variant: "destructive", title: t("updateError"), description: msg })
    } finally {
      setActionLoading(false)
    }
  }

  const handleCheckPreviousYear = async () => {
    setActionLoading(true)
    try {
      const res = await licenseAdminApi.checkPreviousYear(licenseId)
      toast({ title: t("checkPreviousYearSuccess", { checked: res.checked }) })
      loadData()
    } catch {
      toast({ variant: "destructive", title: t("updateError") })
    } finally {
      setActionLoading(false)
    }
  }

  const feeTypeSubtotal = (items: ObligationResponse[]) =>
    items.reduce((sum, o) => sum + Number(o.amount), 0)
  const feeTypePenaltyTotal = (items: ObligationResponse[]) =>
    items.reduce((sum, o) => sum + Number(o.penaltyAmount), 0)

  if (loading || !license) {
    return (
      <div className="p-6 text-center text-muted-foreground">{t("loading")}</div>
    )
  }

  const eventsTotalPages = Math.ceil(eventsTotal / EVENTS_PAGE_SIZE)
  const yearOptions = Array.from({ length: 5 }, (_, i) => license.fiscalYear + 1 + i)

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.push(`/${locale}/dashboard/admin/licenses`)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold">
              {license.companyName || license.companyId.slice(0, 8)}
              <span className="text-muted-foreground font-normal"> / {license.bundleName || "Bundle"}</span>
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Badge className={STATUS_COLORS[license.status]} variant="secondary">
                {t(`status${license.status.charAt(0).toUpperCase() + license.status.slice(1)}` as Parameters<typeof t>[0])}
              </Badge>
              <span className="text-sm text-muted-foreground">{t("year")}: {license.fiscalYear}</span>
              {license.zoneCode && (
                <span className="text-sm text-muted-foreground font-mono">{t("zone")}: {license.zoneCode}</span>
              )}
              <span className="text-xs text-muted-foreground">
                {license.processingMode === "per_line" ? t("perLine") : t("consolidated")}
              </span>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline" size="sm"
            onClick={async () => {
              try {
                const { default: apiClient } = await import('@/core/api/client')
                const response = await apiClient.get(
                  `/licenses/${licenseId}/download-pdf?language=${locale}`,
                  { responseType: 'blob' }
                )
                const blob = new Blob([response.data], { type: 'application/pdf' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `license-${licenseId}.pdf`
                a.click()
                setTimeout(() => URL.revokeObjectURL(url), 5000)
              } catch {
                toast({ title: 'Error', description: 'PDF generation failed', variant: 'destructive' })
              }
            }}
          >
            <FileCheck className="h-3.5 w-3.5 mr-1" /> PDF
          </Button>
          <Button variant="outline" size="sm" onClick={handleCheckPreviousYear} disabled={actionLoading}>
            <History className="h-3.5 w-3.5 mr-1" /> {t("checkPreviousYear")}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setRenewOpen(true)} disabled={actionLoading}>
            <RotateCcw className="h-3.5 w-3.5 mr-1" /> {t("renew")}
          </Button>
          {license.status !== "suspended" && license.status !== "closed" && (
            <Button variant="outline" size="sm" className="text-orange-600" onClick={() => handleStatusChange("suspended")} disabled={actionLoading}>
              <Pause className="h-3.5 w-3.5 mr-1" /> {t("suspend")}
            </Button>
          )}
          {license.status !== "closed" && (
            <Button variant="outline" size="sm" className="text-red-600" onClick={() => handleStatusChange("closed")} disabled={actionLoading}>
              <XCircle className="h-3.5 w-3.5 mr-1" /> {t("close")}
            </Button>
          )}
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-5 gap-3">
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("totalAmount")}</p>
          <p className="text-lg font-bold">{formatXAF(license.totalAmount, locale)}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("amountPaid")}</p>
          <p className="text-lg font-bold text-green-600">{formatXAF(license.amountPaid, locale)}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("pending")}</p>
          <p className="text-lg font-bold text-amber-600">
            {formatXAF(Number(license.totalAmount) - Number(license.amountPaid), locale)}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("penalty")}</p>
          <p className="text-lg font-bold text-red-600">{formatXAF(license.penaltyAmount, locale)}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("complianceScore")}</p>
          <p className={`text-lg font-bold ${
            Number(license.complianceScore || 0) >= 80 ? "text-green-600" :
            Number(license.complianceScore || 0) >= 50 ? "text-yellow-600" : "text-red-600"
          }`}>
            {license.complianceScore != null ? `${Number(license.complianceScore).toFixed(1)}%` : "—"}
          </p>
          <p className="text-xs text-muted-foreground">
            {license.obligationsPaid}/{license.obligationsTotal}
          </p>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="obligations" onValueChange={v => { if (v === "events") loadEvents() }}>
        <TabsList>
          <TabsTrigger value="obligations">
            <ListChecks className="h-3.5 w-3.5 mr-1" /> {t("obligations")} ({obligations.length})
          </TabsTrigger>
          <TabsTrigger value="events">
            <History className="h-3.5 w-3.5 mr-1" /> {t("events")}
          </TabsTrigger>
          <TabsTrigger value="financial">
            <DollarSign className="h-3.5 w-3.5 mr-1" /> {t("financial")}
          </TabsTrigger>
        </TabsList>

        {/* Tab: Obligations grouped by fee_type */}
        <TabsContent value="obligations" className="space-y-3 mt-3">
          {(["tesoro", "municipal", "chamber"] as FeeType[]).map(ft => {
            const items = grouped[ft] || []
            if (!items.length) return null
            const style = FEE_TYPE_STYLES[ft]
            const isExpanded = expandedFeeTypes.has(ft)
            return (
              <Card key={ft} className={`border ${style.bg}`}>
                <button
                  className="w-full flex items-center justify-between p-3 text-left"
                  onClick={() => toggleFeeType(ft)}
                >
                  <span className="font-bold text-sm">
                    {t(style.label as Parameters<typeof t>[0])} ({items.length})
                  </span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-mono">{formatXAF(feeTypeSubtotal(items), locale)}</span>
                    {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </div>
                </button>
                {isExpanded && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("serviceName")}</TableHead>
                        <TableHead>{t("ministry")}</TableHead>
                        <TableHead className="text-right">{t("amount")}</TableHead>
                        <TableHead className="text-right">{t("penalty")}</TableHead>
                        <TableHead className="w-[100px] text-center">{t("status")}</TableHead>
                        <TableHead className="w-[80px] text-center">{t("previousYear")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {items.map(obl => (
                        <TableRow key={obl.id}>
                          <TableCell className="text-sm max-w-[200px] truncate">{obl.serviceName || "—"}</TableCell>
                          <TableCell className="text-xs">{obl.ministryName || "—"}</TableCell>
                          <TableCell className="text-right text-xs font-mono">{formatXAF(obl.amount, locale)}</TableCell>
                          <TableCell className="text-right text-xs font-mono">
                            {Number(obl.penaltyAmount) > 0 ? (
                              <span className="text-red-600">{formatXAF(obl.penaltyAmount, locale)}</span>
                            ) : "—"}
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge className={`text-xs ${OBL_STATUS_COLORS[obl.status]}`} variant="secondary">
                              {oblStatusLabel(obl.status)}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            {obl.previousYearPaid === true ? (
                              <CheckCircle2 className="h-4 w-4 text-green-500 mx-auto" />
                            ) : obl.previousYearPaid === false ? (
                              <XCircle className="h-4 w-4 text-red-500 mx-auto" />
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                      {/* Subtotal row */}
                      <TableRow className="font-bold bg-muted/30">
                        <TableCell colSpan={3} className="text-right text-xs">{t("subtotal")}</TableCell>
                        <TableCell className="text-right text-xs font-mono">{formatXAF(feeTypeSubtotal(items), locale)}</TableCell>
                        <TableCell className="text-right text-xs font-mono">
                          {feeTypePenaltyTotal(items) > 0 ? formatXAF(feeTypePenaltyTotal(items), locale) : "—"}
                        </TableCell>
                        <TableCell colSpan={2} />
                      </TableRow>
                    </TableBody>
                  </Table>
                )}
              </Card>
            )
          })}
          {/* Grand total */}
          {obligations.length > 0 && (
            <div className="flex justify-end px-3">
              <div className="text-right">
                <span className="text-sm font-bold mr-4">{t("grandTotal")}</span>
                <span className="text-lg font-bold font-mono">{formatXAF(license.totalAmount, locale)}</span>
              </div>
            </div>
          )}
        </TabsContent>

        {/* Tab: Events Timeline */}
        <TabsContent value="events" className="mt-3">
          {events.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">{t("noEvents")}</p>
          ) : (
            <div className="space-y-1">
              {events.map(evt => {
                const Icon = EVENT_ICONS[evt.eventType] || Clock
                const color = EVENT_COLORS[evt.eventType] || "text-gray-400"
                return (
                  <div key={evt.id} className="flex items-start gap-3 py-2 px-3 hover:bg-muted/30 rounded">
                    <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{eventLabel(evt.eventType)}</span>
                          {evt.eventData?.source === "system_auto" && (
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-green-100 text-green-700 border-green-200">
                              Auto
                            </Badge>
                          )}
                          {evt.eventData?.source === "admin" && (
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-orange-100 text-orange-700 border-orange-200">
                              Admin
                            </Badge>
                          )}
                          {evt.eventData?.source === "agent" && (
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-blue-100 text-blue-700 border-blue-200">
                              Agent
                            </Badge>
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {new Date(evt.createdAt).toLocaleString(locale === "en" ? "en-US" : locale === "fr" ? "fr-FR" : "es-ES")}
                        </span>
                      </div>
                      {Boolean(evt.eventData?.old_status) && Boolean(evt.eventData?.new_status) && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {String(evt.eventData!.old_status)} → {String(evt.eventData!.new_status)}
                          {evt.eventData!.paid !== undefined && ` (${String(evt.eventData!.paid)}/${String(evt.eventData!.total)})`}
                        </p>
                      )}
                    </div>
                  </div>
                )
              })}
              {/* Events pagination */}
              {eventsTotalPages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-2">
                  <Button variant="outline" size="sm" disabled={eventsPage <= 1}
                    onClick={() => setEventsPage(p => p - 1)}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-xs text-muted-foreground">{eventsPage}/{eventsTotalPages}</span>
                  <Button variant="outline" size="sm" disabled={eventsPage >= eventsTotalPages}
                    onClick={() => setEventsPage(p => p + 1)}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          )}
        </TabsContent>

        {/* Tab: Financial Summary */}
        <TabsContent value="financial" className="mt-3">
          <div className="grid grid-cols-3 gap-4">
            {(["tesoro", "municipal", "chamber"] as FeeType[]).map(ft => {
              const items = grouped[ft] || []
              if (!items.length) return null
              const paid = items.filter(o => ["paid", "processing", "completed"].includes(o.status)).length
              const pending = items.filter(o => ["pending", "selected", "payment_pending"].includes(o.status)).length
              const overdue = items.filter(o => o.status === "overdue").length
              const total = items.length
              const style = FEE_TYPE_STYLES[ft]
              return (
                <Card key={ft} className="p-4">
                  <h3 className="text-sm font-bold mb-3">{t(style.label as Parameters<typeof t>[0])}</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span>{t("obligationsTotal")}</span>
                      <span className="font-bold">{total}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="flex h-2 rounded-full overflow-hidden">
                        <div className="bg-green-500" style={{ width: `${(paid / total) * 100}%` }} />
                        <div className="bg-amber-400" style={{ width: `${(pending / total) * 100}%` }} />
                        <div className="bg-red-500" style={{ width: `${(overdue / total) * 100}%` }} />
                      </div>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-green-600">{paid} {t("oblStatusPaid")}</span>
                      <span className="text-amber-600">{pending} {t("pending")}</span>
                      <span className="text-red-600">{overdue} {t("oblStatusOverdue")}</span>
                    </div>
                    <div className="pt-2 border-t mt-2">
                      <div className="flex justify-between text-xs">
                        <span>{t("subtotal")}</span>
                        <span className="font-mono font-bold">{formatXAF(feeTypeSubtotal(items), locale)}</span>
                      </div>
                      {feeTypePenaltyTotal(items) > 0 && (
                        <div className="flex justify-between text-xs mt-1">
                          <span className="text-red-600">{t("penalty")}</span>
                          <span className="font-mono text-red-600">{formatXAF(feeTypePenaltyTotal(items), locale)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        </TabsContent>
      </Tabs>

      {/* Renew Dialog */}
      <Dialog open={renewOpen} onOpenChange={setRenewOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("renewTitle")}</DialogTitle>
            <DialogDescription>{t("renewDesc")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>{t("renewYear")}</Label>
              <Select value={renewYear} onValueChange={setRenewYear}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {yearOptions.map(y => (
                    <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={handleRenew} disabled={actionLoading}>
              {actionLoading ? t("creating") : t("renew")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
