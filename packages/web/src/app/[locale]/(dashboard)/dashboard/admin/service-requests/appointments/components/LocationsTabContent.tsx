'use client'

import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter, useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Building,
  MapPin,
  Plus,
  Loader2,
  AlertCircle,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Power,
  Phone,
  Mail,
  ChevronDown,
  ChevronUp,
  Globe,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  useEntityLocations,
  useCreateEntityLocation,
  useUpdateEntityLocation,
  useDeleteEntityLocation,
  useToggleEntityLocationActive,
} from '@/modules/entity-locations/hooks'
import { EntityLocationForm } from '@/modules/entity-locations/components/EntityLocationForm'
import {
  DEFAULT_ENTITY_CODES,
  DEFAULT_CITIES,
  DEFAULT_ENTITY_INFO,
  REGIONS,
  type EntityLocation,
  type EntityLocationCreate,
  type EntityLocationUpdate,
  type Region,
} from '@/modules/entity-locations/types'
import {
  useCitiesSimple,
  useEntitiesSimple,
  useCreateCity,
  useCreateEntity,
} from '@/modules/cities'
import type { CityCreate, EntityCreate } from '@/modules/cities'

export default function LocationsTabContent() {
  const t = useTranslations('admin.serviceRequests.appointments.locations')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string

  // State
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [entityFilter, setEntityFilter] = useState<string>('all')
  const [cityFilter, setCityFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Dialog state
  const [editingLocation, setEditingLocation] = useState<EntityLocation | null>(null)
  const [deletingLocation, setDeletingLocation] = useState<EntityLocation | null>(null)

  // City/Entity management state
  const [citiesOpen, setCitiesOpen] = useState(false)
  const [entitiesOpen, setEntitiesOpen] = useState(false)
  const [newCityName, setNewCityName] = useState('')
  const [newCityRegion, setNewCityRegion] = useState<Region>('Continental')
  const [newCityDescription, setNewCityDescription] = useState('')
  const [newEntityCode, setNewEntityCode] = useState('')
  const [newEntityName, setNewEntityName] = useState('')
  const [newEntityDescription, setNewEntityDescription] = useState('')

  // Infinite scroll ref
  const tableContainerRef = useRef<HTMLDivElement>(null)
  const [allLoadedItems, setAllLoadedItems] = useState<EntityLocation[]>([])

  // Fetch cities and entities from API
  const { data: apiCities, isLoading: citiesLoading } = useCitiesSimple(true)
  const { data: apiEntities, isLoading: entitiesLoading } = useEntitiesSimple(true)

  // Mutations for cities and entities
  const createCityMutation = useCreateCity()
  const createEntityMutation = useCreateEntity()

  // Build query params
  const queryParams = useMemo(
    () => ({
      entity_code: entityFilter !== 'all' ? entityFilter : undefined,
      city: cityFilter !== 'all' ? cityFilter : undefined,
      is_active: statusFilter === 'all' ? undefined : statusFilter === 'active',
      page,
      page_size: pageSize,
    }),
    [entityFilter, cityFilter, statusFilter, page, pageSize]
  )

  // Queries
  const { data, isLoading, error, refetch } = useEntityLocations(queryParams)

  // Mutations
  const _createMutation = useCreateEntityLocation() // For future use in inline creation
  const updateMutation = useUpdateEntityLocation()
  const deleteMutation = useDeleteEntityLocation()
  const toggleActiveMutation = useToggleEntityLocationActive()

  // Filtered locations (client-side search on all loaded items)
  const filteredLocations = useMemo(() => {
    const items = allLoadedItems.length > 0 ? allLoadedItems : (data?.items || [])
    if (!searchQuery) return items

    const query = searchQuery.toLowerCase()
    return items.filter(
      (loc) =>
        loc.location_name.toLowerCase().includes(query) ||
        loc.location_address?.toLowerCase().includes(query) ||
        loc.entity_code.toLowerCase().includes(query) ||
        loc.city.toLowerCase().includes(query)
    )
  }, [allLoadedItems, data?.items, searchQuery])

  // Find index of current editing location
  const currentEditIndex = useMemo(() => {
    if (!editingLocation || !filteredLocations.length) return -1
    return filteredLocations.findIndex((loc) => loc.id === editingLocation.id)
  }, [editingLocation, filteredLocations])

  // Handlers
  const handleUpdate = async (formData: EntityLocationCreate) => {
    if (!editingLocation) return
    const updateData: EntityLocationUpdate = {
      location_name: formData.location_name,
      location_address: formData.location_address,
      phone: formData.phone,
      email: formData.email,
      is_main_office: formData.is_main_office,
      is_active: formData.is_active,
      notes: formData.notes,
    }
    await updateMutation.mutateAsync({ id: editingLocation.id, data: updateData })
    setEditingLocation(null)
  }

  const handleDelete = async () => {
    if (!deletingLocation) return
    await deleteMutation.mutateAsync(deletingLocation.id)
    setDeletingLocation(null)
  }

  const handleToggleActive = async (location: EntityLocation) => {
    await toggleActiveMutation.mutateAsync(location.id)
  }

  const handlePreviousLocation = () => {
    if (currentEditIndex > 0) {
      setEditingLocation(filteredLocations[currentEditIndex - 1])
    }
  }

  const handleNextLocation = () => {
    if (currentEditIndex < filteredLocations.length - 1) {
      setEditingLocation(filteredLocations[currentEditIndex + 1])
    }
  }

  // City/Entity creation handlers
  const handleCreateCity = async () => {
    if (!newCityName.trim()) {
      toast.error(t('cityNameRequired'))
      return
    }
    try {
      const cityData: CityCreate = {
        name: newCityName.trim(),
        region: newCityRegion,
        description: newCityDescription.trim() || undefined,
        is_capital: false,
        is_active: true,
      }
      await createCityMutation.mutateAsync(cityData)
      toast.success(t('cityCreated'))
      setNewCityName('')
      setNewCityDescription('')
    } catch (error) {
      toast.error(t('cityCreateError'))
      console.error('Failed to create city:', error)
    }
  }

  const handleCreateEntity = async () => {
    if (!newEntityCode.trim() || !newEntityName.trim()) {
      toast.error(t('entityFieldsRequired'))
      return
    }
    try {
      const entityData: EntityCreate = {
        code: newEntityCode.trim().toUpperCase(),
        name: newEntityName.trim(),
        description: newEntityDescription.trim() || undefined,
        is_active: true,
      }
      await createEntityMutation.mutateAsync(entityData)
      toast.success(t('entityCreated'))
      setNewEntityCode('')
      setNewEntityName('')
      setNewEntityDescription('')
    } catch (error) {
      toast.error(t('entityCreateError'))
      console.error('Failed to create entity:', error)
    }
  }

  // Infinite scroll effect
  useEffect(() => {
    if (data?.items) {
      if (page === 1) {
        setAllLoadedItems(data.items)
      } else {
        setAllLoadedItems(prev => [...prev, ...data.items])
      }
    }
  }, [data?.items, page])

  // Scroll handler for infinite scroll
  const handleScroll = useCallback(() => {
    if (!tableContainerRef.current || isLoading) return
    const { scrollTop, scrollHeight, clientHeight } = tableContainerRef.current
    // Load more when scrolled to 80% of the container
    if (scrollTop + clientHeight >= scrollHeight * 0.8) {
      if (data && page < data.total_pages) {
        setPage(prev => prev + 1)
      }
    }
  }, [data, page, isLoading])

  // Attach scroll listener
  useEffect(() => {
    const container = tableContainerRef.current
    if (container) {
      container.addEventListener('scroll', handleScroll)
      return () => container.removeEventListener('scroll', handleScroll)
    }
  }, [handleScroll])

  // Reset pagination when filters change
  useEffect(() => {
    setPage(1)
    setAllLoadedItems([])
  }, [entityFilter, cityFilter, statusFilter])

  // Merged cities list (API + defaults as fallback)
  const cityOptions = useMemo(() => {
    if (apiCities && apiCities.length > 0) {
      return apiCities.map(c => ({ name: c.name, region: c.region }))
    }
    return DEFAULT_CITIES.map(c => ({ name: c, region: 'Continental' as Region }))
  }, [apiCities])

  // Merged entities list (API + defaults as fallback)
  const entityOptions = useMemo(() => {
    if (apiEntities && apiEntities.length > 0) {
      return apiEntities.map(e => ({ code: e.code, name: e.name }))
    }
    return DEFAULT_ENTITY_CODES.map(code => ({
      code,
      name: DEFAULT_ENTITY_INFO[code]?.description || code,
    }))
  }, [apiEntities])

  // Stats
  const stats = useMemo(() => {
    const items = data?.items || []
    return {
      total: data?.total || 0,
      insular: items.filter((l) => l.region === 'Insular').length,
      continental: items.filter((l) => l.region === 'Continental').length,
      active: items.filter((l) => l.is_active).length,
    }
  }, [data])

  // Render loading
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Render error
  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : 'Error loading data'}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            {tCommon('retry')}
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('totalLocations')}</CardTitle>
            <Building className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              {stats.active} {t('active')}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('insular')}</CardTitle>
            <MapPin className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.insular}</div>
            <p className="text-xs text-muted-foreground">Malabo</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('continental')}</CardTitle>
            <MapPin className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.continental}</div>
            <p className="text-xs text-muted-foreground">Bata, Mongomo...</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('entities')}</CardTitle>
            <Building className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{entityOptions.length}</div>
            <p className="text-xs text-muted-foreground">{t('registeredEntities')}</p>
          </CardContent>
        </Card>
      </div>

      {/* City and Entity Management Sections */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Cities Management */}
        <Collapsible open={citiesOpen} onOpenChange={setCitiesOpen}>
          <Card>
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Globe className="h-5 w-5 text-blue-500" />
                    <div>
                      <CardTitle className="text-base">{t('manageCities')}</CardTitle>
                      <CardDescription className="text-sm">
                        {cityOptions.length} {t('citiesAvailable')}
                      </CardDescription>
                    </div>
                  </div>
                  {citiesOpen ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent className="pt-0 space-y-4">
                {/* Existing cities list */}
                <div className="max-h-[200px] overflow-y-auto border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('cityName')}</TableHead>
                        <TableHead>{t('region')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {citiesLoading ? (
                        <TableRow>
                          <TableCell colSpan={2} className="text-center py-4">
                            <Loader2 className="h-4 w-4 animate-spin mx-auto" />
                          </TableCell>
                        </TableRow>
                      ) : (
                        cityOptions.map((city) => (
                          <TableRow key={city.name}>
                            <TableCell className="font-medium">{city.name}</TableCell>
                            <TableCell>
                              <Badge variant={city.region === 'Insular' ? 'default' : 'secondary'}>
                                {city.region}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>

                {/* Add new city form */}
                <div className="border-t pt-4 space-y-3">
                  <h4 className="font-medium text-sm">{t('addNewCity')}</h4>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="cityName">{t('cityName')} *</Label>
                      <Input
                        id="cityName"
                        placeholder={t('cityNamePlaceholder')}
                        value={newCityName}
                        onChange={(e) => setNewCityName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="cityRegion">{t('region')} *</Label>
                      <Select
                        value={newCityRegion}
                        onValueChange={(v) => setNewCityRegion(v as Region)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {REGIONS.map((region) => (
                            <SelectItem key={region} value={region}>
                              {region}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="cityDescription">{t('description')}</Label>
                    <Input
                      id="cityDescription"
                      placeholder={t('cityDescriptionPlaceholder')}
                      value={newCityDescription}
                      onChange={(e) => setNewCityDescription(e.target.value)}
                    />
                  </div>
                  <Button
                    onClick={handleCreateCity}
                    disabled={createCityMutation.isPending || !newCityName.trim()}
                    size="sm"
                  >
                    {createCityMutation.isPending && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    <Plus className="mr-2 h-4 w-4" />
                    {t('addCity')}
                  </Button>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* Entities Management */}
        <Collapsible open={entitiesOpen} onOpenChange={setEntitiesOpen}>
          <Card>
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Building className="h-5 w-5 text-purple-500" />
                    <div>
                      <CardTitle className="text-base">{t('manageEntities')}</CardTitle>
                      <CardDescription className="text-sm">
                        {entityOptions.length} {t('entitiesAvailable')}
                      </CardDescription>
                    </div>
                  </div>
                  {entitiesOpen ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent className="pt-0 space-y-4">
                {/* Existing entities list */}
                <div className="max-h-[200px] overflow-y-auto border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('entityCode')}</TableHead>
                        <TableHead>{t('entityName')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {entitiesLoading ? (
                        <TableRow>
                          <TableCell colSpan={2} className="text-center py-4">
                            <Loader2 className="h-4 w-4 animate-spin mx-auto" />
                          </TableCell>
                        </TableRow>
                      ) : (
                        entityOptions.map((entity) => (
                          <TableRow key={entity.code}>
                            <TableCell>
                              <Badge variant="outline">{entity.code}</Badge>
                            </TableCell>
                            <TableCell className="text-sm">{entity.name}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>

                {/* Add new entity form */}
                <div className="border-t pt-4 space-y-3">
                  <h4 className="font-medium text-sm">{t('addNewEntity')}</h4>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="entityCode">{t('entityCode')} *</Label>
                      <Input
                        id="entityCode"
                        placeholder={t('entityCodePlaceholder')}
                        value={newEntityCode}
                        onChange={(e) => setNewEntityCode(e.target.value.toUpperCase())}
                        className="uppercase"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="entityName">{t('entityName')} *</Label>
                      <Input
                        id="entityName"
                        placeholder={t('entityNamePlaceholder')}
                        value={newEntityName}
                        onChange={(e) => setNewEntityName(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="entityDescription">{t('description')}</Label>
                    <Input
                      id="entityDescription"
                      placeholder={t('entityDescriptionPlaceholder')}
                      value={newEntityDescription}
                      onChange={(e) => setNewEntityDescription(e.target.value)}
                    />
                  </div>
                  <Button
                    onClick={handleCreateEntity}
                    disabled={createEntityMutation.isPending || !newEntityCode.trim() || !newEntityName.trim()}
                    size="sm"
                  >
                    {createEntityMutation.isPending && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    <Plus className="mr-2 h-4 w-4" />
                    {t('addEntity')}
                  </Button>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      </div>

      {/* Main Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5" />
                {t('title')}
              </CardTitle>
              <CardDescription>{t('subtitle')}</CardDescription>
            </div>
            <Button onClick={() => router.push(`/${locale}/dashboard/admin/service-requests/appointments/locations/new`)}>
              <Plus className="mr-2 h-4 w-4" />
              {t('addLocation')}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-wrap gap-4 mb-6">
            <Select
              value={cityFilter}
              onValueChange={(v) => {
                setCityFilter(v)
                setPage(1)
              }}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder={t('filterCity')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allCities')}</SelectItem>
                {cityOptions.map((city) => (
                  <SelectItem key={city.name} value={city.name}>
                    <div className="flex items-center gap-2">
                      <span>{city.name}</span>
                      <Badge variant="outline" className="text-xs">
                        {city.region}
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={entityFilter}
              onValueChange={(v) => {
                setEntityFilter(v)
                setPage(1)
                setAllLoadedItems([])
              }}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder={t('filterEntity')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allEntities')}</SelectItem>
                {entityOptions.map((entity) => (
                  <SelectItem key={entity.code} value={entity.code}>
                    {entity.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={statusFilter}
              onValueChange={(v) => {
                setStatusFilter(v as 'all' | 'active' | 'inactive')
                setPage(1)
                setAllLoadedItems([])
              }}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder={t('filterStatus')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allStatus')}</SelectItem>
                <SelectItem value="active">{t('activeOnly')}</SelectItem>
                <SelectItem value="inactive">{t('inactiveOnly')}</SelectItem>
              </SelectContent>
            </Select>

            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Table */}
          {filteredLocations.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Building className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium mb-2">{t('noLocations')}</p>
              <p className="text-sm mb-4">{t('noLocationsDescription')}</p>
              <Button onClick={() => router.push(`/${locale}/dashboard/admin/service-requests/appointments/locations/new`)}>
                <Plus className="mr-2 h-4 w-4" />
                {t('createFirstLocation')}
              </Button>
            </div>
          ) : (
            <>
              <div
                ref={tableContainerRef}
                className="border rounded-md max-h-[500px] overflow-y-auto"
              >
                <Table>
                  <TableHeader className="sticky top-0 bg-background z-10">
                    <TableRow>
                      <TableHead>{t('table.entity')}</TableHead>
                      <TableHead>{t('table.city')}</TableHead>
                      <TableHead>{t('table.region')}</TableHead>
                      <TableHead>{t('table.name')}</TableHead>
                      <TableHead>{t('table.contact')}</TableHead>
                      <TableHead>{t('table.status')}</TableHead>
                      <TableHead className="text-right">{t('table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredLocations.map((location) => (
                      <TableRow key={location.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{location.entity_code}</div>
                            <div className="text-xs text-muted-foreground max-w-[150px] truncate">
                              {DEFAULT_ENTITY_INFO[location.entity_code]?.description}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="gap-1">
                            <MapPin className="h-3 w-3" />
                            {location.city}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="secondary"
                            className={
                              location.region === 'Insular'
                                ? 'bg-blue-100 text-blue-700'
                                : 'bg-green-100 text-green-700'
                            }
                          >
                            {location.region}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="max-w-[200px]">
                            <div className="font-medium truncate flex items-center gap-1">
                              {location.location_name}
                              {location.is_main_office && (
                                <Badge variant="default" className="text-xs ml-1">
                                  {t('mainOffice')}
                                </Badge>
                              )}
                            </div>
                            {location.location_address && (
                              <div className="text-xs text-muted-foreground truncate">
                                {location.location_address}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1 text-sm text-muted-foreground">
                            {location.phone && (
                              <span className="flex items-center gap-1">
                                <Phone className="h-3 w-3" />
                                {location.phone}
                              </span>
                            )}
                            {location.email && (
                              <span className="flex items-center gap-1">
                                <Mail className="h-3 w-3" />
                                <span className="truncate max-w-[120px]">{location.email}</span>
                              </span>
                            )}
                            {!location.phone && !location.email && '-'}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={location.is_active ? 'default' : 'secondary'}>
                            {location.is_active ? t('active') : t('inactive')}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => setEditingLocation(location)}>
                                <Pencil className="mr-2 h-4 w-4" />
                                {tCommon('edit')}
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => handleToggleActive(location)}>
                                <Power className="mr-2 h-4 w-4" />
                                {location.is_active ? t('deactivate') : t('activate')}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => setDeletingLocation(location)}
                                className="text-destructive"
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                {tCommon('delete')}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Infinite Scroll Status */}
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  {t('pagination.showing', {
                    from: 1,
                    to: filteredLocations.length,
                    total: data?.total || 0,
                  })}
                </p>
                {data && page < data.total_pages && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    {isLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {t('pagination.loading')}
                      </>
                    ) : (
                      <>
                        <span>{t('pagination.scrollForMore')}</span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPage(prev => prev + 1)}
                        >
                          {t('pagination.loadMore')}
                        </Button>
                      </>
                    )}
                  </div>
                )}
                {data && page >= data.total_pages && filteredLocations.length > 0 && (
                  <p className="text-sm text-muted-foreground">
                    {t('pagination.allLoaded')}
                  </p>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={!!editingLocation} onOpenChange={(open) => !open && setEditingLocation(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('form.editTitle')}</DialogTitle>
            <DialogDescription>{t('form.editDescription')}</DialogDescription>
          </DialogHeader>
          {editingLocation && (
            <EntityLocationForm
              location={editingLocation}
              onSubmit={handleUpdate}
              onCancel={() => setEditingLocation(null)}
              isLoading={updateMutation.isPending}
              onPrevious={handlePreviousLocation}
              onNext={handleNextLocation}
              hasPrevious={currentEditIndex > 0}
              hasNext={currentEditIndex < filteredLocations.length - 1}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deletingLocation} onOpenChange={(open) => !open && setDeletingLocation(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirm.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteConfirm.description', {
                name: deletingLocation?.location_name,
                city: deletingLocation?.city,
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
