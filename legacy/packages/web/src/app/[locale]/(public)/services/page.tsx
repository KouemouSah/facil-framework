'use client'

import { useState, useEffect, useCallback, Suspense, useRef, useMemo } from 'react'
import { useRouter, useSearchParams, useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Search, X, AlertCircle, Loader2, ChevronLeft, ChevronRight,
  LayoutGrid, List, Calculator, SlidersHorizontal
} from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import Breadcrumb from "@/components/ui/breadcrumb"
import {
  searchServices,
  getDefaultSearchResponse,
  formatPrice,
  type SearchFilters,
  type SearchResponse,
  type ServiceResult,
  type FacetItem,
} from "@/core/api/services"

type ViewMode = 'grid' | 'list'
type SortOption = 'relevance' | 'name_asc' | 'name_desc' | 'price_asc' | 'price_desc'
type PriceFilter = 'all' | 'free' | 'formula'

// Constants
const ITEMS_PER_PAGE = 18

// Hardcoded service types list with translation keys (defined outside component to avoid re-creation)
const SERVICE_TYPES_LIST = [
  { type: 'document_processing', key: 'document_processing' },
  { type: 'license_permit', key: 'license_permit' },
  { type: 'residence_permit', key: 'residence_permit' },
  { type: 'registration_fee', key: 'registration_fee' },
  { type: 'inspection_fee', key: 'inspection_fee' },
  { type: 'administrative_tax', key: 'administrative_tax' },
  { type: 'customs_duty', key: 'customs_duty' },
  { type: 'declaration_tax', key: 'declaration_tax' },
] as const

/**
 * Services Content - Component that uses useSearchParams
 */
function ServicesContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const params = useParams()
  const locale = (params?.locale as string) || 'es'
  const t = useTranslations('services')
  const tCommon = useTranslations('common')

  const freeLabel = t('free')

  // State
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // View mode with localStorage persistence
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('services-view-mode')
      return (saved as ViewMode) || 'grid'
    }
    return 'grid'
  })

  // Search input state (local, for controlled input)
  const [searchInputValue, setSearchInputValue] = useState('')

  // Search filters state (used for API calls)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMinistry, setSelectedMinistry] = useState<number | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedServiceType, setSelectedServiceType] = useState<string | null>(null)
  const [sortOption, setSortOption] = useState<SortOption>('relevance')
  const [priceFilter, setPriceFilter] = useState<PriceFilter>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [filtersOpen, setFiltersOpen] = useState(false)

  // Debounce timer ref (prevents re-renders)
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Track if initial load from URL params is done
  const initialLoadDone = useRef(false)

  /**
   * Persist view mode to localStorage
   */
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('services-view-mode', viewMode)
    }
  }, [viewMode])

  /**
   * Initialize filters from URL query params (once on mount)
   */
  useEffect(() => {
    if (initialLoadDone.current) return
    initialLoadDone.current = true

    const categoryParam = searchParams.get('category')
    const queryParam = searchParams.get('q')
    const ministryParam = searchParams.get('ministry')
    const serviceTypeParam = searchParams.get('service_type')
    const sortParam = searchParams.get('sort')
    const pageParam = searchParams.get('page')

    if (queryParam) {
      setSearchInputValue(queryParam)
      setSearchQuery(queryParam)
    }

    if (ministryParam) {
      setSelectedMinistry(parseInt(ministryParam, 10))
    }

    if (categoryParam) {
      setSelectedCategory(categoryParam)
    }

    if (serviceTypeParam) {
      setSelectedServiceType(serviceTypeParam)
    }

    if (sortParam && ['relevance', 'name_asc', 'name_desc', 'price_asc', 'price_desc'].includes(sortParam)) {
      setSortOption(sortParam as SortOption)
    }

    const priceParam = searchParams.get('price')
    if (priceParam && ['all', 'free', 'formula'].includes(priceParam)) {
      setPriceFilter(priceParam as PriceFilter)
    }

    if (pageParam) {
      const page = parseInt(pageParam, 10)
      if (page > 0) {
        setCurrentPage(page)
      }
    }
  }, [searchParams])

  /**
   * Update URL params
   */
  const updateURLParams = useCallback(() => {
    const params = new URLSearchParams()

    if (searchQuery) params.set('q', searchQuery)
    if (selectedCategory) params.set('category', selectedCategory)
    if (selectedMinistry) params.set('ministry', selectedMinistry.toString())
    if (selectedServiceType) params.set('service_type', selectedServiceType)
    if (sortOption !== 'relevance') params.set('sort', sortOption)
    if (priceFilter !== 'all') params.set('price', priceFilter)
    if (currentPage > 1) params.set('page', currentPage.toString())

    const newUrl = params.toString() ? `/${locale}/services?${params.toString()}` : `/${locale}/services`
    router.replace(newUrl, { scroll: false })
  }, [searchQuery, selectedCategory, selectedMinistry, selectedServiceType, sortOption, priceFilter, currentPage, locale, router])

  /**
   * Perform search
   */
  const performSearch = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Parse sort option into sort_by and sort_order
      let sort_by: 'relevance' | 'name' | 'price' = 'relevance'
      let sort_order: 'asc' | 'desc' = 'asc'

      if (sortOption.startsWith('name_')) {
        sort_by = 'name'
        sort_order = sortOption.endsWith('_asc') ? 'asc' : 'desc'
      } else if (sortOption.startsWith('price_')) {
        sort_by = 'price'
        sort_order = sortOption.endsWith('_asc') ? 'asc' : 'desc'
      }

      // Determine calculation_methods filter based on priceFilter
      // 'formula' = percentage_based + formula_based (services with calculated prices)
      // 'free' = still handled client-side as it checks expedition_price === 0
      const calculationMethodsFilter = priceFilter === 'formula'
        ? ['percentage_based', 'formula_based']
        : undefined

      const filters: SearchFilters = {
        q: searchQuery || undefined,
        category_code: selectedCategory || undefined,
        ministry_id: selectedMinistry || undefined,
        service_type: selectedServiceType || undefined,
        calculation_methods: calculationMethodsFilter,
        sort_by,
        sort_order,
        page: currentPage,
        limit: ITEMS_PER_PAGE,
        include_facets: true,
        language: locale
      }

      const results = await searchServices(filters)
      setSearchResults(results)

      // Update URL params
      updateURLParams()

    } catch (err) {
      console.error('Search failed:', err)
      const errorMessage = err instanceof Error ? err.message : 'Failed to search services'
      setError(errorMessage)
      setSearchResults(getDefaultSearchResponse())
    } finally {
      setLoading(false)
    }
  }, [searchQuery, selectedCategory, selectedMinistry, selectedServiceType, sortOption, priceFilter, currentPage, locale, updateURLParams])

  /**
   * Trigger search when filters change
   */
  useEffect(() => {
    performSearch()
  }, [performSearch])

  /**
   * Handle search input change with debounce
   * Uses separate state for input value to prevent lag
   */
  const handleSearchInputChange = (value: string) => {
    // Update input value immediately (no lag)
    setSearchInputValue(value)

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    // Set new debounced search
    debounceTimerRef.current = setTimeout(() => {
      setSearchQuery(value)
      setCurrentPage(1)
    }, 400)
  }

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

  const clearAllFilters = () => {
    setSearchInputValue('')
    setSearchQuery('')
    setSelectedMinistry(null)
    setSelectedCategory(null)
    setSelectedServiceType(null)
    setSortOption('relevance')
    setPriceFilter('all')
    setCurrentPage(1)
  }

  const handleServiceClick = (service: ServiceResult) => {
    router.push(`/${locale}/services/${service.id}`)
  }

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleNextPage = () => {
    if (searchResults && currentPage < searchResults.total_pages) {
      setCurrentPage(currentPage + 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handlePageClick = (page: number) => {
    setCurrentPage(page)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const getPageNumbers = () => {
    if (!searchResults) return []
    const totalPages = searchResults.total_pages
    const pages: (number | string)[] = []

    if (totalPages <= 7) {
      // Show all pages if 7 or fewer
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Always show first page
      pages.push(1)

      if (currentPage > 3) {
        pages.push('...')
      }

      // Show pages around current page
      const start = Math.max(2, currentPage - 1)
      const end = Math.min(totalPages - 1, currentPage + 1)

      for (let i = start; i <= end; i++) {
        pages.push(i)
      }

      if (currentPage < totalPages - 2) {
        pages.push('...')
      }

      // Always show last page
      pages.push(totalPages)
    }

    return pages
  }

  const activeFiltersCount = [
    selectedCategory,
    selectedMinistry,
    selectedServiceType,
    priceFilter !== 'all' ? priceFilter : null
  ].filter(Boolean).length

  // Filtered categories based on selected ministry (cascade filter)
  // Note: The API returns facets based on current filters, so categories
  // are already filtered by the backend when a ministry is selected
  const filteredCategories = useMemo(() => {
    return searchResults?.facets?.categories || []
  }, [searchResults?.facets?.categories])

  // Get translations for service types from serviceTypes namespace
  const tServiceTypes = useTranslations('serviceTypes')

  // Build service type options with translated labels
  const serviceTypeOptions = useMemo(() => {
    return SERVICE_TYPES_LIST.map(st => ({
      type: st.type,
      label: tServiceTypes(`${st.key}.name`)
    }))
  }, [tServiceTypes])

  // Apply client-side filtering only for 'free' filter
  // Note: 'formula' filter is now handled server-side via calculation_methods parameter
  const displayResults = useMemo(() => {
    if (!searchResults?.results) return []

    if (priceFilter === 'free') {
      // Show services with expedition_price === 0 (truly free services)
      // This is still client-side as free services can have any calculation_method
      return searchResults.results.filter(service =>
        service.expedition_price === 0
      )
    }

    // For 'all' and 'formula' (already filtered server-side), return as-is
    return searchResults.results
  }, [searchResults?.results, priceFilter])

  return (
    <div className="bg-background">
      <div className="container mx-auto px-4 py-8">
        <Breadcrumb
          items={[{ label: t('title') }]}
          className="mb-6"
        />

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-4xl font-bold mb-2">{t('title')}</h1>
            <p className="text-muted-foreground">
              {loading
                ? t('loading')
                : t('resultsFound', { count: searchResults?.total_results || 0 })
              }
            </p>
          </div>

          {!loading && searchResults && searchResults.results.length > 0 && (
            <div className="flex items-center gap-2 bg-muted p-1 rounded-lg" role="group" aria-label="View mode">
              <Button
                variant={viewMode === 'grid' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('grid')}
                className="gap-2"
                aria-pressed={viewMode === 'grid'}
                aria-label="Grid view"
              >
                <LayoutGrid className="h-4 w-4" />
                <span className="hidden sm:inline">{t('viewGrid')}</span>
              </Button>
              <Button
                variant={viewMode === 'list' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('list')}
                className="gap-2"
                aria-pressed={viewMode === 'list'}
                aria-label="List view"
              >
                <List className="h-4 w-4" />
                <span className="hidden sm:inline">{t('viewList')}</span>
              </Button>
            </div>
          )}
        </div>

        {/* Search Bar + Filters */}
        <div className="mb-6 space-y-2">
          <div className="flex items-center gap-2">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <Input
                type="text"
                placeholder={t('searchPlaceholder')}
                value={searchInputValue}
                onChange={(e) => handleSearchInputChange(e.target.value)}
                className="pl-9 pr-8 h-9 text-sm"
                aria-label={t('searchPlaceholder')}
              />
              {searchInputValue && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="absolute right-1 top-1/2 transform -translate-y-1/2 h-6 w-6 p-0"
                  onClick={() => { setSearchInputValue(''); setSearchQuery(''); setCurrentPage(1) }}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>

            {/* Mobile filter toggle */}
            <Button
              variant="outline"
              size="sm"
              className="md:hidden h-9 gap-1.5"
              onClick={() => setFiltersOpen(!filtersOpen)}
              aria-expanded={filtersOpen}
            >
              <SlidersHorizontal className="h-4 w-4" />
              <span>{t('filters') || 'Filtros'}</span>
              {(selectedMinistry || selectedCategory || selectedServiceType || priceFilter !== 'all') && (
                <Badge variant="secondary" className="h-5 w-5 p-0 flex items-center justify-center text-xs">
                  {[selectedMinistry, selectedCategory, selectedServiceType, priceFilter !== 'all' ? 1 : null].filter(Boolean).length}
                </Badge>
              )}
            </Button>
          </div>

          {/* Filters row: always visible on md+, collapsible on mobile */}
          <div className={`flex flex-wrap items-center gap-2 ${filtersOpen ? '' : 'hidden md:flex'}`}>

            {/* Ministry Filter */}
            <Select
              value={selectedMinistry?.toString() || "all"}
              onValueChange={(value) => {
                const newMinistry = value === "all" ? null : parseInt(value, 10)
                setSelectedMinistry(newMinistry)
                setSelectedCategory(null)
                setSelectedServiceType(null)
                setCurrentPage(1)
              }}
            >
              <SelectTrigger className="w-[160px] h-9 text-sm">
                <SelectValue placeholder={t('ministry')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allMinistries')}</SelectItem>
                {searchResults?.facets?.ministries?.map((ministry: FacetItem) => (
                  <SelectItem key={ministry.id ?? ministry.name} value={ministry.id?.toString() || ministry.name || ''}>
                    {ministry.name} ({ministry.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Category Filter */}
            <Select
              value={selectedCategory || "all"}
              onValueChange={(value) => {
                const newCategory = value === "all" ? null : value
                setSelectedCategory(newCategory)
                setSelectedServiceType(null)
                setCurrentPage(1)
              }}
            >
              <SelectTrigger className="w-[160px] h-9 text-sm">
                <SelectValue placeholder={t('category')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allCategories')}</SelectItem>
                {filteredCategories.map((category) => (
                  <SelectItem key={category.code} value={category.code || ''}>
                    {category.name} ({category.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Service Type Filter */}
            <Select
              value={selectedServiceType || "all"}
              onValueChange={(value) => {
                setSelectedServiceType(value === "all" ? null : value)
                setCurrentPage(1)
              }}
            >
              <SelectTrigger className="w-[180px] h-9 text-sm">
                <SelectValue placeholder={t('serviceType')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allServiceTypes')}</SelectItem>
                {serviceTypeOptions.map((option) => (
                  <SelectItem key={option.type} value={option.type}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Price Type Filter */}
            <Select
              value={priceFilter}
              onValueChange={(value) => {
                setPriceFilter(value as PriceFilter)
                setCurrentPage(1)
              }}
            >
              <SelectTrigger className="w-[130px] h-9 text-sm">
                <SelectValue placeholder={t('priceType')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allPrices')}</SelectItem>
                <SelectItem value="free">{t('freeServices')}</SelectItem>
                <SelectItem value="formula">{t('formulaServices')}</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort Dropdown */}
            <Select value={sortOption} onValueChange={(value) => { setSortOption(value as SortOption); setCurrentPage(1) }}>
              <SelectTrigger className="w-[140px] h-9 text-sm">
                <SelectValue placeholder={t('sortBy')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="relevance">{t('sortRelevance')}</SelectItem>
                <SelectItem value="name_asc">{t('sortNameAsc')}</SelectItem>
                <SelectItem value="name_desc">{t('sortNameDesc')}</SelectItem>
                <SelectItem value="price_asc">{t('sortPriceAsc')}</SelectItem>
                <SelectItem value="price_desc">{t('sortPriceDesc')}</SelectItem>
              </SelectContent>
            </Select>

            {/* Clear Filters Button (only when filters active) */}
            {activeFiltersCount > 0 && (
              <Button variant="ghost" size="sm" onClick={clearAllFilters} className="h-9 text-xs text-muted-foreground">
                <X className="h-3 w-3 mr-1" />
                {t('clearFilters')}
              </Button>
            )}
          </div>

          {/* Active Filters Badges Row */}
          {activeFiltersCount > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {selectedMinistry && (
                <Badge variant="secondary" className="pl-3 pr-1 py-1 text-xs gap-1 flex items-center">
                  {searchResults?.facets?.ministries?.find((m: FacetItem) => m.id === selectedMinistry)?.name || t('ministry')}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-4 w-4 p-0 ml-1 hover:bg-destructive/20 rounded-full"
                    onClick={() => { setSelectedMinistry(null); setSelectedCategory(null); setSelectedServiceType(null); setCurrentPage(1) }}
                  >
                    <X className="h-2.5 w-2.5" />
                  </Button>
                </Badge>
              )}
              {selectedCategory && (
                <Badge variant="secondary" className="pl-3 pr-1 py-1 text-xs gap-1 flex items-center">
                  {filteredCategories.find((c) => c.code === selectedCategory)?.name || t('category')}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-4 w-4 p-0 ml-1 hover:bg-destructive/20 rounded-full"
                    onClick={() => { setSelectedCategory(null); setSelectedServiceType(null); setCurrentPage(1) }}
                  >
                    <X className="h-2.5 w-2.5" />
                  </Button>
                </Badge>
              )}
              {selectedServiceType && (
                <Badge variant="secondary" className="pl-3 pr-1 py-1 text-xs gap-1 flex items-center">
                  {serviceTypeOptions.find(o => o.type === selectedServiceType)?.label || selectedServiceType}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-4 w-4 p-0 ml-1 hover:bg-destructive/20 rounded-full"
                    onClick={() => { setSelectedServiceType(null); setCurrentPage(1) }}
                  >
                    <X className="h-2.5 w-2.5" />
                  </Button>
                </Badge>
              )}
              {priceFilter !== 'all' && (
                <Badge variant="secondary" className="pl-3 pr-1 py-1 text-xs gap-1 flex items-center">
                  {priceFilter === 'free' ? t('freeServices') : t('formulaServices')}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-4 w-4 p-0 ml-1 hover:bg-destructive/20 rounded-full"
                    onClick={() => { setPriceFilter('all'); setCurrentPage(1) }}
                  >
                    <X className="h-2.5 w-2.5" />
                  </Button>
                </Badge>
              )}
            </div>
          )}
        </div>

        {/* Results area */}
        <div>
          {error && !loading && (
            <Alert variant="destructive" className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="p-4 space-y-3 animate-pulse">
                  <div className="h-4 bg-muted rounded w-3/4" />
                  <div className="h-3 bg-muted rounded w-1/2" />
                  <div className="space-y-2">
                    <div className="h-3 bg-muted rounded w-full" />
                    <div className="h-3 bg-muted rounded w-5/6" />
                  </div>
                  <div className="flex justify-between pt-2">
                    <div className="h-6 bg-muted rounded w-20" />
                    <div className="h-6 bg-muted rounded w-16" />
                  </div>
                </Card>
              ))}
            </div>
          )}

          {!loading && searchResults && searchResults.total_results === 0 && (
            <Card className="p-12 text-center">
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">{t('noResults')}</h3>
              <p className="text-muted-foreground mb-4">{t('tryDifferentFilters')}</p>
              {searchResults.suggestions && searchResults.suggestions.length > 0 && (
                <div className="mt-6">
                  <p className="text-sm text-muted-foreground mb-3">{t('suggestions')}:</p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {searchResults.suggestions.map((suggestion, idx) => (
                      <Button key={idx} variant="outline" size="sm" onClick={() => { setSearchInputValue(suggestion); setSearchQuery(suggestion); setCurrentPage(1) }}>
                        {suggestion}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )}

          {/* Bundle Results (commercial license packages matching the search) */}
          {!loading && searchResults && searchResults.bundles && searchResults.bundles.length > 0 && (
            <div className="mb-6">
              <p className="text-sm font-medium text-muted-foreground mb-2">
                {t('bundlesFound', { count: searchResults.bundles.length, defaultValue: `${searchResults.bundles.length} paquete(s) comercial(es)` })}
              </p>
              <div className="flex flex-wrap gap-3">
                {searchResults.bundles.map((bundle) => (
                  <Card
                    key={bundle.id}
                    className="group hover:shadow-md transition-all cursor-pointer border-primary/20 bg-primary/5 flex-1 min-w-[250px] max-w-[400px]"
                    onClick={() => router.push(`/${locale}/licencias-comerciales?bundle=${bundle.bundle_code}`)}
                  >
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="secondary" className="text-xs">{t('bundle', { defaultValue: 'Paquete' })}</Badge>
                        <span className="text-xs text-muted-foreground">{bundle.item_count} {t('servicesIncluded', { defaultValue: 'servicios' })}</span>
                      </div>
                      <h3 className="font-semibold text-sm group-hover:text-primary transition-colors">{bundle.name}</h3>
                      {bundle.description && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{bundle.description}</p>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Grid View */}
          {!loading && searchResults && displayResults.length > 0 && viewMode === 'grid' && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
              {displayResults.map((service) => {
                const shouldShowCalculateButton = service.expedition_price === 0 && service.renewal_price === 0

                return (
                  <Card
                    key={service.id}
                    className="group hover:shadow-lg transition-all duration-300 flex flex-col"
                  >
                    <div className="p-6 space-y-4 flex-1 flex flex-col">
                      <div className="flex-1">
                        <h3 className="font-semibold text-base mb-2 group-hover:text-primary transition-colors line-clamp-2">
                          {service.name}
                        </h3>
                        <Badge variant="secondary" className="text-[10px]">{service.category_name}</Badge>
                        {service.ministry_name && (
                          <p className="text-xs text-muted-foreground mt-1">{service.ministry_name}</p>
                        )}
                      </div>

                      <div className="mt-auto pt-4 border-t space-y-3">
                        {!shouldShowCalculateButton ? (
                          <div className="flex items-center gap-4 min-h-[48px]">
                            <div>
                              <p className="text-xs text-muted-foreground">{t('firstExpedition')}</p>
                              <p className="font-semibold text-base text-primary">{formatPrice(service.expedition_price, freeLabel, locale)}</p>
                            </div>
                            {service.renewal_price > 0 && (
                              <>
                                <span className="text-muted-foreground">|</span>
                                <div>
                                  <p className="text-xs text-muted-foreground">{t('renewalPrice')}</p>
                                  <p className="font-semibold text-base text-primary">{formatPrice(service.renewal_price, freeLabel, locale)}</p>
                                </div>
                              </>
                            )}
                          </div>
                        ) : (
                          <div className="min-h-[48px] flex items-center">
                            <Button
                              variant="outline"
                              className="w-full gap-2"
                              onClick={(e) => {
                                e.stopPropagation()
                                router.push(`/${locale}/calculateur?service_id=${service.id}`)
                              }}
                            >
                              <Calculator className="h-4 w-4" />
                              {t('calculate')}
                            </Button>
                          </div>
                        )}

                        <Button
                          variant="default"
                          className="w-full"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleServiceClick(service)
                          }}
                        >
                          {t('viewDetails')}
                        </Button>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}

          {/* List View */}
          {!loading && searchResults && displayResults.length > 0 && viewMode === 'list' && (
            <div className="space-y-4 mb-8">
              {displayResults.map((service) => {
                const shouldShowCalculateButton = service.expedition_price === 0 && service.renewal_price === 0

                return (
                  <Card
                    key={service.id}
                    className="group hover:shadow-md transition-all duration-300"
                  >
                    <div className="p-6">
                      <div className="flex flex-col lg:flex-row gap-6">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-lg mb-2 group-hover:text-primary transition-colors">
                            {service.name}
                          </h3>
                          <div className="mb-3">
                            <Badge variant="secondary" className="text-[10px]">{service.category_name}</Badge>
                            {service.ministry_name && (
                              <p className="text-xs text-muted-foreground mt-1">{service.ministry_name}</p>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-col justify-between gap-3 lg:min-w-[220px] pt-4 lg:pt-0 border-t lg:border-t-0 lg:border-l lg:pl-6">
                          {!shouldShowCalculateButton ? (
                            <div className="flex items-center gap-4 min-h-[48px]">
                              <div>
                                <p className="text-xs text-muted-foreground">{t('firstExpedition')}</p>
                                <p className="font-semibold text-base text-primary">{formatPrice(service.expedition_price, freeLabel, locale)}</p>
                              </div>
                              {service.renewal_price > 0 && (
                                <>
                                  <span className="text-muted-foreground">|</span>
                                  <div>
                                    <p className="text-xs text-muted-foreground">{t('renewalPrice')}</p>
                                    <p className="font-semibold text-base text-primary">{formatPrice(service.renewal_price, freeLabel, locale)}</p>
                                  </div>
                                </>
                              )}
                            </div>
                          ) : (
                            <div className="min-h-[48px] flex items-center">
                              <Button
                                variant="outline"
                                className="gap-2"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  router.push(`/${locale}/calculateur?service_id=${service.id}`)
                                }}
                              >
                                <Calculator className="h-4 w-4" />
                                {t('calculate')}
                              </Button>
                            </div>
                          )}

                          <Button
                            variant="default"
                            className="w-full"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleServiceClick(service)
                            }}
                          >
                            {t('viewDetails')}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}

          {/* Pagination */}
          {!loading && searchResults && displayResults.length > 0 && searchResults.total_pages > 1 && (
            <div className="flex flex-col items-center gap-4 mb-4">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePreviousPage}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  <span className="hidden sm:inline ml-1">{tCommon('previous')}</span>
                </Button>

                <div className="flex items-center gap-1">
                  {getPageNumbers().map((page, idx) => (
                    typeof page === 'number' ? (
                      <Button
                        key={idx}
                        variant={currentPage === page ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handlePageClick(page)}
                        className="min-w-[40px]"
                      >
                        {page}
                      </Button>
                    ) : (
                      <span key={idx} className="px-2 text-muted-foreground">
                        {page}
                      </span>
                    )
                  ))}
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNextPage}
                  disabled={currentPage === searchResults.total_pages}
                >
                  <span className="hidden sm:inline mr-1">{tCommon('next')}</span>
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>

              <span className="text-sm text-muted-foreground">
                {tCommon('pageOf', { current: currentPage, total: searchResults.total_pages })}
              </span>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}

/**
 * Services Page - Wrapper with Suspense boundary
 * Note: Header and Footer are provided by the (public) layout
 */
export default function ServicesPage() {
  return (
    <Suspense fallback={
      <div className="bg-background">
        <div className="container mx-auto px-4 py-8">
          <div className="flex justify-center items-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        </div>
      </div>
    }>
      <ServicesContent />
    </Suspense>
  )
}
