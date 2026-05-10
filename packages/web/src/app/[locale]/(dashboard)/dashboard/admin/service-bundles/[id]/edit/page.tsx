"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog"
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover"
import {
  ArrowLeft, Save, Plus, Trash2, Copy, Loader2, Search,
  Upload, FileSpreadsheet, FileText, GripVertical, Eye, Printer,
} from "lucide-react"
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy, arrayMove,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { bundleApi, bundleAdminApi } from "@/modules/fiscal-services/services/bundle-api"
import { useToast } from "@/hooks/use-toast"
import { formatXAF } from "@/core/utils/format"
import type {
  ServiceBundle, CommerceZone, BundleItem, FiscalServiceOption,
  BulkImportItem, ParsedPdfItem, FeeType,
} from "@/types/service-bundle"
import { FEE_TYPE_LABELS } from "@/types/service-bundle"

import { FICHE_PRINT_STYLES } from "@/modules/fiscal-services/constants/fiche-styles"

// ============================================================
// Sortable Row Component (drag-drop)
// ============================================================
function SortableRow({
  item, onDelete,
}: {
  item: BundleItem
  onDelete: (id: string) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <TableRow ref={setNodeRef} style={style}>
      <TableCell className="w-[30px] cursor-grab" {...attributes} {...listeners}>
        <GripVertical className="h-3.5 w-3.5 text-muted-foreground" />
      </TableCell>
      <TableCell className="font-mono text-xs">{item.serviceCode}</TableCell>
      <TableCell className="text-sm">{item.serviceName}</TableCell>
      <TableCell className="text-xs text-muted-foreground">{item.ministryName}</TableCell>
      <TableCell className="text-right font-mono font-medium">{formatXAF(item.amount)}</TableCell>
      <TableCell className="text-center">
        {item.isFixedAcrossZones && <Badge variant="outline" className="text-xs">F</Badge>}
      </TableCell>
      <TableCell>
        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:text-destructive"
          onClick={() => onDelete(item.id)}>
          <Trash2 className="h-3 w-3" />
        </Button>
      </TableCell>
    </TableRow>
  )
}

// ============================================================
// Preview Fiche — grouped by fee_type with sub-totals + grand total
// ============================================================
function FichePreview({
  bundle, zone, items, totalAmount, t,
}: {
  bundle: ServiceBundle
  zone: CommerceZone | undefined
  items: BundleItem[]
  totalAmount: string
  t: (key: string) => string
}) {
  const handlePrint = () => {
    const printWindow = window.open("", "_blank")
    if (!printWindow) return
    const html = document.getElementById("fiche-preview")?.innerHTML
    printWindow.document.write(`
      <html><head><title>${t("ficheTitle")}</title>
      <style>${FICHE_PRINT_STYLES}</style></head><body>${html}</body></html>
    `)
    printWindow.document.close()
    printWindow.print()
  }

  const today = new Date().toLocaleDateString("es-GQ", { year: "numeric", month: "long", day: "numeric" })

  const feeTypeColors: Record<FeeType, { bg: string; text: string }> = {
    tesoro: { bg: "bg-blue-900", text: "text-white" },
    municipal: { bg: "bg-green-800", text: "text-white" },
    chamber: { bg: "bg-amber-700", text: "text-white" },
  }

  const feeTypes: FeeType[] = ["tesoro", "municipal", "chamber"]
  let grandTotal = 0

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={handlePrint}>
          <Printer className="h-3.5 w-3.5 mr-1" /> {t("fichePrint")}
        </Button>
      </div>
      <div id="fiche-preview" className="bg-white border rounded-lg p-6 text-black text-xs">
        {/* Header */}
        <div className="header text-center mb-6">
          <div className="text-[10px] text-gray-500 mb-1">{t("ficheSubtitle")}</div>
          <h1 className="text-sm font-bold tracking-widest">{t("ficheTitle")}</h1>
          <div className="w-24 h-0.5 bg-blue-900 mx-auto mt-2" />
        </div>

        {/* Meta */}
        <div className="flex justify-between text-[11px] mb-4 border-b pb-2">
          <div><strong>{t("ficheCommerceType")}:</strong> {bundle.commerceType}</div>
          <div><strong>{t("ficheZone")}:</strong> {zone?.zoneCode} — {zone?.nameEs}</div>
          <div><strong>{t("ficheDate")}:</strong> {today}</div>
        </div>
        {bundle.legalReference && (
          <div className="text-[10px] text-gray-600 mb-3">
            <strong>{t("ficheRef")}:</strong> {bundle.legalReference}
          </div>
        )}

        {/* Items grouped by fee_type → then by ministry */}
        {feeTypes.map(ft => {
          const ftItems = items.filter(i => (i.feeType || "tesoro") === ft)
          if (ftItems.length === 0) return null
          const ftTotal = ftItems.reduce((s, i) => s + Number(i.amount), 0)
          grandTotal += ftTotal
          const colors = feeTypeColors[ft]
          const label = FEE_TYPE_LABELS[ft]

          // Group by ministry within fee_type
          const byMinistry: Record<string, BundleItem[]> = {}
          ftItems.forEach(item => {
            const key = item.ministryName || "—"
            if (!byMinistry[key]) byMinistry[key] = []
            byMinistry[key].push(item)
          })

          return (
            <div key={ft} className="mb-4">
              <div className={`text-[11px] font-bold px-2 py-1 mb-1 ${colors.bg} ${colors.text}`}>
                {label.es}
              </div>
              {Object.entries(byMinistry).map(([ministry, ministryItems]) => (
                <div key={ministry} className="mb-2">
                  {Object.keys(byMinistry).length > 1 && (
                    <div className="text-[10px] font-medium text-gray-700 px-1 mb-0.5">{ministry}</div>
                  )}
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="bg-gray-100">
                        <th className="border px-2 py-1 text-left w-[70px] text-[10px]">{t("ficheServiceCode")}</th>
                        <th className="border px-2 py-1 text-left text-[10px]">{t("ficheServiceName")}</th>
                        <th className="border px-2 py-1 text-right w-[100px] text-[10px]">{t("ficheAmount")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ministryItems.map(item => (
                        <tr key={item.id}>
                          <td className="border px-2 py-1 font-mono">{item.serviceCode}</td>
                          <td className="border px-2 py-1">{item.serviceName}</td>
                          <td className="border px-2 py-1 text-right font-mono">{formatXAF(item.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
              <div className="bg-gray-200 font-bold text-[10px] px-2 py-1 flex justify-between">
                <span>SUB-TOTAL {label.es}</span>
                <span className="font-mono">{formatXAF(ftTotal)}</span>
              </div>
            </div>
          )
        })}

        {/* Grand Total */}
        <div className="bg-blue-950 text-white font-bold text-sm px-3 py-2 flex justify-between items-center mt-2">
          <span>{t("ficheGrandTotal")}</span>
          <span className="font-mono">{formatXAF(grandTotal || totalAmount)}</span>
        </div>

        {/* Footer */}
        <div className="footer text-center mt-6 pt-3 border-t border-gray-300 text-[9px] text-gray-500">
          {bundle.bundleCode} — {t("ficheSubtitle")} — {today}
        </div>
      </div>
    </div>
  )
}

// ============================================================
// Main Edit Page
// ============================================================
export default function BundleEditPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.serviceBundles")
  const { toast } = useToast()
  const bundleId = params.id as string

  // Bundle metadata
  const [bundle, setBundle] = useState<ServiceBundle | null>(null)
  const [form, setForm] = useState({
    bundleCode: "", commerceType: "", nameEs: "", descriptionEs: "",
    legalReference: "", isActive: true, installmentEligible: false,
    maxInstallments: 1, installmentFrequency: "monthly",
  })

  // Zones & items
  const [zones, setZones] = useState<CommerceZone[]>([])
  const [selectedZone, setSelectedZone] = useState<string>("")
  const [items, setItems] = useState<BundleItem[]>([])
  const [totalAmount, setTotalAmount] = useState("0")

  // UI state
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [itemSaving, setItemSaving] = useState(false)
  const [showAddItem, setShowAddItem] = useState(false)
  const [showCopyZone, setShowCopyZone] = useState(false)
  const [activeTab, setActiveTab] = useState("items")

  // Service search
  const [serviceSearch, setServiceSearch] = useState("")
  const [serviceResults, setServiceResults] = useState<FiscalServiceOption[]>([])
  const [serviceSearching, setServiceSearching] = useState(false)
  const [selectedService, setSelectedService] = useState<FiscalServiceOption | null>(null)
  const [servicePickerOpen, setServicePickerOpen] = useState(false)
  const searchTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Add item form
  const [newItemAmount, setNewItemAmount] = useState("")
  const [newItemFixed, setNewItemFixed] = useState(false)

  // Copy zone form
  const [copySource, setCopySource] = useState("")
  const [copyTarget, setCopyTarget] = useState("")
  const [copyMultiplier, setCopyMultiplier] = useState("1.0")

  // Import state
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importParsing, setImportParsing] = useState(false)
  const [importPreview, setImportPreview] = useState<BulkImportItem[]>([])
  const [importError, setImportError] = useState("")
  const [importResult, setImportResult] = useState("")

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  // Load bundle + zones
  useEffect(() => {
    async function load() {
      try {
        const [b, z] = await Promise.all([bundleApi.getBundle(bundleId), bundleApi.listZones()])
        setBundle(b)
        setForm({
          bundleCode: b.bundleCode, commerceType: b.commerceType,
          nameEs: b.nameEs, descriptionEs: b.descriptionEs || "",
          legalReference: b.legalReference || "", isActive: b.isActive,
          installmentEligible: b.installmentEligible,
          maxInstallments: b.maxInstallments,
          installmentFrequency: b.installmentFrequency,
        })
        setZones(z)
        if (z.length > 0) setSelectedZone(z[0].id)
      } catch (err) { console.error("Failed to load bundle:", err) }
      finally { setLoading(false) }
    }
    load()
  }, [bundleId])

  // Load items for selected zone
  const loadItems = useCallback(async () => {
    if (!selectedZone || !bundleId) return
    try {
      const pricing = await bundleApi.getBundlePricing(bundleId, selectedZone)
      setItems(pricing.items || [])
      setTotalAmount(String(pricing.totalAmount || "0"))
    } catch (err) { console.error("Failed to load pricing:", err) }
  }, [bundleId, selectedZone])

  useEffect(() => { loadItems() }, [loadItems])

  // Debounced service search
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    if (!serviceSearch || serviceSearch.length < 2) { setServiceResults([]); return }
    searchTimerRef.current = setTimeout(async () => {
      setServiceSearching(true)
      try { setServiceResults(await bundleAdminApi.searchServices(serviceSearch)) }
      catch { setServiceResults([]) }
      finally { setServiceSearching(false) }
    }, 300)
    return () => { if (searchTimerRef.current) clearTimeout(searchTimerRef.current) }
  }, [serviceSearch])

  // Save metadata
  const handleSaveMetadata = async () => {
    setSaving(true)
    try {
      const updated = await bundleAdminApi.updateBundle(bundleId, {
        bundleCode: form.bundleCode, commerceType: form.commerceType, nameEs: form.nameEs,
        descriptionEs: form.descriptionEs || undefined, legalReference: form.legalReference || undefined,
        isActive: form.isActive, installmentEligible: form.installmentEligible,
        maxInstallments: form.maxInstallments, installmentFrequency: form.installmentFrequency,
      })
      setBundle(updated)
      toast({ title: t("saveSuccess") })
    } catch (err) {
      console.error("Save failed:", err)
      toast({ variant: "destructive", title: t("saveError") })
    } finally { setSaving(false) }
  }

  // Add item
  const handleAddItem = async () => {
    if (!selectedService || !newItemAmount) return
    setItemSaving(true)
    try {
      await bundleAdminApi.upsertItem(bundleId, {
        fiscalServiceId: selectedService.id, zoneId: selectedZone,
        ministryId: selectedService.ministryId ?? undefined,
        amount: parseFloat(newItemAmount), isFixedAcrossZones: newItemFixed,
      })
      setShowAddItem(false); setSelectedService(null); setServiceSearch("")
      setNewItemAmount(""); setNewItemFixed(false); await loadItems()
    } catch (err) { console.error("Add item failed:", err) }
    finally { setItemSaving(false) }
  }

  // Delete item
  const handleDeleteItem = async (itemId: string) => {
    try { await bundleAdminApi.deleteItem(itemId); await loadItems() }
    catch (err) { console.error("Delete item failed:", err) }
  }

  // Copy zone prices
  const handleCopyZone = async () => {
    if (!copySource || !copyTarget) return
    setItemSaving(true)
    try {
      await bundleAdminApi.copyZonePrices(bundleId, {
        sourceZoneId: copySource, targetZoneId: copyTarget,
        multiplier: parseFloat(copyMultiplier) || 1.0,
      })
      setShowCopyZone(false); await loadItems()
    } catch (err) { console.error("Copy zone failed:", err) }
    finally { setItemSaving(false) }
  }

  // Drag-drop reorder
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = items.findIndex(i => i.id === active.id)
    const newIndex = items.findIndex(i => i.id === over.id)
    const reordered = arrayMove(items, oldIndex, newIndex)
    setItems(reordered)
    try {
      await bundleAdminApi.reorderItems(bundleId, reordered.map(i => i.id))
    } catch (err) { console.error("Reorder failed:", err) }
  }

  // Parse import file (Excel or PDF)
  const handleParseFile = async () => {
    if (!importFile) return
    setImportParsing(true); setImportError(""); setImportPreview([])

    try {
      const ext = importFile.name.toLowerCase().split(".").pop()

      if (ext === "xlsx" || ext === "xls") {
        // Parse Excel client-side with SheetJS
        const XLSX = await import("xlsx")
        const arrayBuffer = await importFile.arrayBuffer()
        const workbook = XLSX.read(arrayBuffer, { type: "array" })
        const sheet = workbook.Sheets[workbook.SheetNames[0]]
        const rows = XLSX.utils.sheet_to_json(sheet, { header: 1 }) as unknown[][]
        if (rows.length < 2) throw new Error("Empty spreadsheet")

        // Header: first row — look for zone codes
        const header = (rows[0] as unknown[]).map(c => String(c || "").trim().toUpperCase())
        const zoneCodeSet = new Set(zones.map(z => z.zoneCode))
        const zoneColMap: Record<number, string> = {}
        let serviceCol = 0
        header.forEach((cell, ci) => {
          if (zoneCodeSet.has(cell)) zoneColMap[ci] = cell
          if (["CÓDIGO", "CODIGO", "CODE", "SERVICE_CODE"].includes(cell)) serviceCol = ci
        })

        if (Object.keys(zoneColMap).length === 0) {
          throw new Error("No zone columns found (A1, A2, B1, etc.) in header")
        }

        const parsed: BulkImportItem[] = []
        for (let r = 1; r < rows.length; r++) {
          const row = rows[r] as unknown[]
          const rawCode = String(row[serviceCol] || "").trim().toUpperCase()
          if (!rawCode) continue
          for (const [ci, zoneCode] of Object.entries(zoneColMap)) {
            const val = row[parseInt(ci)]
            const amt = typeof val === "number" ? val : parseFloat(String(val || "0").replace(/[^\d.]/g, ""))
            if (amt > 0) {
              parsed.push({ serviceCode: rawCode, zoneCode, amount: amt })
            }
          }
        }
        setImportPreview(parsed)
      } else if (ext === "pdf") {
        // Send to backend for pdfplumber extraction
        const result = await bundleAdminApi.parsePdf(bundleId, importFile)
        setImportPreview(
          result.extractedItems.map((it: ParsedPdfItem) => ({
            serviceCode: it.serviceCode,
            zoneCode: it.zoneCode,
            amount: it.amount,
            isFixedAcrossZones: it.isFixedAcrossZones,
          }))
        )
      } else {
        throw new Error("Unsupported file type. Use .xlsx or .pdf")
      }
    } catch (err) {
      setImportError(err instanceof Error ? err.message : String(err))
    } finally {
      setImportParsing(false)
    }
  }

  // Confirm import
  const handleConfirmImport = async () => {
    if (importPreview.length === 0) return
    setItemSaving(true); setImportError("")
    try {
      const result = await bundleAdminApi.bulkImport(bundleId, importPreview)
      setImportResult(t("importSuccess", { imported: result.imported }))
      if (result.skipped.length > 0) {
        setImportResult(prev => prev + ` — ${t("importSkipped", { count: result.skipped.length })}`)
      }
      setImportPreview([]); setImportFile(null)
      await loadItems()
    } catch (err) {
      setImportError(err instanceof Error ? err.message : String(err))
    } finally { setItemSaving(false) }
  }

  if (loading) return <div className="p-8 text-center text-muted-foreground">{t("loading")}</div>
  if (!bundle) return <div className="p-8 text-center text-destructive">{t("notFound")}</div>

  const selectedZoneObj = zones.find(z => z.id === selectedZone)

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push(`/${locale}/dashboard/admin/service-bundles/${bundleId}`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-xl font-bold">{t("editTitle", { name: bundle.nameEs })}</h1>
          <p className="text-sm text-muted-foreground">{bundle.bundleCode}</p>
        </div>
      </div>

      {/* Metadata Form */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm">{t("bundleData")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 px-4 pb-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">{t("code")}</Label>
              <Input value={form.bundleCode} onChange={(e) => setForm(f => ({ ...f, bundleCode: e.target.value }))} className="h-8 text-sm font-mono" />
            </div>
            <div>
              <Label className="text-xs">{t("commerceType")}</Label>
              <Input value={form.commerceType} onChange={(e) => setForm(f => ({ ...f, commerceType: e.target.value }))} className="h-8 text-sm" />
            </div>
          </div>
          <div>
            <Label className="text-xs">{t("nameEs")}</Label>
            <Input value={form.nameEs} onChange={(e) => setForm(f => ({ ...f, nameEs: e.target.value }))} className="h-8 text-sm" />
          </div>
          <div>
            <Label className="text-xs">{t("description")}</Label>
            <Textarea value={form.descriptionEs} onChange={(e) => setForm(f => ({ ...f, descriptionEs: e.target.value }))} className="text-sm min-h-[60px]" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">{t("legalReference")}</Label>
              <Input value={form.legalReference} onChange={(e) => setForm(f => ({ ...f, legalReference: e.target.value }))} className="h-8 text-sm" placeholder={t("legalReferencePlaceholder")} />
            </div>
            <div className="flex items-center gap-2 pt-5">
              <Switch checked={form.isActive} onCheckedChange={(v) => setForm(f => ({ ...f, isActive: v }))} />
              <Label className="text-xs">{t("isActive")}</Label>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 items-end">
            <div className="flex items-center gap-2">
              <Switch checked={form.installmentEligible} onCheckedChange={(v) => setForm(f => ({ ...f, installmentEligible: v, ...(v ? {} : { maxInstallments: 1, installmentFrequency: "monthly" }) }))} />
              <Label className="text-xs">{t("allowInstallments")}</Label>
            </div>
            {form.installmentEligible && (
              <>
                <div>
                  <Label className="text-xs">{t("maxInstallments")}</Label>
                  <Input type="number" min={1} max={12} value={form.maxInstallments}
                    onChange={(e) => setForm(f => ({ ...f, maxInstallments: parseInt(e.target.value) || 1 }))}
                    className="h-8 text-sm" />
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
              </>
            )}
          </div>
          <div className="flex justify-end">
            <Button size="sm" onClick={handleSaveMetadata} disabled={saving}>
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
              {t("saveData")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tabs: Items | Import | Preview Fiche */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="items"><GripVertical className="h-3.5 w-3.5 mr-1" /> {t("servicesByZone")}</TabsTrigger>
          <TabsTrigger value="import"><Upload className="h-3.5 w-3.5 mr-1" /> {t("importTitle")}</TabsTrigger>
          <TabsTrigger value="preview"><Eye className="h-3.5 w-3.5 mr-1" /> {t("previewFiche")}</TabsTrigger>
        </TabsList>

        {/* ===== ITEMS TAB (with drag-drop) ===== */}
        <TabsContent value="items">
          <Card>
            <CardHeader className="py-3 px-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">
                  {selectedZoneObj?.zoneCode || "—"} ({selectedZoneObj?.nameEs || ""})
                </CardTitle>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setShowCopyZone(true)}>
                    <Copy className="h-3 w-3 mr-1" /> {t("copyZone")}
                  </Button>
                  <Button size="sm" className="h-7 text-xs" onClick={() => setShowAddItem(true)}>
                    <Plus className="h-3 w-3 mr-1" /> {t("add")}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-3 space-y-3">
              {/* Zone Selector */}
              <div className="flex gap-1 flex-wrap">
                {zones.map((zone) => (
                  <Button key={zone.id} variant={selectedZone === zone.id ? "default" : "outline"}
                    size="sm" className="h-7 text-xs" onClick={() => setSelectedZone(zone.id)}>
                    {zone.zoneCode}
                  </Button>
                ))}
              </div>

              {/* Items Table with DnD */}
              <div className="text-[10px] text-muted-foreground mb-1">{t("dragToReorder")}</div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[30px]" />
                    <TableHead className="w-[80px]">{t("serviceCode")}</TableHead>
                    <TableHead>{t("serviceName")}</TableHead>
                    <TableHead>{t("ministry")}</TableHead>
                    <TableHead className="w-[120px] text-right">{t("amount")}</TableHead>
                    <TableHead className="w-[60px] text-center">{t("fixed")}</TableHead>
                    <TableHead className="w-[50px]" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-6 text-muted-foreground">
                        {t("noServicesInZone")}
                      </TableCell>
                    </TableRow>
                  ) : (
                    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                      <SortableContext items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
                        {items.map((item) => (
                          <SortableRow key={item.id} item={item} onDelete={handleDeleteItem} />
                        ))}
                      </SortableContext>
                    </DndContext>
                  )}
                  {items.length > 0 && (
                    <TableRow className="bg-muted/50 font-bold">
                      <TableCell />
                      <TableCell colSpan={3} className="text-right">{t("totalTreasury")}</TableCell>
                      <TableCell className="text-right font-mono">{formatXAF(totalAmount)}</TableCell>
                      <TableCell colSpan={2} />
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== IMPORT TAB ===== */}
        <TabsContent value="import">
          <Card>
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-sm">{t("importTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="border rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <FileSpreadsheet className="h-4 w-4 text-green-600" /> {t("importExcel")}
                  </div>
                  <p className="text-xs text-muted-foreground">{t("importExcelHint")}</p>
                </div>
                <div className="border rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <FileText className="h-4 w-4 text-red-600" /> {t("importPdf")}
                  </div>
                  <p className="text-xs text-muted-foreground">{t("importPdfHint")}</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Input
                  type="file"
                  accept=".xlsx,.xls,.pdf"
                  onChange={(e) => { setImportFile(e.target.files?.[0] || null); setImportPreview([]); setImportError(""); setImportResult("") }}
                  className="text-sm flex-1"
                />
                <Button size="sm" onClick={handleParseFile} disabled={!importFile || importParsing}>
                  {importParsing ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Search className="h-3.5 w-3.5 mr-1" />}
                  {importParsing ? t("parsing") : t("import")}
                </Button>
              </div>

              {importError && (
                <div className="text-sm text-destructive bg-destructive/10 rounded p-2">{importError}</div>
              )}
              {importResult && (
                <div className="text-sm text-green-700 bg-green-50 rounded p-2">{importResult}</div>
              )}

              {importPreview.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium">{t("previewImport")} ({importPreview.length} items)</h4>
                    <Button size="sm" onClick={handleConfirmImport} disabled={itemSaving}>
                      {itemSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Upload className="h-3.5 w-3.5 mr-1" />}
                      {t("confirmImport")}
                    </Button>
                  </div>
                  <div className="max-h-[300px] overflow-y-auto border rounded">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[100px]">{t("serviceCode")}</TableHead>
                          <TableHead className="w-[60px]">{t("zones")}</TableHead>
                          <TableHead className="text-right w-[100px]">{t("amount")}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {importPreview.slice(0, 100).map((item, i) => (
                          <TableRow key={i}>
                            <TableCell className="font-mono text-xs">{item.serviceCode}</TableCell>
                            <TableCell className="text-xs">{item.zoneCode}</TableCell>
                            <TableCell className="text-right font-mono text-xs">{formatXAF(item.amount)}</TableCell>
                          </TableRow>
                        ))}
                        {importPreview.length > 100 && (
                          <TableRow>
                            <TableCell colSpan={3} className="text-center text-xs text-muted-foreground">
                              +{importPreview.length - 100} more items...
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== PREVIEW FICHE TAB ===== */}
        <TabsContent value="preview">
          <FichePreview bundle={bundle} zone={selectedZoneObj} items={items} totalAmount={totalAmount} t={t} />
        </TabsContent>
      </Tabs>

      {/* Add Item Dialog */}
      <Dialog open={showAddItem} onOpenChange={(open) => {
        setShowAddItem(open)
        if (!open) { setSelectedService(null); setServiceSearch(""); setNewItemAmount(""); setNewItemFixed(false) }
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">{t("addService")} — {selectedZoneObj?.zoneCode}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">{t("selectService")}</Label>
              <Popover open={servicePickerOpen} onOpenChange={setServicePickerOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start h-9 text-sm font-normal">
                    {selectedService ? (
                      <span className="truncate"><span className="font-mono mr-1">{selectedService.serviceCode}</span>{selectedService.nameEs}</span>
                    ) : (<span className="text-muted-foreground">{t("searchService")}</span>)}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[400px] p-2" align="start">
                  <div className="relative mb-2">
                    <Search className="absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
                    <Input value={serviceSearch} onChange={(e) => setServiceSearch(e.target.value)}
                      placeholder={t("searchService")} className="pl-8 h-8 text-sm" autoFocus />
                  </div>
                  <div className="max-h-[250px] overflow-y-auto">
                    {serviceSearching ? (
                      <div className="text-center py-3 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin mx-auto" /></div>
                    ) : serviceResults.length === 0 ? (
                      <div className="text-center py-3 text-xs text-muted-foreground">
                        {serviceSearch.length >= 2 ? t("noServiceFound") : t("searchService")}
                      </div>
                    ) : serviceResults.map((svc) => (
                      <button key={svc.id} className="w-full text-left px-2 py-1.5 hover:bg-muted rounded text-sm flex items-center gap-2"
                        onClick={() => { setSelectedService(svc); setServicePickerOpen(false) }}>
                        <span className="font-mono text-xs text-muted-foreground w-14 shrink-0">{svc.serviceCode}</span>
                        <span className="truncate flex-1">{svc.nameEs}</span>
                        {svc.ministryName && <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">{svc.ministryName}</span>}
                      </button>
                    ))}
                  </div>
                </PopoverContent>
              </Popover>
            </div>
            {selectedService?.ministryName && (
              <div>
                <Label className="text-xs">{t("ministry")}</Label>
                <Input value={selectedService.ministryName} disabled className="h-8 text-sm bg-muted" />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">{t("amount")}</Label>
                <Input type="number" step="1" min="0" value={newItemAmount}
                  onChange={(e) => setNewItemAmount(e.target.value)} className="h-8 text-sm" placeholder="50000" />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <Switch checked={newItemFixed} onCheckedChange={setNewItemFixed} />
                <Label className="text-xs">{t("fixedAllZones")}</Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setShowAddItem(false)}>{t("cancel")}</Button>
            <Button size="sm" onClick={handleAddItem} disabled={itemSaving || !selectedService || !newItemAmount}>
              {itemSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Plus className="h-3.5 w-3.5 mr-1" />}
              {t("add")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Copy Zone Dialog */}
      <Dialog open={showCopyZone} onOpenChange={setShowCopyZone}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-sm">{t("copyPricesBetweenZones")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">{t("sourceZone")}</Label>
              <Select value={copySource} onValueChange={setCopySource}>
                <SelectTrigger className="h-8 text-sm"><SelectValue placeholder={t("select")} /></SelectTrigger>
                <SelectContent>{zones.map(z => <SelectItem key={z.id} value={z.id}>{z.zoneCode} — {z.nameEs}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">{t("targetZone")}</Label>
              <Select value={copyTarget} onValueChange={setCopyTarget}>
                <SelectTrigger className="h-8 text-sm"><SelectValue placeholder={t("select")} /></SelectTrigger>
                <SelectContent>{zones.map(z => <SelectItem key={z.id} value={z.id}>{z.zoneCode} — {z.nameEs}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">{t("multiplier")}</Label>
              <Input type="number" step="0.01" value={copyMultiplier}
                onChange={(e) => setCopyMultiplier(e.target.value)} className="h-8 text-sm" />
              <p className="text-xs text-muted-foreground mt-1">{t("multiplierHint")}</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setShowCopyZone(false)}>{t("cancel")}</Button>
            <Button size="sm" onClick={handleCopyZone} disabled={itemSaving || !copySource || !copyTarget}>
              {itemSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Copy className="h-3.5 w-3.5 mr-1" />}
              {t("copy")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
