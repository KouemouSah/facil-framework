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
  Building2, Users, ShieldCheck, FolderOpen, Search, Eye,
  ChevronLeft, ChevronRight, CheckCircle, XCircle,
} from "lucide-react"
import { companiesSupervisorApi } from "@/modules/companies/services/api"
import type { CompanyAdminListResponse, CompanyStats } from "@/modules/companies/types"

const REGIMEN_OPTIONS = ["bundle", "declarativo", "exento", "pendiente"] as const

export default function SupervisorCompaniesPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("supervisor.companies")

  const [data, setData] = useState<CompanyAdminListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isActive, setIsActive] = useState<string>("all")
  const [isVerified, setIsVerified] = useState<string>("all")
  const [regimenFiscal, setRegimenFiscal] = useState<string>("all")
  const [stats, setStats] = useState<CompanyStats>({
    total: 0, active: 0, verified: 0, inactive: 0, with_licenses: 0, by_regimen: {},
  })
  const fetchSeq = useRef(0)
  const PAGE_SIZE = 20

  const fetchCompanies = useCallback(async () => {
    const seq = ++fetchSeq.current
    setLoading(true)
    try {
      const result = await companiesSupervisorApi.listMyCompanies({
        page,
        pageSize: PAGE_SIZE,
        search: search || undefined,
        isActive: isActive === "all" ? undefined : isActive === "true",
        isVerified: isVerified === "all" ? undefined : isVerified === "true",
        regimenFiscal: regimenFiscal === "all" ? undefined : regimenFiscal,
      })
      if (seq === fetchSeq.current) setData(result)
    } catch (err) {
      console.error("Failed to fetch companies:", err)
    } finally {
      if (seq === fetchSeq.current) setLoading(false)
    }
  }, [page, search, isActive, isVerified, regimenFiscal])

  useEffect(() => { fetchCompanies() }, [fetchCompanies])
  useEffect(() => { companiesSupervisorApi.getStats().then(setStats).catch(() => {}) }, [])

  const [searchInput, setSearchInput] = useState("")
  useEffect(() => {
    const timer = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  // Supervisor views company detail (dedicated supervisor route)
  const basePath = `/${locale}/dashboard/supervisor/companies`

  return (
    <div className="space-y-4 p-4">
      <div>
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-blue-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t("statsTotal")}</p>
              <p className="text-lg font-bold">{stats.total}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t("statsActive")}</p>
              <p className="text-lg font-bold">{stats.active}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-purple-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t("statsVerified")}</p>
              <p className="text-lg font-bold">{stats.verified}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4 text-orange-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t("statsWithLicenses")}</p>
              <p className="text-lg font-bold">{stats.with_licenses}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("search")}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-8 h-9"
          />
        </div>
        <Select value={isActive} onValueChange={(v) => { setIsActive(v); setPage(1) }}>
          <SelectTrigger className="w-[130px] h-9"><SelectValue placeholder={t("status")} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allStatuses")}</SelectItem>
            <SelectItem value="true">{t("active")}</SelectItem>
            <SelectItem value="false">{t("inactive")}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={isVerified} onValueChange={(v) => { setIsVerified(v); setPage(1) }}>
          <SelectTrigger className="w-[140px] h-9"><SelectValue placeholder={t("allVerification")} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allVerification")}</SelectItem>
            <SelectItem value="true">{t("verified")}</SelectItem>
            <SelectItem value="false">{t("unverified")}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={regimenFiscal} onValueChange={(v) => { setRegimenFiscal(v); setPage(1) }}>
          <SelectTrigger className="w-[150px] h-9"><SelectValue placeholder={t("allRegimen")} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allRegimen")}</SelectItem>
            {REGIMEN_OPTIONS.map((r) => (
              <SelectItem key={r} value={r}>{t(r)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("legalName")}</TableHead>
                <TableHead className="w-[100px]">Identificador</TableHead>
                <TableHead className="w-[100px]">{t("city")}</TableHead>
                <TableHead className="w-[70px]">{t("zone")}</TableHead>
                <TableHead className="w-[100px]">{t("regimen")}</TableHead>
                <TableHead className="w-[70px] text-center">{t("members")}</TableHead>
                <TableHead className="w-[80px] text-center">{t("status")}</TableHead>
                <TableHead className="w-[80px] text-center">{t("isVerified")}</TableHead>
                <TableHead className="w-[60px]">{t("actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">
                    {t("loading")}
                  </TableCell>
                </TableRow>
              ) : !data?.items?.length ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">
                    {t("noResults")}
                  </TableCell>
                </TableRow>
              ) : data.items.map((company) => (
                <TableRow
                  key={company.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => router.push(`${basePath}/${company.id}`)}
                >
                  <TableCell className="font-medium text-sm">
                    <div>
                      <span>{company.legal_name}</span>
                      {company.trade_name && (
                        <span className="block text-xs text-muted-foreground">{company.trade_name}</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{company.registration_number || company.nif || "-"}</TableCell>
                  <TableCell className="text-xs">{company.city_name || "-"}</TableCell>
                  <TableCell className="text-xs">{company.zone_code || "-"}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {company.regimen_fiscal ? t(company.regimen_fiscal) : t("pendiente")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Users className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs">{company.member_count || 0}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant={company.is_active ? "default" : "secondary"} className="text-xs">
                      {company.is_active ? t("active") : t("inactive")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    {company.is_verified ? (
                      <CheckCircle className="h-4 w-4 text-green-500 mx-auto" />
                    ) : (
                      <XCircle className="h-4 w-4 text-gray-300 mx-auto" />
                    )}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={(e) => { e.stopPropagation(); router.push(`${basePath}/${company.id}`) }}
                      title={t("view")}
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
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
