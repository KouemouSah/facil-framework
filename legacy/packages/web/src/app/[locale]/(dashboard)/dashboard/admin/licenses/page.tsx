"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  FolderOpen, Search, Eye, ChevronLeft, ChevronRight,
  Plus, AlertTriangle, CheckCircle2,
} from "lucide-react"
import FiscalServicesTabNav from "@/modules/fiscal-services/components/FiscalServicesTabNav"
import { SortableHeader } from "@/components/ui/sortable-header"
import { useSortState } from "@/hooks/use-sort-state"
import { useToast } from "@/hooks/use-toast"
import { formatXAF } from "@/core/utils/format"
import { licenseApi, licenseAdminApi } from "@/modules/fiscal-services/services/license-api"
import CompanySearchSelect from "@/modules/companies/components/CompanySearchSelect"
import { bundleApi } from "@/modules/fiscal-services/services/bundle-api"
import type { LicenseListResponse, LicenseStats, LicenseStatus } from "@/types/commercial-license"
import type { ServiceBundle, CommerceZone } from "@/types/service-bundle"

const STATUS_COLORS: Record<LicenseStatus, string> = {
  open: "bg-blue-100 text-blue-800",
  partial: "bg-yellow-100 text-yellow-800",
  complete: "bg-green-100 text-green-800",
  overdue: "bg-red-100 text-red-800",
  suspended: "bg-gray-100 text-gray-800",
  closed: "bg-gray-200 text-gray-600",
}

const CURRENT_YEAR = new Date().getFullYear()
const PAGE_SIZE = 20

export default function LicensesPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.licenses")
  const { toast } = useToast()

  const [data, setData] = useState<LicenseListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<LicenseStats | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [searchInput, setSearchInput] = useState("")
  const [fiscalYear, setFiscalYear] = useState<string>(String(CURRENT_YEAR))
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [bundleFilter, setBundleFilter] = useState<string>("all")
  const [bundles, setBundles] = useState<ServiceBundle[]>([])
  const [sort, handleSort] = useSortState('fiscal_year', 'desc')
  const fetchSeq = useRef(0)

  // Create dialog state
  const [createOpen, setCreateOpen] = useState(false)
  const [createBundleId, setCreateBundleId] = useState("")
  const [createZoneId, setCreateZoneId] = useState("")
  const [createCompanyId, setCreateCompanyId] = useState("")
  const [createYear, setCreateYear] = useState(String(CURRENT_YEAR))
  const [zones, setZones] = useState<CommerceZone[]>([])
  const [creating, setCreating] = useState(false)

  // Load bundles list for filter + create dialog
  useEffect(() => {
    bundleApi.listBundles({ pageSize: 100, isActive: true })
      .then(res => setBundles(res.items))
      .catch(() => {})
    bundleApi.listZones()
      .then(setZones)
      .catch(() => {})
  }, [])

  // Load stats
  useEffect(() => {
    const fy = fiscalYear === "all" ? undefined : Number(fiscalYear)
    licenseApi.getStats(fy)
      .then(setStats)
      .catch(() => {})
  }, [fiscalYear])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  // Fetch licenses
  const fetchLicenses = useCallback(async () => {
    const seq = ++fetchSeq.current
    setLoading(true)
    try {
      const result = await licenseApi.listLicenses({
        page,
        pageSize: PAGE_SIZE,
        fiscalYear: fiscalYear === "all" ? undefined : Number(fiscalYear),
        status: statusFilter === "all" ? undefined : statusFilter,
        bundleId: bundleFilter === "all" ? undefined : bundleFilter,
        search: search || undefined,
        sortBy: sort.column || undefined,
        sortOrder: sort.direction,
      })
      if (seq === fetchSeq.current) setData(result)
    } catch {
      if (seq === fetchSeq.current) {
        toast({ variant: "destructive", title: t("loadError") })
      }
    } finally {
      if (seq === fetchSeq.current) setLoading(false)
    }
  }, [page, fiscalYear, statusFilter, bundleFilter, search, sort, t, toast])

  useEffect(() => { fetchLicenses() }, [fetchLicenses])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const basePath = `/${locale}/dashboard/admin/licenses`

  const statusLabel = (status: LicenseStatus) => {
    const key = `status${status.charAt(0).toUpperCase() + status.slice(1)}` as
      "statusOpen" | "statusPartial" | "statusComplete" | "statusOverdue" | "statusSuspended" | "statusClosed"
    return t(key)
  }

  // Create license handler
  const handleCreate = async () => {
    if (!createBundleId || !createZoneId || !createCompanyId || !createYear) return
    setCreating(true)
    try {
      const license = await licenseAdminApi.openLicense({
        companyId: createCompanyId.trim(),
        bundleId: createBundleId,
        zoneId: createZoneId,
        fiscalYear: Number(createYear),
      })
      toast({ title: t("createSuccess") })
      setCreateOpen(false)
      router.push(`${basePath}/${license.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("createError")
      toast({ variant: "destructive", title: t("createError"), description: msg })
    } finally {
      setCreating(false)
    }
  }

  const yearOptions = Array.from({ length: 7 }, (_, i) => CURRENT_YEAR - 3 + i)

  return (
    <div className="space-y-4 p-4">
      <FiscalServicesTabNav activeTab="licenses" />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><Plus className="h-4 w-4 mr-1" /> {t("newLicense")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("createTitle")}</DialogTitle>
              <DialogDescription>{t("createDesc")}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>{t("bundle")}</Label>
                <Select value={createBundleId} onValueChange={setCreateBundleId}>
                  <SelectTrigger><SelectValue placeholder={t("selectBundle")} /></SelectTrigger>
                  <SelectContent>
                    {bundles.map(b => (
                      <SelectItem key={b.id} value={b.id}>{b.bundleCode} — {b.nameEs}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{t("zone")}</Label>
                <Select value={createZoneId} onValueChange={setCreateZoneId}>
                  <SelectTrigger><SelectValue placeholder={t("selectZone")} /></SelectTrigger>
                  <SelectContent>
                    {zones.map(z => (
                      <SelectItem key={z.id} value={z.id}>{z.zoneCode} — {z.nameEs}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{t("companyId")}</Label>
                <CompanySearchSelect
                  value={createCompanyId || null}
                  onValueChange={setCreateCompanyId}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("fiscalYear")}</Label>
                <Select value={createYear} onValueChange={setCreateYear}>
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
              <Button onClick={handleCreate} disabled={creating || !createBundleId || !createZoneId || !createCompanyId}>
                {creating ? t("creating") : t("create")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-blue-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t("statTotal")}</p>
                <p className="text-lg font-bold">{stats.totalLicenses}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t("statOpen")}</p>
                <p className="text-lg font-bold">{stats.openLicenses}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t("statOverdue")}</p>
                <p className="text-lg font-bold">{stats.overdueLicenses}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <div>
                <p className="text-xs text-muted-foreground">{t("statCollected")}</p>
                <p className="text-lg font-bold">{formatXAF(stats.amountPaid, locale)}</p>
                <p className="text-xs text-muted-foreground">/ {formatXAF(stats.totalAmount, locale)}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("search")}
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            className="pl-8 h-9"
          />
        </div>
        <Select value={fiscalYear} onValueChange={v => { setFiscalYear(v); setPage(1) }}>
          <SelectTrigger className="w-[130px] h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allYears")}</SelectItem>
            {yearOptions.map(y => (
              <SelectItem key={y} value={String(y)}>{y}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={bundleFilter} onValueChange={v => { setBundleFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[180px] h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allBundles")}</SelectItem>
            {bundles.map(b => (
              <SelectItem key={b.id} value={b.id}>{b.bundleCode}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[140px] h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allStatuses")}</SelectItem>
            {(["open", "partial", "complete", "overdue", "suspended", "closed"] as LicenseStatus[]).map(s => (
              <SelectItem key={s} value={s}>{statusLabel(s)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <SortableHeader column="company_name" label={t("company")} sort={sort} onSort={handleSort} />
              <TableHead>{t("bundle")}</TableHead>
              <SortableHeader column="zone_code" label={t("zone")} sort={sort} onSort={handleSort} className="w-[60px]" />
              <SortableHeader column="fiscal_year" label={t("year")} sort={sort} onSort={handleSort} className="w-[60px] text-center" />
              <SortableHeader column="status" label={t("status")} sort={sort} onSort={handleSort} className="w-[90px] text-center" />
              <SortableHeader column="total_amount" label={t("totalAmount")} sort={sort} onSort={handleSort} className="text-right" />
              <SortableHeader column="amount_paid" label={t("amountPaid")} sort={sort} onSort={handleSort} className="text-right" />
              <SortableHeader column="compliance_score" label={t("compliance")} sort={sort} onSort={handleSort} className="w-[80px] text-center" />
              <SortableHeader column="deadline" label={t("deadline")} sort={sort} onSort={handleSort} className="w-[100px]" />
              <TableHead className="w-[60px]">{t("actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center py-8 text-muted-foreground">
                  {t("loading")}
                </TableCell>
              </TableRow>
            ) : !data?.items?.length ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center py-8 text-muted-foreground">
                  {t("noResults")}
                </TableCell>
              </TableRow>
            ) : data.items.map(lic => (
              <TableRow
                key={lic.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => router.push(`${basePath}/${lic.id}`)}
              >
                <TableCell className="font-medium text-sm max-w-[180px] truncate">
                  {lic.companyName || lic.companyId.slice(0, 8)}
                </TableCell>
                <TableCell className="text-xs">{lic.bundleName || "—"}</TableCell>
                <TableCell className="text-xs font-mono text-center">{lic.zoneCode || "—"}</TableCell>
                <TableCell className="text-center">{lic.fiscalYear}</TableCell>
                <TableCell className="text-center">
                  <Badge className={`text-xs ${STATUS_COLORS[lic.status] || ""}`} variant="secondary">
                    {statusLabel(lic.status)}
                  </Badge>
                </TableCell>
                <TableCell className="text-right text-xs font-mono">
                  {formatXAF(lic.totalAmount, locale)}
                </TableCell>
                <TableCell className="text-right text-xs font-mono">
                  {formatXAF(lic.amountPaid, locale)}
                </TableCell>
                <TableCell className="text-center">
                  <span className={`text-xs font-bold ${
                    Number(lic.complianceScore || 0) >= 80 ? "text-green-600" :
                    Number(lic.complianceScore || 0) >= 50 ? "text-yellow-600" : "text-red-600"
                  }`}>
                    {lic.complianceScore != null ? `${Number(lic.complianceScore).toFixed(0)}%` : "—"}
                  </span>
                </TableCell>
                <TableCell className="text-xs">{lic.deadline || "—"}</TableCell>
                <TableCell onClick={e => e.stopPropagation()}>
                  <Button
                    variant="ghost" size="icon" className="h-7 w-7"
                    onClick={() => router.push(`${basePath}/${lic.id}`)}
                  >
                    <Eye className="h-3.5 w-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {t("pageInfo", { total: data?.total ?? 0, page, totalPages })}
          </span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
