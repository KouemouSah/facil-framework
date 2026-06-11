"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  ArrowLeft, Download, FileText, CreditCard, MapPin, Pencil, Printer, Eye,
} from "lucide-react"
import { bundleApi, bundleAdminApi } from "@/modules/fiscal-services/services/bundle-api"
import { formatXAF } from "@/core/utils/format"
import { FICHE_PRINT_STYLES } from "@/modules/fiscal-services/constants/fiche-styles"
import type {
  ServiceBundle, CommerceZone, BundleItem, BundleDocument,
  ZoneTotal, InstallmentPreview, FeeType, FeeTypeTotals,
} from "@/types/service-bundle"
import { FEE_TYPE_LABELS } from "@/types/service-bundle"

export default function BundleDetailPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.serviceBundles")
  const bundleId = params.id as string

  const [bundle, setBundle] = useState<ServiceBundle | null>(null)
  const [zones, setZones] = useState<CommerceZone[]>([])
  const [selectedZone, setSelectedZone] = useState<string>("")
  const [items, setItems] = useState<BundleItem[]>([])
  const [zoneTotals, setZoneTotals] = useState<ZoneTotal[]>([])
  const [documents, setDocuments] = useState<BundleDocument[]>([])
  const [installmentPreview, setInstallmentPreview] = useState<InstallmentPreview | null>(null)
  const [totalAmount, setTotalAmount] = useState<string>("0")
  const [feeTypeTotals, setFeeTypeTotals] = useState<FeeTypeTotals | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCode, setShowCode] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const [b, z, docs] = await Promise.all([
          bundleApi.getBundle(bundleId),
          bundleApi.listZones(),
          bundleApi.getBundleDocuments(bundleId),
        ])
        setBundle(b)
        setZones(z)
        setDocuments(docs)
        if (z.length > 0) setSelectedZone(z[0].id)
      } catch (err) {
        console.error("Failed to load bundle:", err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [bundleId])

  useEffect(() => {
    if (!selectedZone || !bundleId) return
    async function loadPricing() {
      try {
        const pricing = await bundleApi.getBundlePricing(bundleId, selectedZone)
        setItems(pricing.items || [])
        setTotalAmount(String(pricing.totalAmount || "0"))
        setFeeTypeTotals(pricing.feeTypeTotals || null)
      } catch (err) {
        console.error("Failed to load pricing:", err)
      }
    }
    loadPricing()
  }, [bundleId, selectedZone])

  useEffect(() => {
    if (!bundleId) return
    bundleApi.getPricingMatrix(bundleId)
      .then(matrix => setZoneTotals(matrix.zoneTotals || []))
      .catch(() => {})
  }, [bundleId])

  useEffect(() => {
    if (!selectedZone || !bundle?.installmentEligible) {
      setInstallmentPreview(null)
      return
    }
    bundleApi.previewInstallments(bundleId, selectedZone, bundle.maxInstallments)
      .then(setInstallmentPreview)
      .catch(() => setInstallmentPreview(null))
  }, [bundleId, selectedZone, bundle])

  const handleExport = async (format: "csv" | "xlsx" = "xlsx") => {
    if (!bundle) return
    try {
      const blob = format === "xlsx"
        ? await bundleAdminApi.exportXlsx(bundleId)
        : await bundleAdminApi.exportCsv(bundleId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `bundle_${bundle.bundleCode}_matrix.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error("Export failed:", err)
    }
  }

  if (loading) return <div className="p-8 text-center text-muted-foreground">{t("loading")}</div>
  if (!bundle) return <div className="p-8 text-center text-destructive">{t("notFound")}</div>

  const selectedZoneObj = zones.find(z => z.id === selectedZone)

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push(`/${locale}/dashboard/admin/service-bundles`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">{bundle.nameEs}</h1>
            <Badge variant={bundle.isActive ? "default" : "secondary"}>
              {bundle.isActive ? t("active") : t("inactive")}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {bundle.bundleCode} — {bundle.commerceType}
            {bundle.legalReference && ` — ${bundle.legalReference}`}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => router.push(`/${locale}/dashboard/admin/service-bundles/${bundleId}/edit`)}>
          <Pencil className="h-4 w-4 mr-1" /> {t("edit")}
        </Button>
        <Button variant="outline" size="sm" onClick={() => handleExport("xlsx")}>
          <Download className="h-4 w-4 mr-1" /> Excel
        </Button>
        <Button variant="ghost" size="sm" onClick={() => handleExport("csv")}>
          {t("csv")}
        </Button>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-4 gap-3">
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("services")}</p>
          <p className="text-lg font-bold">{bundle.itemCount}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("zones")}</p>
          <p className="text-lg font-bold">{bundle.zoneCount}/{zones.length}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("payment")}</p>
          <p className="text-lg font-bold">
            {bundle.installmentEligible ? `${bundle.maxInstallments}x ${bundle.installmentFrequency}` : t("single")}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted-foreground">{t("total")} ({selectedZoneObj?.zoneCode || "—"})</p>
          <p className="text-lg font-bold">{formatXAF(totalAmount)}</p>
        </Card>
      </div>

      <Tabs defaultValue="pricing" className="space-y-3">
        <TabsList>
          <TabsTrigger value="pricing">
            <CreditCard className="h-3.5 w-3.5 mr-1" /> {t("pricingByZone")}
          </TabsTrigger>
          <TabsTrigger value="matrix">
            <MapPin className="h-3.5 w-3.5 mr-1" /> {t("zoneSummary")}
          </TabsTrigger>
          <TabsTrigger value="documents">
            <FileText className="h-3.5 w-3.5 mr-1" /> {t("documents")} ({documents.length})
          </TabsTrigger>
          <TabsTrigger value="fiche">
            <Eye className="h-3.5 w-3.5 mr-1" /> {t("previewFiche")}
          </TabsTrigger>
        </TabsList>

        {/* Pricing Tab */}
        <TabsContent value="pricing" className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex gap-1 flex-wrap">
              {zones.map((zone) => (
                <Button
                  key={zone.id}
                  variant={selectedZone === zone.id ? "default" : "outline"}
                  size="sm" className="h-7 text-xs"
                  onClick={() => setSelectedZone(zone.id)}
                >
                  {zone.zoneCode}
                </Button>
              ))}
            </div>
            <Button
              variant="ghost" size="sm" className="h-7 text-xs"
              onClick={() => setShowCode(!showCode)}
            >
              {showCode ? t("hideCode") : t("showCode")}
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    {showCode && <TableHead className="w-[80px]">{t("serviceCode")}</TableHead>}
                    <TableHead>{t("serviceName")}</TableHead>
                    <TableHead>{t("ministry")}</TableHead>
                    <TableHead className="w-[80px] text-center">{t("type")}</TableHead>
                    <TableHead className="w-[120px] text-right">{t("amount")}</TableHead>
                    <TableHead className="w-[60px] text-center">{t("fixed")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={item.id}>
                      {showCode && <TableCell className="font-mono text-xs">{item.serviceCode}</TableCell>}
                      <TableCell className="text-sm">{item.serviceName}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{item.ministryName}</TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={`text-[10px] ${
                          item.feeType === "municipal" ? "border-green-600 text-green-700" :
                          item.feeType === "chamber" ? "border-amber-600 text-amber-700" :
                          ""
                        }`}>
                          {item.feeType === "tesoro" ? "T" : item.feeType === "municipal" ? "M" : "C"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium">{formatXAF(item.amount)}</TableCell>
                      <TableCell className="text-center">
                        {item.isFixedAcrossZones && <Badge variant="outline" className="text-xs">F</Badge>}
                      </TableCell>
                    </TableRow>
                  ))}
                  {feeTypeTotals && Number(feeTypeTotals.tesoro) > 0 && (
                    <TableRow className="bg-blue-50">
                      <TableCell colSpan={4} className="text-right text-xs font-medium">Sub-total Tesoro Público</TableCell>
                      <TableCell className="text-right font-mono font-medium">{formatXAF(feeTypeTotals.tesoro)}</TableCell>
                      <TableCell />
                    </TableRow>
                  )}
                  {feeTypeTotals && Number(feeTypeTotals.municipal) > 0 && (
                    <TableRow className="bg-green-50">
                      <TableCell colSpan={4} className="text-right text-xs font-medium">Sub-total Ayuntamiento</TableCell>
                      <TableCell className="text-right font-mono font-medium">{formatXAF(feeTypeTotals.municipal)}</TableCell>
                      <TableCell />
                    </TableRow>
                  )}
                  {feeTypeTotals && Number(feeTypeTotals.chamber) > 0 && (
                    <TableRow className="bg-amber-50">
                      <TableCell colSpan={4} className="text-right text-xs font-medium">Sub-total Cámara de Comercio</TableCell>
                      <TableCell className="text-right font-mono font-medium">{formatXAF(feeTypeTotals.chamber)}</TableCell>
                      <TableCell />
                    </TableRow>
                  )}
                  <TableRow className="bg-muted/50 font-bold">
                    <TableCell colSpan={4} className="text-right">{t("ficheGrandTotal")}</TableCell>
                    <TableCell className="text-right font-mono">{formatXAF(feeTypeTotals?.grandTotal || totalAmount)}</TableCell>
                    <TableCell />
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {installmentPreview && (
            <Card>
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-sm">
                  {t("paymentPlan")} ({installmentPreview.numInstallments} {t("installments")} {installmentPreview.frequency})
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-3">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[60px]">#</TableHead>
                      <TableHead>{t("dueDate")}</TableHead>
                      <TableHead className="text-right">{t("amount")}</TableHead>
                      <TableHead className="text-right">{t("accumulated")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {installmentPreview.installments.map((inst) => (
                      <TableRow key={inst.installmentNumber}>
                        <TableCell>{inst.installmentNumber}</TableCell>
                        <TableCell>{inst.dueDate}</TableCell>
                        <TableCell className="text-right font-mono">{formatXAF(inst.amountDue)}</TableCell>
                        <TableCell className="text-right font-mono text-muted-foreground">{formatXAF(inst.cumulativePaid)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <p className="text-xs text-muted-foreground mt-2">
                  {t("gracePeriod")}: {installmentPreview.gracePeriodDays} {t("days")} —
                  {t("lateFee")}: {(parseFloat(installmentPreview.lateFeeRate) * 100).toFixed(0)}%
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Zone Totals Tab */}
        <TabsContent value="matrix">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]">{t("code")}</TableHead>
                    <TableHead>{t("name")}</TableHead>
                    <TableHead className="w-[50px] text-center">{t("tier")}</TableHead>
                    <TableHead className="w-[110px] text-right">Tesoro</TableHead>
                    <TableHead className="w-[110px] text-right">Ayunt.</TableHead>
                    <TableHead className="w-[110px] text-right">Cámara</TableHead>
                    <TableHead className="w-[120px] text-right font-bold">{t("total")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {zoneTotals.map((zt) => (
                    <TableRow
                      key={zt.zone.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => setSelectedZone(zt.zone.id)}
                    >
                      <TableCell className="font-mono font-bold">{zt.zone.zoneCode}</TableCell>
                      <TableCell className="text-sm">{zt.zone.nameEs}</TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">{zt.zone.zoneTier}</Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">{formatXAF(zt.tesoroTotal)}</TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        {Number(zt.municipalTotal) > 0 ? formatXAF(zt.municipalTotal) : <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        {Number(zt.chamberTotal) > 0 ? formatXAF(zt.chamberTotal) : <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-right font-mono font-bold">{formatXAF(zt.totalAmount)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("documentName")}</TableHead>
                    <TableHead className="w-[120px]">{t("templateCode")}</TableHead>
                    <TableHead className="w-[100px] text-center">{t("required")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center py-6 text-muted-foreground">
                        {t("noDocuments")}
                      </TableCell>
                    </TableRow>
                  ) : (
                    documents.map((doc) => (
                      <TableRow key={doc.documentTemplateId}>
                        <TableCell className="text-sm">{doc.documentNameEs}</TableCell>
                        <TableCell className="font-mono text-xs">{doc.templateCode || "—"}</TableCell>
                        <TableCell className="text-center">
                          <Badge variant={doc.isRequired ? "default" : "outline"} className="text-xs">
                            {doc.isRequired ? t("yes") : t("no")}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Fiche Preview Tab — grouped by fee_type with sub-totals */}
        <TabsContent value="fiche">
          <div className="space-y-3">
            <div className="flex justify-end">
              <Button size="sm" variant="outline" onClick={() => {
                const pw = window.open("", "_blank")
                if (!pw) return
                const html = document.getElementById("fiche-detail-preview")?.innerHTML
                pw.document.write(`<html><head><title>${t("ficheTitle")}</title>
                  <style>${FICHE_PRINT_STYLES}</style></head><body>${html}</body></html>`)
                pw.document.close()
                pw.print()
              }}>
                <Printer className="h-3.5 w-3.5 mr-1" /> {t("fichePrint")}
              </Button>
            </div>
            <div id="fiche-detail-preview" className="bg-white border rounded-lg p-6 text-black text-xs">
              <div className="text-center mb-6">
                <div className="text-[10px] text-gray-500 mb-1">{t("ficheSubtitle")}</div>
                <div className="text-sm font-bold tracking-widest">{t("ficheTitle")}</div>
                <div className="w-24 h-0.5 bg-blue-900 mx-auto mt-2" />
              </div>
              <div className="flex justify-between text-[11px] mb-4 border-b pb-2">
                <div><strong>{t("ficheCommerceType")}:</strong> {bundle.commerceType}</div>
                <div><strong>{t("ficheZone")}:</strong> {selectedZoneObj?.zoneCode} — {selectedZoneObj?.nameEs}</div>
                <div><strong>{t("ficheDate")}:</strong> {new Date().toLocaleDateString("es-GQ")}</div>
              </div>
              {bundle.legalReference && (
                <div className="text-[10px] text-gray-600 mb-3">
                  <strong>{t("ficheRef")}:</strong> {bundle.legalReference}
                </div>
              )}

              {/* Group items by fee_type */}
              {(["tesoro", "municipal", "chamber"] as FeeType[]).map((ft) => {
                const ftItems = items.filter(i => (i.feeType || "tesoro") === ft)
                if (ftItems.length === 0) return null
                const ftLabel = FEE_TYPE_LABELS[ft]
                const ftTotal = feeTypeTotals ? Number(feeTypeTotals[ft] || 0) : ftItems.reduce((s, i) => s + Number(i.amount), 0)
                return (
                  <div key={ft} className="mb-4">
                    <div className={`text-[11px] font-bold px-2 py-1 mb-1 ${
                      ft === "tesoro" ? "bg-blue-900 text-white" :
                      ft === "municipal" ? "bg-green-800 text-white" :
                      "bg-amber-700 text-white"
                    }`}>
                      {ftLabel.es}
                    </div>
                    <table className="w-full border-collapse">
                      <thead>
                        <tr className="bg-gray-100">
                          <th className="border px-2 py-1 text-left w-[70px] text-[10px]">{t("ficheServiceCode")}</th>
                          <th className="border px-2 py-1 text-left text-[10px]">{t("ficheServiceName")}</th>
                          <th className="border px-2 py-1 text-left text-[10px]">{t("ficheMinistry")}</th>
                          <th className="border px-2 py-1 text-right w-[100px] text-[10px]">{t("ficheAmount")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ftItems.map(item => (
                          <tr key={item.id}>
                            <td className="border px-2 py-1 font-mono">{item.serviceCode}</td>
                            <td className="border px-2 py-1">{item.serviceName}</td>
                            <td className="border px-2 py-1 text-gray-600">{item.ministryName}</td>
                            <td className="border px-2 py-1 text-right font-mono">{formatXAF(item.amount)}</td>
                          </tr>
                        ))}
                        <tr className="bg-gray-200 font-bold text-[10px]">
                          <td className="border px-2 py-1" colSpan={3}>SUB-TOTAL {ftLabel.es}</td>
                          <td className="border px-2 py-1 text-right font-mono">{formatXAF(ftTotal)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )
              })}

              {/* Grand Total */}
              <div className="bg-blue-950 text-white font-bold text-sm px-3 py-2 flex justify-between items-center mt-2">
                <span>{t("ficheGrandTotal")}</span>
                <span className="font-mono">{formatXAF(feeTypeTotals?.grandTotal || totalAmount)}</span>
              </div>

              <div className="text-center mt-6 pt-3 border-t border-gray-300 text-[9px] text-gray-500">
                {bundle.bundleCode} — {t("ficheSubtitle")} — {new Date().toLocaleDateString("es-GQ")}
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
