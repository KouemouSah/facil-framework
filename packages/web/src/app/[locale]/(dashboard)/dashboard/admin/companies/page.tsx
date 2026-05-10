"use client"

import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Building2, Users, ShieldCheck, FolderOpen, Search, Eye,
  ChevronLeft, ChevronRight, CheckCircle, XCircle, AlertTriangle, TrendingUp,
  ArrowUpDown, ArrowUp, ArrowDown, ChevronDown, Download, Brain,
  Briefcase, MapPin, FileText, List, Columns3, X, SlidersHorizontal, Star, Save,
  MoreHorizontal, ExternalLink, FolderSearch, Plus, Archive,
} from "lucide-react"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  DndContext, closestCenter, DragEndEvent, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import { useDraggable, useDroppable } from '@dnd-kit/core'
import {
  Chart as ChartJS, ArcElement, Tooltip, CategoryScale, LinearScale,
  PointElement, LineElement, Filler,
} from 'chart.js'
import { Doughnut, Line } from 'react-chartjs-2'
import { companiesAdminApi, companyDashboardApi } from "@/modules/companies/services/api"
import { companyPublicApi } from "@/modules/companies/services/api"
import apiClient from '@/core/api/client'
import type {
  Company, CompanyAdminListResponse, GlobalStats, CompanyAnalytics, PublicZone,
} from "@/modules/companies/types"

ChartJS.register(ArcElement, Tooltip, CategoryScale, LinearScale, PointElement, LineElement, Filler)

const REGIMEN_OPTIONS = ["bundle", "declarativo", "exento", "pendiente"] as const

const REGIMEN_COLORS: Record<string, string> = {
  bundle: '#0ea5e9',
  declarativo: '#a855f7',
  exento: '#22c55e',
  pendiente: '#f59e0b',
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toLocaleString()
}

// =============================================================================
// SVG GAUGE COMPONENT
// =============================================================================

function GaugeRing({ value, max, color, size = 48 }: { value: number; max: number; color: string; size?: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  const r = (size - 6) / 2
  const circumference = 2 * Math.PI * r
  const offset = circumference * (1 - pct)

  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth={5} className="text-gray-100" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={color} strokeWidth={5} strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={offset}
        className="transition-all duration-700"
      />
      <text
        x={size / 2} y={size / 2}
        textAnchor="middle" dominantBaseline="central"
        className="rotate-90 origin-center fill-gray-700"
        fontSize={size < 48 ? 10 : 12} fontWeight="bold"
      >
        {Math.round(pct * 100)}%
      </text>
    </svg>
  )
}

// =============================================================================
// SPARKLINE COMPONENT (chart.js Line, minimal)
// =============================================================================

function Sparkline({ data, color = '#3b82f6' }: { data: number[]; color?: string }) {
  const chartData = useMemo(() => ({
    labels: data.map((_, i) => String(i)),
    datasets: [{
      data,
      borderColor: color,
      backgroundColor: `${color}15`,
      borderWidth: 1.5,
      pointRadius: 0,
      fill: true,
      tension: 0.4,
    }],
  }), [data, color])

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: { tooltip: { enabled: false }, legend: { display: false } },
    scales: {
      x: { display: false },
      y: { display: false, beginAtZero: true },
    },
    elements: { line: { borderCapStyle: 'round' as const } },
  }), [])

  return (
    <div className="h-8 w-20">
      <Line data={chartData} options={options} />
    </div>
  )
}

// =============================================================================
// SORTABLE COLUMN DEFINITION
// =============================================================================

type SortKey = 'legal_name' | 'is_active' | 'is_verified' | 'created_at'
type KanbanGroupBy = 'regimen' | 'zone'

const KANBAN_PER_COL = 12

const KANBAN_REGIMEN_COLS = [
  { key: 'bundle', label: 'Bundle', color: '#0ea5e9', bg: 'bg-sky-50 border-sky-200' },
  { key: 'declarativo', label: 'Declarativo', color: '#a855f7', bg: 'bg-violet-50 border-violet-200' },
  { key: 'exento', label: 'Exento', color: '#22c55e', bg: 'bg-emerald-50 border-emerald-200' },
  { key: 'pendiente', label: 'Pendiente', color: '#f59e0b', bg: 'bg-amber-50 border-amber-200' },
]

// =============================================================================
// DND COMPONENTS
// =============================================================================

function DraggableCard({ company }: { company: Company }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: company.id,
    data: { company },
  })
  const style = transform ? {
    transform: `translate(${transform.x}px, ${transform.y}px)`,
    zIndex: isDragging ? 50 : undefined,
    opacity: isDragging ? 0.7 : 1,
  } : undefined

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className="bg-white border border-gray-200 rounded-md p-2.5 hover:shadow-sm transition-shadow cursor-grab active:cursor-grabbing"
    >
      <div className="flex items-start justify-between gap-1 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <Building2 className="h-3.5 w-3.5 text-blue-500 shrink-0" />
          <span className="text-xs font-semibold text-gray-900 line-clamp-1">{company.legal_name}</span>
        </div>
        {company.is_verified && <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />}
      </div>
      {company.nif && (
        <p className="text-[10px] text-gray-400 font-mono ml-5 mb-0.5">{company.nif}</p>
      )}
      <div className="flex items-center gap-2 text-[10px] text-gray-400 ml-5">
        {company.zone_code && <span>{company.zone_code}</span>}
        {company.forma_juridica && (
          <Badge variant="outline" className="text-[8px] px-1 py-0 border-gray-200">
            {company.forma_juridica}
          </Badge>
        )}
      </div>
    </div>
  )
}

function DroppableColumn({ id, children }: { id: string; children: React.ReactNode }) {
  const { isOver, setNodeRef } = useDroppable({ id })
  return (
    <div
      ref={setNodeRef}
      className={`flex-1 min-h-[200px] p-2 space-y-2 transition-colors rounded-b-lg border border-t-0 border-gray-200 ${
        isOver ? 'bg-blue-50/50' : 'bg-gray-50/30'
      }`}
    >
      {children}
    </div>
  )
}

// =============================================================================
// PAGE COMPONENT
// =============================================================================

export default function AdminCompaniesPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.companies")

  // --- List state ---
  const [data, setData] = useState<CompanyAdminListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isActive, setIsActive] = useState<string>("all")
  const [isVerified, setIsVerified] = useState<string>("all")
  const [regimenFiscal, setRegimenFiscal] = useState<string>("all")
  const [zoneId, setZoneId] = useState<string>("all")
  const [cityId, setCityId] = useState<string>("all")
  const [sortBy, setSortBy] = useState<SortKey>('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const fetchSeq = useRef(0)
  const PAGE_SIZE = 20

  // --- Selection state ---
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [bulkLoading, setBulkLoading] = useState(false)

  // --- View mode ---
  const [viewMode, setViewMode] = useState<'list' | 'kanban'>('list')
  const [kanbanGroupBy, setKanbanGroupBy] = useState<KanbanGroupBy>('regimen')
  const [kanbanData, setKanbanData] = useState<Record<string, Company[]>>({})
  const [kanbanLoading, setKanbanLoading] = useState(false)
  const kanbanSeqRef = useRef(0)

  // --- Filter options ---
  const [zones, setZones] = useState<PublicZone[]>([])
  const [cities, setCities] = useState<{ id: string; name: string }[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)

  // --- Saved filter presets (localStorage) ---
  type FilterPreset = { name: string; isActive: string; isVerified: string; regimenFiscal: string; zoneId: string }
  const PRESETS_KEY = 'admin_companies_filter_presets'

  const [savedPresets, setSavedPresets] = useState<FilterPreset[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      return JSON.parse(localStorage.getItem(PRESETS_KEY) || '[]')
    } catch { return [] }
  })

  // --- KPI state ---
  const [globalStats, setGlobalStats] = useState<GlobalStats | null>(null)
  const [analytics, setAnalytics] = useState<CompanyAnalytics | null>(null)

  // --- Fetch list ---
  const fetchCompanies = useCallback(async () => {
    const seq = ++fetchSeq.current
    setLoading(true)
    try {
      const result = await companiesAdminApi.listAll({
        page,
        pageSize: PAGE_SIZE,
        search: search || undefined,
        isActive: isActive === "all" ? undefined : isActive === "true",
        isVerified: isVerified === "all" ? undefined : isVerified === "true",
        regimenFiscal: regimenFiscal === "all" ? undefined : regimenFiscal,
        zoneId: zoneId === "all" ? undefined : zoneId,
        cityId: cityId === "all" ? undefined : cityId,
        sortBy,
        sortOrder,
      })
      if (seq === fetchSeq.current) setData(result)
    } catch (err) {
      console.error("Failed to fetch companies:", err)
    } finally {
      if (seq === fetchSeq.current) setLoading(false)
    }
  }, [page, search, isActive, isVerified, regimenFiscal, zoneId, cityId, sortBy, sortOrder])

  useEffect(() => { fetchCompanies() }, [fetchCompanies])

  // Fetch KPI + filter options
  useEffect(() => {
    companyDashboardApi.getGlobalStats().then(setGlobalStats).catch(() => {})
    companyDashboardApi.getAnalytics().then(setAnalytics).catch(() => {})
    companyPublicApi.getZones().then(setZones).catch(() => {})
  }, [])

  // --- City cascade from zone ---
  useEffect(() => {
    if (zoneId === 'all') {
      setCities([])
      setCityId('all')
      return
    }
    // Fetch all cities from /cities/simple, then filter client-side by zone
    // Cities table has region (Insular/Continental), zones have zone_tier
    // We use companies data to find cities that have companies in this zone
    apiClient.get<{ id: string; name: string; region: string }[]>('/cities/simple')
      .then(res => {
        // Filter cities that belong to companies in this zone by cross-referencing
        // Since cities don't have zone_id directly, use analytics.by_city which has zone_code
        const zoneObj = zones.find(z => z.id === zoneId)
        if (zoneObj && analytics?.by_city?.length) {
          const cityNames = new Set(
            analytics.by_city.filter(c => c.zone_code === zoneObj.zone_code).map(c => c.city_name)
          )
          setCities(res.data.filter(c => cityNames.has(c.name)))
        } else {
          setCities(res.data)
        }
      })
      .catch(() => setCities([]))
  }, [zoneId, zones, analytics])

  // --- Search debounce ---
  const [searchInput, setSearchInput] = useState("")
  useEffect(() => {
    const timer = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  // --- Sort toggle ---
  const toggleSort = (col: SortKey) => {
    if (sortBy === col) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortOrder('asc')
    }
    setPage(1)
  }

  // --- Selection helpers ---
  const allOnPageSelected = data?.items?.length ? data.items.every(c => selected.has(c.id)) : false

  const toggleSelectAll = () => {
    if (!data?.items) return
    const next = new Set(selected)
    if (allOnPageSelected) {
      data.items.forEach(c => next.delete(c.id))
    } else {
      data.items.forEach(c => next.add(c.id))
    }
    setSelected(next)
  }

  const toggleSelect = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  // --- Actions ---
  const handleVerify = async (e: React.MouseEvent, companyId: string, currentlyVerified: boolean) => {
    e.stopPropagation()
    const msg = currentlyVerified ? t("unverifyConfirm") : t("verifyConfirm")
    if (!window.confirm(msg)) return
    try {
      await companiesAdminApi.verify(companyId, !currentlyVerified)
      fetchCompanies()
      companyDashboardApi.getGlobalStats().then(setGlobalStats).catch(() => {})
    } catch (err) {
      console.error("Verify failed:", err)
    }
  }

  // --- Bulk actions ---
  const handleBulkVerify = async (verify: boolean) => {
    if (selected.size === 0) return
    const msg = verify
      ? `Verificar ${selected.size} empresas?`
      : `Revocar verificación de ${selected.size} empresas?`
    if (!window.confirm(msg)) return
    setBulkLoading(true)
    try {
      await Promise.all(
        Array.from(selected).map(id => companiesAdminApi.verify(id, verify))
      )
      setSelected(new Set())
      fetchCompanies()
      companyDashboardApi.getGlobalStats().then(setGlobalStats).catch(() => {})
    } catch (err) {
      console.error("Bulk verify failed:", err)
    } finally {
      setBulkLoading(false)
    }
  }

  const handleBulkClassify = async () => {
    if (selected.size === 0) return
    if (!window.confirm(`Reclasificar ${selected.size} empresas con IA?`)) return
    setBulkLoading(true)
    try {
      await Promise.all(
        Array.from(selected).map(id => companiesAdminApi.classify(id))
      )
      setSelected(new Set())
      fetchCompanies()
    } catch (err) {
      console.error("Bulk classify failed:", err)
    } finally {
      setBulkLoading(false)
    }
  }

  const handleExportCSV = () => {
    if (!data?.items?.length) return
    const headers = ['legal_name', 'nif', 'tax_id', 'forma_juridica', 'sector_actividad', 'city_name', 'zone_code', 'regimen_fiscal', 'is_active', 'is_verified']
    const rows = data.items
      .filter(c => selected.size === 0 || selected.has(c.id))
      .map(c => headers.map(h => {
        const v = (c as unknown as Record<string, unknown>)[h]
        return v == null ? '' : String(v)
      }))
    const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n')
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `empresas_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // --- Filter presets ---
  const savePreset = () => {
    const name = window.prompt('Nombre del filtro guardado:')
    if (!name) return
    const preset: FilterPreset = { name, isActive, isVerified, regimenFiscal, zoneId }
    const next = [...savedPresets.filter(p => p.name !== name), preset]
    setSavedPresets(next)
    localStorage.setItem(PRESETS_KEY, JSON.stringify(next))
  }

  const loadPreset = (preset: FilterPreset) => {
    setIsActive(preset.isActive)
    setIsVerified(preset.isVerified)
    setRegimenFiscal(preset.regimenFiscal)
    setZoneId(preset.zoneId)
    setPage(1)
  }

  const deletePreset = (name: string) => {
    const next = savedPresets.filter(p => p.name !== name)
    setSavedPresets(next)
    localStorage.setItem(PRESETS_KEY, JSON.stringify(next))
  }

  const resetAllFilters = () => {
    setIsActive('all'); setIsVerified('all'); setRegimenFiscal('all')
    setZoneId('all'); setCityId('all'); setSearchInput(''); setSearch('')
    setPage(1)
  }

  // --- Active filter tags ---
  const activeFilters: { key: string; label: string; onClear: () => void }[] = []
  if (isActive !== 'all') activeFilters.push({ key: 'active', label: isActive === 'true' ? t('active') : t('inactive'), onClear: () => { setIsActive('all'); setPage(1) } })
  if (isVerified !== 'all') activeFilters.push({ key: 'verified', label: isVerified === 'true' ? t('verified') : t('unverified'), onClear: () => { setIsVerified('all'); setPage(1) } })
  if (regimenFiscal !== 'all') activeFilters.push({ key: 'regimen', label: t(regimenFiscal), onClear: () => { setRegimenFiscal('all'); setPage(1) } })
  if (zoneId !== 'all') {
    const z = zones.find(z => z.id === zoneId)
    activeFilters.push({ key: 'zone', label: z ? z.zone_code : 'Zona', onClear: () => { setZoneId('all'); setCityId('all'); setPage(1) } })
  }
  if (cityId !== 'all') {
    const cityObj = cities.find(c => c.id === cityId)
    activeFilters.push({ key: 'city', label: cityObj?.name || 'Ciudad', onClear: () => { setCityId('all'); setPage(1) } })
  }
  if (search) activeFilters.push({ key: 'search', label: `"${search}"`, onClear: () => { setSearchInput(''); setSearch(''); setPage(1) } })

  const basePath = `/${locale}/dashboard/admin/companies`

  // --- Kanban fetch ---
  const doKanbanFetch = useCallback(async (groupBy: KanbanGroupBy, s: string) => {
    const seq = ++kanbanSeqRef.current
    setKanbanLoading(true)
    try {
      if (groupBy === 'regimen') {
        const results = await Promise.all(
          KANBAN_REGIMEN_COLS.map(col =>
            companiesAdminApi.listAll({
              pageSize: KANBAN_PER_COL, page: 1,
              regimenFiscal: col.key,
              search: s || undefined,
            }).then(r => ({ key: col.key, items: r.items as Company[] }))
          )
        )
        if (seq === kanbanSeqRef.current) {
          const d: Record<string, Company[]> = {}
          for (const r of results) d[r.key] = r.items
          setKanbanData(d)
        }
      } else {
        // Group by zone — fetch top zones
        const results = await Promise.all(
          zones.slice(0, 8).map(z =>
            companiesAdminApi.listAll({
              pageSize: KANBAN_PER_COL, page: 1,
              zoneId: z.id,
              search: s || undefined,
            }).then(r => ({ key: z.id, items: r.items as Company[] }))
          )
        )
        if (seq === kanbanSeqRef.current) {
          const d: Record<string, Company[]> = {}
          for (const r of results) d[r.key] = r.items
          setKanbanData(d)
        }
      }
    } catch {
      if (seq === kanbanSeqRef.current) setKanbanData({})
    } finally {
      if (seq === kanbanSeqRef.current) setKanbanLoading(false)
    }
  }, [zones])

  useEffect(() => {
    if (viewMode !== 'kanban') return
    const timer = setTimeout(() => doKanbanFetch(kanbanGroupBy, search), 200)
    return () => clearTimeout(timer)
  }, [viewMode, kanbanGroupBy, search, doKanbanFetch])

  // --- DnD ---
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || !active.data.current) return
    const company = active.data.current.company as Company
    const targetCol = over.id as string

    // Only regime kanban supports DnD reclassification
    if (kanbanGroupBy !== 'regimen') return
    if (company.regimen_fiscal === targetCol) return

    const confirmed = window.confirm(
      `Reclasificar "${company.legal_name}" con IA?\n\nEl agente de clasificación evaluará la empresa y asignará el régimen apropiado (puede diferir de la columna destino).`
    )
    if (!confirmed) return

    try {
      // Use classify endpoint — the agent will reclassify
      await companiesAdminApi.classify(company.id)
      doKanbanFetch(kanbanGroupBy, search)
      companyDashboardApi.getGlobalStats().then(setGlobalStats).catch(() => {})
    } catch (err) {
      console.error("Reclassify failed:", err)
    }
  }

  // --- Derived KPI values ---
  const gs = globalStats
  const totalCompanies = gs?.total_companies ?? 0
  const activeCompanies = gs?.active_companies ?? 0
  const verifiedCompanies = gs?.verified_companies ?? 0
  const activePct = totalCompanies > 0 ? Math.round((activeCompanies / totalCompanies) * 100) : 0
  const verifiedPct = totalCompanies > 0 ? Math.round((verifiedCompanies / totalCompanies) * 100) : 0

  // Sparkline data from monthly_trend (last 6 months)
  const sparkData = useMemo(() => {
    if (!analytics?.monthly_trend?.length) return []
    return analytics.monthly_trend.slice(-6).map(m => m.created)
  }, [analytics])

  // Total debt from debt_by_fee_type
  const totalDebt = useMemo(() => {
    if (!analytics?.debt_by_fee_type?.length) return 0
    return analytics.debt_by_fee_type.reduce((sum, d) => sum + (d.total_amount - d.paid), 0)
  }, [analytics])

  // Donut data for regimes
  const donutData = useMemo(() => {
    if (!gs) return null
    const labels = ['Bundle', 'Declarativo', 'Exento', 'Pendiente']
    const values = [gs.bundle_count, gs.declarativo_count, gs.exento_count, gs.pendiente_count]
    if (values.every(v => v === 0)) return null
    return {
      labels,
      datasets: [{
        data: values,
        backgroundColor: [REGIMEN_COLORS.bundle, REGIMEN_COLORS.declarativo, REGIMEN_COLORS.exento, REGIMEN_COLORS.pendiente],
        borderWidth: 0,
      }],
    }
  }, [gs])

  const donutOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { enabled: true } },
    cutout: '65%',
  }), [])

  // License count from analytics.by_forma_juridica
  const licenseCount = useMemo(() => {
    if (!analytics?.by_forma_juridica?.length) return 0
    return analytics.by_forma_juridica.reduce((sum, f) => sum + f.with_license, 0)
  }, [analytics])

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => router.push(`/${locale}/dashboard/admin/companies/archived`)}
          >
            <Archive className="h-4 w-4 mr-1" />
            Archivadas
          </Button>
          <Button
            size="sm"
            onClick={() => router.push(`/${locale}/dashboard/admin/companies/new`)}
          >
            <Plus className="h-4 w-4 mr-1" />
            {t("createPage.newButton")}
          </Button>
          {viewMode === 'kanban' && (
            <Select value={kanbanGroupBy} onValueChange={(v) => setKanbanGroupBy(v as KanbanGroupBy)}>
              <SelectTrigger className="w-[130px] h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="regimen">Por Régimen</SelectItem>
                <SelectItem value="zone">Por Zona</SelectItem>
              </SelectContent>
            </Select>
          )}
          <div className="flex border rounded-md overflow-hidden">
            <button onClick={() => setViewMode('list')} className={`p-1.5 ${viewMode === 'list' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
              <List className="h-4 w-4" />
            </button>
            <button onClick={() => setViewMode('kanban')} className={`p-1.5 ${viewMode === 'kanban' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
              <Columns3 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* ===== ENRICHED KPI CARDS ===== */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        {/* 1. Total + Sparkline */}
        <Card className="p-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <Building2 className="h-4 w-4 text-blue-500" />
              <p className="text-xs text-muted-foreground">{t("statsTotal")}</p>
            </div>
            {sparkData.length > 0 && <Sparkline data={sparkData} color="#3b82f6" />}
          </div>
          <p className="text-2xl font-bold">{fmt(totalCompanies)}</p>
          {sparkData.length >= 2 && (
            <div className="flex items-center gap-1 mt-0.5">
              <TrendingUp className="h-3 w-3 text-green-500" />
              <span className="text-[10px] text-green-600">
                +{sparkData[sparkData.length - 1] - sparkData[sparkData.length - 2]} este mes
              </span>
            </div>
          )}
        </Card>

        {/* 2. Activas + Gauge */}
        <Card className="p-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <p className="text-xs text-muted-foreground">{t("statsActive")}</p>
              </div>
              <p className="text-2xl font-bold">{fmt(activeCompanies)}</p>
              <p className="text-[10px] text-muted-foreground">{activePct}% del total</p>
            </div>
            <GaugeRing value={activeCompanies} max={totalCompanies} color="#22c55e" size={52} />
          </div>
        </Card>

        {/* 3. Verificadas + Progress bar */}
        <Card className="p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldCheck className="h-4 w-4 text-purple-500" />
            <p className="text-xs text-muted-foreground">{t("statsVerified")}</p>
          </div>
          <p className="text-2xl font-bold">{fmt(verifiedCompanies)}</p>
          <div className="mt-1.5">
            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>{verifiedPct}%</span>
              <span>{verifiedCompanies}/{totalCompanies}</span>
            </div>
            <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${verifiedPct}%`,
                  backgroundColor: verifiedPct >= 80 ? '#22c55e' : verifiedPct >= 50 ? '#f59e0b' : '#ef4444',
                }}
              />
            </div>
          </div>
        </Card>

        {/* 4. Con Licencias + Ratio */}
        <Card className="p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <FolderOpen className="h-4 w-4 text-orange-500" />
            <p className="text-xs text-muted-foreground">{t("statsWithLicenses")}</p>
          </div>
          <p className="text-2xl font-bold">{fmt(licenseCount)}</p>
          <div className="mt-1.5">
            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>Cobertura</span>
              <span>{totalCompanies > 0 ? Math.round((licenseCount / totalCompanies) * 100) : 0}%</span>
            </div>
            <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-orange-400 rounded-full transition-all duration-700"
                style={{ width: `${totalCompanies > 0 ? (licenseCount / totalCompanies) * 100 : 0}%` }}
              />
            </div>
          </div>
        </Card>

        {/* 5. Deuda Total + Alert badge */}
        <Card className="p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertTriangle className={`h-4 w-4 ${totalDebt > 0 ? 'text-red-500' : 'text-gray-400'}`} />
            <p className="text-xs text-muted-foreground">Deuda Total</p>
          </div>
          <p className="text-2xl font-bold">{fmt(totalDebt)}</p>
          <p className="text-[10px] text-muted-foreground">XAF</p>
          {totalDebt > 1_000_000 && (
            <Badge variant="destructive" className="text-[9px] px-1.5 py-0 mt-1">
              Alto riesgo
            </Badge>
          )}
        </Card>

        {/* 6. Mini Donut Régimes */}
        <Card className="p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <p className="text-xs text-muted-foreground">Régimen Fiscal</p>
          </div>
          {donutData ? (
            <div className="flex items-center gap-2">
              <div className="h-14 w-14 shrink-0">
                <Doughnut data={donutData} options={donutOptions} />
              </div>
              <div className="flex flex-col gap-0.5 min-w-0">
                {donutData.labels.map((label, i) => (
                  <div key={label} className="flex items-center gap-1 text-[9px]">
                    <div className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: donutData.datasets[0].backgroundColor[i] as string }} />
                    <span className="truncate text-muted-foreground">{label}</span>
                    <span className="font-semibold ml-auto">{donutData.datasets[0].data[i]}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground text-center py-2">—</p>
          )}
        </Card>
      </div>

      {/* ===== KANBAN VIEW ===== */}
      {viewMode === 'kanban' && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          {kanbanLoading ? (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="min-w-[260px] flex-1">
                  <div className="h-10 bg-gray-100 rounded-t-lg animate-pulse" />
                  <div className="border border-t-0 border-gray-200 rounded-b-lg p-2 space-y-2">
                    {Array.from({ length: 3 }).map((_, j) => (
                      <div key={j} className="h-16 bg-gray-100 rounded animate-pulse" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : kanbanGroupBy === 'regimen' ? (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {KANBAN_REGIMEN_COLS.map(col => {
                const items = kanbanData[col.key] || []
                return (
                  <div key={col.key} className="min-w-[260px] flex-1 flex flex-col">
                    <div className={`flex items-center justify-between px-3 py-2 rounded-t-lg border ${col.bg}`}>
                      <span className="text-xs font-semibold" style={{ color: col.color }}>{col.label}</span>
                      <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-white/70">
                        {items.length}
                      </Badge>
                    </div>
                    <DroppableColumn id={col.key}>
                      {items.length === 0 ? (
                        <p className="text-center text-xs text-muted-foreground py-8">—</p>
                      ) : items.map(c => (
                        <DraggableCard key={c.id} company={c} />
                      ))}
                    </DroppableColumn>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {zones.slice(0, 8).map(z => {
                const items = kanbanData[z.id] || []
                return (
                  <div key={z.id} className="min-w-[240px] flex-1 flex flex-col">
                    <div className="flex items-center justify-between px-3 py-2 rounded-t-lg border bg-gray-50 border-gray-200">
                      <span className="text-xs font-semibold text-gray-700">{z.zone_code}</span>
                      <Badge variant="secondary" className="text-[10px] px-1.5 py-0">{items.length}</Badge>
                    </div>
                    <DroppableColumn id={z.id}>
                      {items.length === 0 ? (
                        <p className="text-center text-xs text-muted-foreground py-8">—</p>
                      ) : items.map(c => (
                        <DraggableCard key={c.id} company={c} />
                      ))}
                    </DroppableColumn>
                  </div>
                )
              })}
            </div>
          )}
        </DndContext>
      )}

      {/* ===== LIST VIEW ===== */}
      {viewMode === 'list' && <>

      {/* ===== FILTERS ===== */}
      <div className="flex flex-wrap gap-2">
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
          <SelectTrigger className="w-[120px] h-9 text-xs"><SelectValue placeholder={t("status")} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allStatuses")}</SelectItem>
            <SelectItem value="true">{t("active")}</SelectItem>
            <SelectItem value="false">{t("inactive")}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={isVerified} onValueChange={(v) => { setIsVerified(v); setPage(1) }}>
          <SelectTrigger className="w-[130px] h-9 text-xs"><SelectValue placeholder={t("allVerification")} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allVerification")}</SelectItem>
            <SelectItem value="true">{t("verified")}</SelectItem>
            <SelectItem value="false">{t("unverified")}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={regimenFiscal} onValueChange={(v) => { setRegimenFiscal(v); setPage(1) }}>
          <SelectTrigger className="w-[140px] h-9 text-xs"><SelectValue placeholder={t("allRegimen")} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allRegimen")}</SelectItem>
            {REGIMEN_OPTIONS.map((r) => (
              <SelectItem key={r} value={r}>{t(r)}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Advanced filters toggle */}
        <Button
          variant={showAdvanced ? 'secondary' : 'ghost'}
          size="sm"
          className="h-9 text-xs gap-1"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Más
          <ChevronDown className={`h-3 w-3 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
        </Button>

        {/* Export + Save preset */}
        <Button variant="outline" size="sm" className="h-9 gap-1 text-xs" onClick={handleExportCSV}>
          <Download className="h-3.5 w-3.5" /> CSV
        </Button>
        <Button variant="ghost" size="sm" className="h-9 gap-1 text-xs" onClick={savePreset} title="Guardar filtros">
          <Save className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Advanced filter panel (zone → city cascade) */}
      {showAdvanced && (
        <div className="flex flex-wrap gap-2 p-3 bg-muted/30 rounded-lg border">
          <Select value={zoneId} onValueChange={(v) => { setZoneId(v); setCityId('all'); setPage(1) }}>
            <SelectTrigger className="w-[160px] h-8 text-xs"><SelectValue placeholder="Zona" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las zonas</SelectItem>
              {zones.map(z => <SelectItem key={z.id} value={z.id}>{z.zone_code} — {z.name_es}</SelectItem>)}
            </SelectContent>
          </Select>

          {zoneId !== 'all' && cities.length > 0 && (
            <Select value={cityId} onValueChange={(v) => { setCityId(v); setPage(1) }}>
              <SelectTrigger className="w-[160px] h-8 text-xs"><SelectValue placeholder="Ciudad" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las ciudades</SelectItem>
                {cities.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          )}

          {/* Saved presets */}
          {savedPresets.length > 0 && (
            <div className="flex items-center gap-1 ml-auto">
              <Star className="h-3.5 w-3.5 text-amber-400" />
              {savedPresets.map(p => (
                <div key={p.name} className="flex items-center gap-0.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs px-2"
                    onClick={() => loadPreset(p)}
                  >
                    {p.name}
                  </Button>
                  <button onClick={() => deletePreset(p.name)} className="text-gray-300 hover:text-red-400">
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Filter tags */}
      {activeFilters.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {activeFilters.map(f => (
            <Badge key={f.key} variant="secondary" className="text-xs gap-1 pr-1">
              {f.label}
              <button onClick={f.onClear} className="ml-0.5 hover:text-destructive">
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          <Button variant="ghost" size="sm" className="h-6 text-xs text-muted-foreground" onClick={resetAllFilters}>
            Limpiar todo
          </Button>
        </div>
      )}

      {/* ===== BULK ACTION BAR ===== */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-xs font-medium text-blue-700">{selected.size} seleccionadas</span>
          <div className="flex gap-1 ml-auto">
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={() => handleBulkVerify(true)} disabled={bulkLoading}>
              <ShieldCheck className="h-3 w-3" /> Verificar
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={() => handleBulkVerify(false)} disabled={bulkLoading}>
              <XCircle className="h-3 w-3" /> Revocar
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={handleBulkClassify} disabled={bulkLoading}>
              <Brain className="h-3 w-3" /> Clasificar IA
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setSelected(new Set())}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {/* ===== DATA TABLE ===== */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px]">
                  <Checkbox
                    checked={allOnPageSelected && (data?.items?.length ?? 0) > 0}
                    onCheckedChange={toggleSelectAll}
                    aria-label="Seleccionar todo"
                  />
                </TableHead>
                <TableHead>
                  <button onClick={() => toggleSort('legal_name')} className="flex items-center gap-1 hover:text-foreground">
                    {t("legalName")}
                    {sortBy === 'legal_name' ? (sortOrder === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-30" />}
                  </button>
                </TableHead>
                <TableHead className="w-[100px]">Identificador</TableHead>
                <TableHead className="w-[100px]">{t("city")}</TableHead>
                <TableHead className="w-[70px]">{t("zone")}</TableHead>
                <TableHead className="w-[100px]">{t("regimen")}</TableHead>
                <TableHead className="w-[70px] text-center">{t("members")}</TableHead>
                <TableHead className="w-[80px]">
                  <button onClick={() => toggleSort('is_active')} className="flex items-center gap-1 hover:text-foreground">
                    {t("status")}
                    {sortBy === 'is_active' ? (sortOrder === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-30" />}
                  </button>
                </TableHead>
                <TableHead className="w-[80px]">
                  <button onClick={() => toggleSort('is_verified')} className="flex items-center gap-1 hover:text-foreground">
                    {t("isVerified")}
                    {sortBy === 'is_verified' ? (sortOrder === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-30" />}
                  </button>
                </TableHead>
                <TableHead className="w-[50px]"></TableHead>
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
              ) : data.items.map((company) => {
                const isExpanded = expandedId === company.id
                return (
                  <TableRow key={company.id} className="group">
                    {/* Checkbox */}
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={selected.has(company.id)}
                        onCheckedChange={() => toggleSelect(company.id)}
                        aria-label={`Seleccionar ${company.legal_name}`}
                      />
                    </TableCell>
                    {/* Name + expand toggle */}
                    <TableCell className="font-medium text-sm">
                      <div className="flex items-start gap-1">
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : company.id)}
                          className="mt-0.5 shrink-0"
                        >
                          <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                        </button>
                        <div
                          className="cursor-pointer hover:underline"
                          onClick={() => router.push(`${basePath}/${company.id}`)}
                        >
                          <span>{company.legal_name}</span>
                          {company.trade_name && (
                            <span className="block text-xs text-muted-foreground">{company.trade_name}</span>
                          )}
                        </div>
                      </div>
                      {/* Expanded details */}
                      {isExpanded && (
                        <div className="mt-2 ml-5 p-2.5 bg-muted/30 rounded-md border border-muted space-y-1.5">
                          {company.forma_juridica && (
                            <div className="flex items-center gap-1.5 text-xs">
                              <FileText className="h-3 w-3 text-blue-400" />
                              <span className="text-muted-foreground">Forma:</span>
                              <span className="font-medium">{company.forma_juridica}</span>
                            </div>
                          )}
                          {company.sector_actividad && (
                            <div className="flex items-center gap-1.5 text-xs">
                              <Briefcase className="h-3 w-3 text-emerald-400" />
                              <span className="text-muted-foreground">Sector:</span>
                              <span className="font-medium">
                                {company.sector_actividad}
                                {company.subsector_actividad && ` / ${company.subsector_actividad}`}
                              </span>
                            </div>
                          )}
                          {company.objeto_social && (
                            <div className="flex items-start gap-1.5 text-xs">
                              <Briefcase className="h-3 w-3 text-gray-400 mt-0.5" />
                              <span className="text-muted-foreground shrink-0">Objeto:</span>
                              <span className="line-clamp-2">{company.objeto_social}</span>
                            </div>
                          )}
                          {company.address && (
                            <div className="flex items-center gap-1.5 text-xs">
                              <MapPin className="h-3 w-3 text-rose-400" />
                              <span className="text-muted-foreground">Dirección:</span>
                              <span>{company.address}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-3 text-xs text-muted-foreground pt-1 border-t border-muted">
                            <span>Miembros: <strong>{company.member_count || 0}</strong></span>
                            {company.registration_number && <span>Reg: <strong className="font-mono">{company.registration_number}</strong></span>}
                          </div>
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{company.registration_number || company.nif || "-"}</TableCell>
                    <TableCell className="text-xs">{company.city_name || "-"}</TableCell>
                    <TableCell className="text-xs">{company.zone_code || "-"}</TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className="text-xs"
                        style={{
                          borderColor: REGIMEN_COLORS[company.regimen_fiscal ?? 'pendiente'] ?? REGIMEN_COLORS.pendiente,
                          color: REGIMEN_COLORS[company.regimen_fiscal ?? 'pendiente'] ?? REGIMEN_COLORS.pendiente,
                        }}
                      >
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
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-7 w-7">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                          <DropdownMenuItem onClick={() => router.push(`${basePath}/${company.id}`)}>
                            <Eye className="h-3.5 w-3.5 mr-2" />
                            {t("view")}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => window.open(`${basePath}/${company.id}`, '_blank')}>
                            <ExternalLink className="h-3.5 w-3.5 mr-2" />
                            Abrir en nueva pestaña
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={(e) => handleVerify(e as unknown as React.MouseEvent, company.id, !!company.is_verified)}>
                            <ShieldCheck className={`h-3.5 w-3.5 mr-2 ${company.is_verified ? 'text-green-500' : 'text-gray-400'}`} />
                            {company.is_verified ? t("unverify") : t("verify")}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => { companiesAdminApi.classify(company.id).then(() => fetchCompanies()).catch(() => {}) }}>
                            <Brain className="h-3.5 w-3.5 mr-2 text-violet-500" />
                            {t("classify")}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => router.push(`/${locale}/dashboard/admin/licenses?company=${company.id}`)}>
                            <FolderSearch className="h-3.5 w-3.5 mr-2 text-orange-500" />
                            Ver licencias
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ===== PAGINATION ===== */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          {data ? t("pageInfo", { total: data.total, page, totalPages }) : ''}
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

      </>}
    </div>
  )
}
