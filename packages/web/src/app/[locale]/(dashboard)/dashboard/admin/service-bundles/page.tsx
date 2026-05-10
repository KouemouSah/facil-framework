"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card, CardContent } from "@/components/ui/card"
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
  Package, MapPin, Layers, Search, Eye, Download, ChevronLeft, ChevronRight,
  Plus, Trash2, Pencil,
} from "lucide-react"
import FiscalServicesTabNav from "@/modules/fiscal-services/components/FiscalServicesTabNav"
import { SortableHeader } from "@/components/ui/sortable-header"
import { useSortState } from "@/hooks/use-sort-state"
import { bundleApi, bundleAdminApi } from "@/modules/fiscal-services/services/bundle-api"
import type { BundleListResponse, BundleStats } from "@/types/service-bundle"

export default function ServiceBundlesPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.serviceBundles")
  const [sort, handleSort, sortData] = useSortState()
  const [data, setData] = useState<BundleListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isActive, setIsActive] = useState<string>("all")
  const [stats, setStats] = useState<BundleStats>({ bundles: 0, zones: 0, items: 0 })
  const fetchSeq = useRef(0)
  const PAGE_SIZE = 20

  const fetchBundles = useCallback(async () => {
    const seq = ++fetchSeq.current
    setLoading(true)
    try {
      const result = await bundleApi.listBundles({
        page, pageSize: PAGE_SIZE,
        search: search || undefined,
        isActive: isActive === "all" ? undefined : isActive === "true",
      })
      if (seq === fetchSeq.current) setData(result)
    } catch (err) {
      console.error("Failed to fetch bundles:", err)
    } finally {
      if (seq === fetchSeq.current) setLoading(false)
    }
  }, [page, search, isActive])

  useEffect(() => { fetchBundles() }, [fetchBundles])
  useEffect(() => { bundleAdminApi.getStats().then(setStats).catch(() => {}) }, [])

  const [searchInput, setSearchInput] = useState("")
  useEffect(() => {
    const timer = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  const handleExport = async (e: React.MouseEvent, bundleId: string, bundleCode: string) => {
    e.stopPropagation()
    try {
      const blob = await bundleAdminApi.exportCsv(bundleId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url; a.download = `bundle_${bundleCode}_matrix.csv`; a.click()
      URL.revokeObjectURL(url)
    } catch (err) { console.error("Export failed:", err) }
  }

  const handleDelete = async (e: React.MouseEvent, bundleId: string, bundleName: string) => {
    e.stopPropagation()
    if (!window.confirm(`${t("deleteConfirm")} "${bundleName}"?`)) return
    try {
      await bundleAdminApi.deleteBundle(bundleId)
      fetchBundles()
      bundleAdminApi.getStats().then(setStats).catch(() => {})
    } catch (err) { console.error("Delete failed:", err) }
  }

  const basePath = `/${locale}/dashboard/admin/service-bundles`

  return (
    <div className="space-y-4 p-4">
      <FiscalServicesTabNav activeTab="bundles" />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button size="sm" onClick={() => router.push(`${basePath}/new`)}>
          <Plus className="h-4 w-4 mr-1" /> {t("newBundle")}
        </Button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-blue-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t("bundles")}</p>
              <p className="text-lg font-bold">{stats.bundles}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-green-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t("zones")}</p>
              <p className="text-lg font-bold">{stats.zones}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-orange-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t("totalItems")}</p>
              <p className="text-lg font-bold">{stats.items}</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder={t("search")} value={searchInput} onChange={(e) => setSearchInput(e.target.value)} className="pl-8 h-9" />
        </div>
        <Select value={isActive} onValueChange={(v) => { setIsActive(v); setPage(1) }}>
          <SelectTrigger className="w-[140px] h-9"><SelectValue placeholder={t("status")} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allStatuses")}</SelectItem>
            <SelectItem value="true">{t("active")}</SelectItem>
            <SelectItem value="false">{t("inactive")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableHeader column="bundleCode" label={t("code")} sort={sort} onSort={handleSort} className="w-[120px]" />
                <SortableHeader column="nameEs" label={t("name")} sort={sort} onSort={handleSort} />
                <SortableHeader column="commerceType" label={t("type")} sort={sort} onSort={handleSort} className="w-[120px]" />
                <SortableHeader column="itemCount" label={t("items")} sort={sort} onSort={handleSort} className="w-[70px] text-center" />
                <TableHead className="w-[70px] text-center">{t("zones")}</TableHead>
                <TableHead className="w-[90px] text-center">{t("payment")}</TableHead>
                <SortableHeader column="isActive" label={t("status")} sort={sort} onSort={handleSort} className="w-[80px] text-center" />
                <TableHead className="w-[110px]">{t("actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={8} className="text-center py-8 text-muted-foreground">{t("loading")}</TableCell></TableRow>
              ) : !data?.items?.length ? (
                <TableRow><TableCell colSpan={8} className="text-center py-8 text-muted-foreground">{t("noResults")}</TableCell></TableRow>
              ) : (sortData(data.items as unknown as Record<string, unknown>[], { bundleCode: 'string', nameEs: 'string', commerceType: 'string', itemCount: 'number', isActive: 'boolean' }) as unknown as typeof data.items).map((bundle) => (
                <TableRow key={bundle.id} className="cursor-pointer hover:bg-muted/50" onClick={() => router.push(`${basePath}/${bundle.id}`)}>
                  <TableCell className="font-mono text-xs">{bundle.bundleCode}</TableCell>
                  <TableCell className="font-medium text-sm">{bundle.nameEs}</TableCell>
                  <TableCell className="text-xs">{bundle.commerceType}</TableCell>
                  <TableCell className="text-center">{bundle.itemCount}</TableCell>
                  <TableCell className="text-center">{bundle.zoneCount}</TableCell>
                  <TableCell className="text-center">
                    {bundle.installmentEligible
                      ? <Badge variant="outline" className="text-xs">{bundle.maxInstallments}x</Badge>
                      : <span className="text-xs text-muted-foreground">{t("single")}</span>}
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant={bundle.isActive ? "default" : "secondary"} className="text-xs">
                      {bundle.isActive ? t("active") : t("inactive")}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-0.5" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => router.push(`${basePath}/${bundle.id}`)} title={t("edit")}>
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => router.push(`${basePath}/${bundle.id}/edit`)} title={t("edit")}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => handleExport(e, bundle.id, bundle.bundleCode)} title={t("exportCsv")}>
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={(e) => handleDelete(e, bundle.id, bundle.nameEs)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">{t("pageInfo", { total: data?.total ?? 0, page, totalPages })}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}
    </div>
  )
}
