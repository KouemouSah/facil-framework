'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import {
  Building2, Search, MapPin, ChevronLeft, ChevronRight, ChevronDown,
  Briefcase, FileText, Users, LayoutGrid, List, X, SlidersHorizontal,
  ArrowUpDown, ArrowUp, ArrowDown, Columns3,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetClose,
} from '@/components/ui/sheet'
import { companyPublicApi } from '@/modules/companies/services/api'
import { getLocalizedName } from '@/core/utils/i18n-helpers'
import {
  useAnnuaireSearch,
  useAnnuaireZones,
  useAnnuaireSectors,
  useAnnuaireProvincias,
  useAnnuaireCiudades,
  useAnnuaireFormas,
  useAnnuairePrefetch,
} from '@/modules/companies/hooks/useAnnuaireSearch'
import type { PublicCompany } from '@/modules/companies/types'

const PAGE_SIZE = 20
const KANBAN_PER_COL = 10

const FORMA_LABELS: Record<string, { label: string; color: string }> = {
  autonomo: { label: 'Autónomo', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  sociedad_limitada: { label: 'S.L.', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  sociedad_anonima: { label: 'S.A.', color: 'bg-violet-50 text-violet-700 border-violet-200' },
  ong: { label: 'ONG', color: 'bg-amber-50 text-amber-700 border-amber-200' },
  cooperativa: { label: 'Cooperativa', color: 'bg-cyan-50 text-cyan-700 border-cyan-200' },
  sucursal: { label: 'Sucursal', color: 'bg-slate-50 text-slate-600 border-slate-200' },
  empresa_individual: { label: 'Emp. Individual', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
}

const SORT_COLUMNS = [
  { key: 'legal_name', i18nKey: 'sortByName' },
  { key: 'city', i18nKey: 'sortByCity' },
  { key: 'sector', i18nKey: 'sortBySector' },
  { key: 'forma', i18nKey: 'sortByForma' },
] as const

type FormaCount = { value: string; count: number }

// =============================================================================
// DEBOUNCE HOOK
// =============================================================================

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

// =============================================================================
// PAGE COMPONENT
// =============================================================================

export default function AnnuairePage() {
  const locale = useLocale()
  const t = useTranslations('public')

  // --- Search & filter state ---
  const [query, setQuery] = useState('')
  const [zoneId, setZoneId] = useState('')
  const [sector, setSector] = useState('')
  const [formaJuridica, setFormaJuridica] = useState('')
  const [provincia, setProvincia] = useState('')
  const [ciudad, setCiudad] = useState('')
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('legal_name')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')

  // Debounce search query (350ms)
  const debouncedQuery = useDebouncedValue(query, 350)

  // Reset page when debounced query changes (NOT on keystroke — avoids flash)
  const prevDebouncedRef = useRef(debouncedQuery)
  useEffect(() => {
    if (prevDebouncedRef.current !== debouncedQuery) {
      prevDebouncedRef.current = debouncedQuery
      setPage(1)
    }
  }, [debouncedQuery])

  // --- Kanban state (manual — multi-query parallel) ---
  const [kanbanData, setKanbanData] = useState<Record<string, PublicCompany[]>>({})
  const [kanbanLoading, setKanbanLoading] = useState(false)
  const kanbanSeqRef = useRef(0)

  // --- UI state ---
  const [viewMode, setViewMode] = useState<'grid' | 'list' | 'kanban'>('grid')
  const [showFilters, setShowFilters] = useState(false)
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)

  // --- React Query: search ---
  const searchParams = useMemo(() => ({
    q: debouncedQuery || undefined,
    zone_id: zoneId || undefined,
    sector: sector || undefined,
    forma_juridica: formaJuridica || undefined,
    provincia: provincia || undefined,
    ciudad: ciudad || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
    page,
    page_size: PAGE_SIZE,
  }), [debouncedQuery, zoneId, sector, formaJuridica, provincia, ciudad, sortBy, sortOrder, page])

  const { data: searchData, isLoading: loading } = useAnnuaireSearch(
    searchParams,
    viewMode !== 'kanban',
  )

  const items = searchData?.items ?? []
  const total = searchData?.total ?? 0

  // --- React Query: filter options ---
  const { data: zones = [] } = useAnnuaireZones()
  const { data: sectors = [] } = useAnnuaireSectors()
  const { data: provincias = [] } = useAnnuaireProvincias()
  const { data: ciudades = [] } = useAnnuaireCiudades(provincia)
  const { data: formaCounts = [] } = useAnnuaireFormas()

  // --- Prefetch next page ---
  const prefetchSearch = useAnnuairePrefetch()

  const handlePrefetchNext = useCallback(() => {
    const totalPages = Math.ceil(total / PAGE_SIZE) || 1
    if (page < totalPages) {
      prefetchSearch({ ...searchParams, page: page + 1 })
    }
  }, [prefetchSearch, searchParams, page, total])

  const handlePrefetchPrev = useCallback(() => {
    if (page > 1) {
      prefetchSearch({ ...searchParams, page: page - 1 })
    }
  }, [prefetchSearch, searchParams, page])

  // Reset ciudad when provincia changes
  useEffect(() => {
    if (!provincia) setCiudad('')
  }, [provincia])

  // --- Kanban: parallel fetch per forma column ---
  const doKanbanFetch = useCallback(async (
    q: string, z: string, s: string, p: string, ci: string, columns: FormaCount[],
  ) => {
    if (columns.length === 0) return
    const seq = ++kanbanSeqRef.current
    setKanbanLoading(true)
    try {
      const results = await Promise.all(
        columns.map(fc =>
          companyPublicApi.search({
            q: q || undefined, zone_id: z || undefined, sector: s || undefined,
            forma_juridica: fc.value, provincia: p || undefined, ciudad: ci || undefined,
            sort_by: 'legal_name', sort_order: 'asc',
            page: 1, page_size: KANBAN_PER_COL,
          }).then(res => ({ forma: fc.value, items: res.items }))
        ),
      )
      if (seq === kanbanSeqRef.current) {
        const data: Record<string, PublicCompany[]> = {}
        for (const r of results) data[r.forma] = r.items
        setKanbanData(data)
      }
    } catch {
      if (seq === kanbanSeqRef.current) setKanbanData({})
    } finally {
      if (seq === kanbanSeqRef.current) setKanbanLoading(false)
    }
  }, [])

  useEffect(() => {
    if (viewMode !== 'kanban' || formaCounts.length === 0) return
    const timer = setTimeout(
      () => doKanbanFetch(debouncedQuery, zoneId, sector, provincia, ciudad, formaCounts),
      100,
    )
    return () => clearTimeout(timer)
  }, [viewMode, debouncedQuery, zoneId, sector, provincia, ciudad, formaCounts, doKanbanFetch])

  // --- Derived ---
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1
  const activeFilterCount = [zoneId, sector, formaJuridica, provincia, ciudad].filter(Boolean).length

  const resetFilters = () => {
    setZoneId(''); setSector(''); setFormaJuridica(''); setProvincia(''); setCiudad('')
    setPage(1)
  }

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortOrder('asc')
    }
    setPage(1)
  }

  const getForma = (f?: string | null) => {
    if (!f) return null
    return FORMA_LABELS[f] || { label: f, color: 'bg-gray-50 text-gray-600 border-gray-200' }
  }
  const getId = (c: PublicCompany) => c.nif || c.registration_number || ''
  const getIdPrefix = (c: PublicCompany) => c.nif ? 'NIF' : c.registration_number ? 'Reg.' : ''

  // ===================== Filter Controls (shared between inline & sheet) =====================

  const FilterControls = () => (
    <div className="flex flex-col gap-3">
      <Select value={provincia} onValueChange={(v) => { setProvincia(v === 'all' ? '' : v); setCiudad(''); setPage(1) }}>
        <SelectTrigger className="h-9 text-xs bg-white">
          <SelectValue placeholder="Provincia" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todas las provincias</SelectItem>
          {provincias.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
        </SelectContent>
      </Select>

      {provincia && ciudades.length > 0 && (
        <Select value={ciudad} onValueChange={(v) => { setCiudad(v === 'all' ? '' : v); setPage(1) }}>
          <SelectTrigger className="h-9 text-xs bg-white">
            <SelectValue placeholder="Ciudad" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas las ciudades</SelectItem>
            {ciudades.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      )}

      <Select value={zoneId} onValueChange={(v) => { setZoneId(v === 'all' ? '' : v); setPage(1) }}>
        <SelectTrigger className="h-9 text-xs bg-white">
          <SelectValue placeholder={t('annuaire.allZones')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('annuaire.allZones')}</SelectItem>
          {zones.map(z => <SelectItem key={z.id} value={z.id}>{z.zone_code} — {getLocalizedName(z as unknown as Record<string, unknown>, locale)}</SelectItem>)}
        </SelectContent>
      </Select>

      <Select value={sector} onValueChange={(v) => { setSector(v === 'all' ? '' : v); setPage(1) }}>
        <SelectTrigger className="h-9 text-xs bg-white">
          <SelectValue placeholder={t('annuaire.allSectors')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('annuaire.allSectors')}</SelectItem>
          {sectors.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
        </SelectContent>
      </Select>

      <Select value={formaJuridica} onValueChange={(v) => { setFormaJuridica(v === 'all' ? '' : v); setPage(1) }}>
        <SelectTrigger className="h-9 text-xs bg-white">
          <SelectValue placeholder="Forma jurídica" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todas las formas</SelectItem>
          {formaCounts.map(fc => {
            const label = FORMA_LABELS[fc.value]?.label || fc.value
            return (
              <SelectItem key={fc.value} value={fc.value}>
                {label} ({fc.count})
              </SelectItem>
            )
          })}
        </SelectContent>
      </Select>

      {activeFilterCount > 0 && (
        <Button variant="ghost" size="sm" className="h-9 text-xs text-gray-400 gap-1 w-full" onClick={() => { resetFilters(); setMobileFiltersOpen(false) }}>
          <X className="h-3 w-3" /> Limpiar filtros
        </Button>
      )}
    </div>
  )

  // ===================== Skeleton Components =====================

  const CardSkeleton = ({ compact }: { compact?: boolean }) => (
    <div className={`border border-gray-100 rounded-lg bg-white ${compact ? 'p-3' : 'p-4'}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-start gap-2 min-w-0 flex-1">
          <Skeleton className="h-4 w-4 mt-0.5 rounded shrink-0" />
          <Skeleton className="h-4 w-3/4" />
        </div>
        <Skeleton className="h-4 w-12 rounded-full shrink-0" />
      </div>
      <div className="ml-6 space-y-1.5">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  )

  // ===================== Empty State SVG =====================

  const EmptyState = () => (
    <div className="text-center py-16 px-4">
      <svg className="mx-auto mb-6 text-gray-300" width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="20" y="40" width="30" height="50" rx="2" fill="currentColor" opacity="0.15" />
        <rect x="55" y="25" width="25" height="65" rx="2" fill="currentColor" opacity="0.2" />
        <rect x="85" y="50" width="20" height="40" rx="2" fill="currentColor" opacity="0.12" />
        <rect x="27" y="48" width="6" height="6" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="37" y="48" width="6" height="6" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="27" y="60" width="6" height="6" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="37" y="60" width="6" height="6" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="62" y="33" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="71" y="33" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="62" y="44" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="71" y="44" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="62" y="55" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="71" y="55" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="62" y="66" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="71" y="66" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="90" y="58" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <rect x="90" y="68" width="5" height="5" rx="1" fill="currentColor" opacity="0.3" />
        <line x1="10" y1="90" x2="110" y2="90" stroke="currentColor" strokeWidth="1.5" opacity="0.15" />
        <circle cx="90" cy="30" r="12" stroke="currentColor" strokeWidth="2.5" opacity="0.25" fill="none" />
        <line x1="99" y1="39" x2="108" y2="48" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" opacity="0.25" />
        <text x="90" y="35" textAnchor="middle" fill="currentColor" opacity="0.3" fontSize="14" fontWeight="bold">?</text>
      </svg>
      <p className="text-gray-500 font-medium mb-1">{t('annuaire.noResults')}</p>
      <p className="text-gray-400 text-sm">{t('annuaire.noResultsHint')}</p>
    </div>
  )

  // ===================== Company Card =====================

  const CompanyCard = ({ c, compact }: { c: PublicCompany; compact?: boolean }) => {
    const forma = getForma(c.forma_juridica)
    return (
      <div className={`group border border-gray-200 rounded-lg bg-white hover:border-gray-300 hover:shadow-sm active:shadow-sm transition-all ${compact ? 'p-3' : 'p-4'}`}>
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="flex items-start gap-2 min-w-0">
            <Building2 className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
            <h3 className={`font-semibold text-gray-900 leading-tight ${compact ? 'text-sm' : 'text-base'} line-clamp-1`}>
              {c.legal_name}
            </h3>
          </div>
          {forma && (
            <Badge variant="outline" className={`text-[10px] px-1.5 py-0 shrink-0 border ${forma.color}`}>
              {forma.label}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500 ml-6 mb-1">
          <FileText className="h-3 w-3 text-amber-500 shrink-0" />
          <span className="font-mono">{getIdPrefix(c)} {getId(c)}</span>
        </div>
        {(c.sector_actividad || c.objeto_social) && (
          <div className="flex items-start gap-1.5 text-xs text-gray-500 ml-6 mb-1">
            <Briefcase className="h-3 w-3 text-emerald-500 mt-0.5 shrink-0" />
            <p className="line-clamp-1">
              {c.sector_actividad && (
                <span className="font-medium text-gray-600">
                  {c.sector_actividad}
                  {c.subsector_actividad && ` / ${c.subsector_actividad}`}
                </span>
              )}
              {c.sector_actividad && c.objeto_social && <span className="text-gray-300"> | </span>}
              {c.objeto_social && <span>{c.objeto_social}</span>}
            </p>
          </div>
        )}
        {(c.city_name || c.address) && (
          <div className="flex items-center gap-1.5 text-xs text-gray-500 ml-6">
            <MapPin className="h-3 w-3 text-rose-400 shrink-0" />
            {c.city_name && <span>{c.city_name}{c.provincia ? `, ${c.provincia}` : ''}</span>}
            {c.city_name && c.address && <span className="text-gray-300">|</span>}
            {c.address && <span className="truncate">{c.address}</span>}
          </div>
        )}
      </div>
    )
  }

  // ===================== Sort Header (list mode) =====================

  const SortHeader = ({ colKey, children }: { colKey: string; children: React.ReactNode }) => {
    const isActive = sortBy === colKey
    return (
      <button
        onClick={() => toggleSort(colKey)}
        className={`flex items-center gap-1 text-xs font-medium px-2 py-1.5 rounded transition-colors ${
          isActive ? 'text-blue-700 bg-blue-50' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
        }`}
      >
        {children}
        {isActive ? (
          sortOrder === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        )}
      </button>
    )
  }

  // ===================== Render =====================

  return (
    <div className="container mx-auto px-4 py-6 sm:py-8 max-w-6xl">
      {/* Header */}
      <div className="text-center mb-4 sm:mb-6">
        <div className="inline-flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-blue-50 mb-2 sm:mb-3">
          <Users className="h-5 w-5 sm:h-6 sm:w-6 text-blue-600" />
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">{t('annuaire.title')}</h1>
        <p className="text-xs sm:text-sm text-gray-500 mt-1">{t('annuaire.subtitle')}</p>
      </div>

      {/* Sticky search + filter bar on mobile */}
      <div className="sticky top-0 z-10 -mx-4 px-4 pb-2 bg-white/95 backdrop-blur-sm md:static md:mx-0 md:px-0 md:bg-transparent md:backdrop-blur-none">
        {/* Search */}
        <div className="relative mb-2 sm:mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-400" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('annuaire.searchPlaceholder')}
            className="pl-10 h-10 bg-white border-gray-200 focus:border-blue-400"
          />
        </div>

        {/* Filter bar */}
        <div className="flex gap-2 mb-2 flex-wrap items-center">
          {/* Desktop: inline sector + forma dropdowns */}
          <div className="hidden sm:contents">
            <Select value={sector} onValueChange={(v) => { setSector(v === 'all' ? '' : v); setPage(1) }}>
              <SelectTrigger className="w-[140px] h-8 text-xs bg-white">
                <SelectValue placeholder={t('annuaire.allSectors')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('annuaire.allSectors')}</SelectItem>
                {sectors.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>

            <Select value={formaJuridica} onValueChange={(v) => { setFormaJuridica(v === 'all' ? '' : v); setPage(1) }}>
              <SelectTrigger className="w-[170px] h-8 text-xs bg-white">
                <SelectValue placeholder="Forma jurídica" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las formas</SelectItem>
                {formaCounts.map(fc => {
                  const label = FORMA_LABELS[fc.value]?.label || fc.value
                  return (
                    <SelectItem key={fc.value} value={fc.value}>
                      {label} ({fc.count})
                    </SelectItem>
                  )
                })}
              </SelectContent>
            </Select>
          </div>

          {/* Forma count badges — desktop only, when no filter active */}
          {!formaJuridica && formaCounts.length > 0 && (
            <div className="hidden md:flex items-center gap-1">
              {formaCounts.slice(0, 4).map(fc => {
                const forma = FORMA_LABELS[fc.value]
                if (!forma) return null
                return (
                  <button
                    key={fc.value}
                    onClick={() => { setFormaJuridica(fc.value); setPage(1) }}
                    className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border transition-colors hover:opacity-80 ${forma.color}`}
                  >
                    {forma.label}
                    <span className="font-semibold">{fc.count}</span>
                  </button>
                )
              })}
            </div>
          )}

          {/* Desktop: advanced filters toggle */}
          <Button
            variant={showFilters ? 'secondary' : 'ghost'}
            size="sm"
            className="hidden sm:inline-flex h-8 text-xs gap-1"
            onClick={() => setShowFilters(!showFilters)}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Filtros
            {activeFilterCount > 0 && (
              <Badge className="bg-blue-600 text-white text-[10px] px-1 py-0 ml-1">{activeFilterCount}</Badge>
            )}
            <ChevronDown className={`h-3 w-3 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
          </Button>

          {/* Mobile: bottom sheet trigger */}
          <Button
            variant="ghost"
            size="sm"
            className="sm:hidden h-8 text-xs gap-1"
            onClick={() => setMobileFiltersOpen(true)}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Filtros
            {activeFilterCount > 0 && (
              <Badge className="bg-blue-600 text-white text-[10px] px-1 py-0 ml-1">{activeFilterCount}</Badge>
            )}
          </Button>

          {/* Desktop clear */}
          {activeFilterCount > 0 && (
            <Button variant="ghost" size="sm" className="hidden sm:inline-flex h-8 text-xs text-gray-400 gap-1" onClick={resetFilters}>
              <X className="h-3 w-3" /> Limpiar
            </Button>
          )}

          {/* View toggle + count */}
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs text-gray-400 hidden sm:inline">{total.toLocaleString()} {t('annuaire.results')}</span>
            <span className="text-xs text-gray-400 sm:hidden">{total.toLocaleString()}</span>
            <div className="flex border border-gray-200 rounded-md overflow-hidden">
              <button onClick={() => setViewMode('grid')} className={`p-1.5 ${viewMode === 'grid' ? 'bg-blue-50 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}>
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => setViewMode('list')} className={`p-1.5 ${viewMode === 'list' ? 'bg-blue-50 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}>
                <List className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => setViewMode('kanban')} className={`p-1.5 hidden sm:block ${viewMode === 'kanban' ? 'bg-blue-50 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}>
                <Columns3 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile bottom sheet filters */}
      <Sheet open={mobileFiltersOpen} onOpenChange={setMobileFiltersOpen}>
        <SheetContent side="bottom" className="rounded-t-2xl max-h-[80vh] overflow-y-auto">
          <SheetHeader className="pb-4">
            <SheetTitle className="text-base">Filtros</SheetTitle>
            <SheetDescription className="sr-only">
              Filtrar empresas por provincia, ciudad, zona y forma jurídica
            </SheetDescription>
          </SheetHeader>
          <FilterControls />
          <div className="mt-4 pt-3 border-t">
            <SheetClose asChild>
              <Button className="w-full h-10" size="sm">
                {t('annuaire.results')}: {total.toLocaleString()}
              </Button>
            </SheetClose>
          </div>
        </SheetContent>
      </Sheet>

      {/* Desktop: advanced filters — expandable inline */}
      {showFilters && (
        <div className="hidden sm:flex gap-2 mb-4 flex-wrap p-3 bg-gray-50 rounded-lg border border-gray-100">
          <Select value={provincia} onValueChange={(v) => { setProvincia(v === 'all' ? '' : v); setCiudad(''); setPage(1) }}>
            <SelectTrigger className="w-[160px] h-8 text-xs bg-white">
              <SelectValue placeholder="Provincia" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las provincias</SelectItem>
              {provincias.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
            </SelectContent>
          </Select>

          {provincia && ciudades.length > 0 && (
            <Select value={ciudad} onValueChange={(v) => { setCiudad(v === 'all' ? '' : v); setPage(1) }}>
              <SelectTrigger className="w-[160px] h-8 text-xs bg-white">
                <SelectValue placeholder="Ciudad" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las ciudades</SelectItem>
                {ciudades.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          )}

          <Select value={zoneId} onValueChange={(v) => { setZoneId(v === 'all' ? '' : v); setPage(1) }}>
            <SelectTrigger className="w-[160px] h-8 text-xs bg-white">
              <SelectValue placeholder={t('annuaire.allZones')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('annuaire.allZones')}</SelectItem>
              {zones.map(z => <SelectItem key={z.id} value={z.id}>{z.zone_code} — {getLocalizedName(z as unknown as Record<string, unknown>, locale)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* ===== KANBAN VIEW ===== */}
      {viewMode === 'kanban' ? (
        kanbanLoading ? (
          <div className="flex gap-4 overflow-x-auto pb-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="min-w-[260px] w-[260px] shrink-0">
                <Skeleton className="h-8 w-full mb-3 rounded" />
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, j) => (
                    <CardSkeleton key={j} compact />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : formaCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="flex gap-4 overflow-x-auto pb-4 -mx-4 px-4 snap-x snap-mandatory md:snap-none">
            {formaCounts.map(fc => {
              const forma = FORMA_LABELS[fc.value]
              const colItems = kanbanData[fc.value] || []
              const label = forma?.label || fc.value
              const colorCls = forma?.color || 'bg-gray-50 text-gray-600 border-gray-200'
              return (
                <div key={fc.value} className="min-w-[260px] w-[260px] shrink-0 flex flex-col snap-start">
                  <div className={`flex items-center justify-between px-3 py-2 rounded-t-lg border ${colorCls}`}>
                    <span className="text-xs font-semibold">{label}</span>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-white/70">
                      {fc.count}
                    </Badge>
                  </div>
                  <div className="flex-1 bg-gray-50/50 border border-t-0 border-gray-200 rounded-b-lg p-2 space-y-2 max-h-[600px] overflow-y-auto">
                    {colItems.length === 0 ? (
                      <p className="text-center text-xs text-gray-400 py-6">—</p>
                    ) : (
                      colItems.map(c => (
                        <div key={c.id} className="bg-white border border-gray-150 rounded-md p-2.5 hover:shadow-sm transition-shadow">
                          <div className="flex items-start gap-1.5 mb-1">
                            <Building2 className="h-3.5 w-3.5 text-blue-500 mt-0.5 shrink-0" />
                            <h4 className="text-xs font-semibold text-gray-900 leading-tight line-clamp-2">
                              {c.legal_name}
                            </h4>
                          </div>
                          {(c.nif || c.registration_number) && (
                            <div className="flex items-center gap-1 text-[10px] text-gray-400 ml-5 mb-0.5">
                              <FileText className="h-2.5 w-2.5" />
                              <span className="font-mono">{c.nif || c.registration_number}</span>
                            </div>
                          )}
                          {c.sector_actividad && (
                            <div className="flex items-center gap-1 text-[10px] text-gray-400 ml-5 mb-0.5">
                              <Briefcase className="h-2.5 w-2.5 text-emerald-400" />
                              <span className="line-clamp-1">{c.sector_actividad}</span>
                            </div>
                          )}
                          {c.city_name && (
                            <div className="flex items-center gap-1 text-[10px] text-gray-400 ml-5">
                              <MapPin className="h-2.5 w-2.5 text-rose-400" />
                              <span>{c.city_name}{c.provincia ? `, ${c.provincia}` : ''}</span>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                    {colItems.length > 0 && colItems.length < fc.count && (
                      <button
                        onClick={() => { setFormaJuridica(fc.value); setViewMode('grid'); setPage(1) }}
                        className="w-full text-center text-[10px] text-blue-600 hover:text-blue-700 py-1.5 font-medium"
                      >
                        +{fc.count - colItems.length} más →
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )
      ) : (
        <>
          {/* Sort headers (list mode only, desktop) */}
          {viewMode === 'list' && !loading && items.length > 0 && (
            <div className="hidden sm:flex items-center gap-1 mb-2 border-b border-gray-100 pb-2">
              {SORT_COLUMNS.map(col => (
                <SortHeader key={col.key} colKey={col.key}>
                  {t(`annuaire.${col.i18nKey}`)}
                </SortHeader>
              ))}
            </div>
          )}

          {/* Grid/List Results */}
          {loading ? (
            <div className="grid gap-3 grid-cols-1 md:grid-cols-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <CardSkeleton key={i} compact={viewMode === 'list'} />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="grid gap-3 grid-cols-1 md:grid-cols-2">
              {items.map(c => <CompanyCard key={c.id} c={c} compact={viewMode === 'list'} />)}
            </div>
          )}

          {/* Pagination — touch-friendly on mobile */}
          {totalPages > 1 && !loading && (
            <div className="flex items-center justify-center gap-2 sm:gap-3 mt-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                onMouseEnter={handlePrefetchPrev}
                disabled={page <= 1}
                className="text-gray-500 h-10 w-10 sm:h-8 sm:w-auto p-0 sm:px-3"
              >
                <ChevronLeft className="h-5 w-5 sm:h-4 sm:w-4" />
              </Button>
              <span className="text-sm sm:text-xs text-gray-500 tabular-nums min-w-[4rem] text-center">{page} / {totalPages}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                onMouseEnter={handlePrefetchNext}
                disabled={page >= totalPages}
                className="text-gray-500 h-10 w-10 sm:h-8 sm:w-auto p-0 sm:px-3"
              >
                <ChevronRight className="h-5 w-5 sm:h-4 sm:w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
