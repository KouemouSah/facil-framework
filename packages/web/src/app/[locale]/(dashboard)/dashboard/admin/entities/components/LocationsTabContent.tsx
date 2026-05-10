'use client'

/**
 * Locations Tab Content
 * CRUD management for entity locations
 * Simplified version without inline city/entity creation (handled in separate tabs)
 */

import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
  RefreshCw,
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
  DEFAULT_ENTITY_INFO,
  type EntityLocation,
  type EntityLocationCreate,
  type EntityLocationUpdate,
} from '@/modules/entity-locations/types'
import {
  useCitiesSimple,
  useEntitiesSimple,
} from '@/modules/cities'

export default function LocationsTabContent() {
  const t = useTranslations('admin.entities.locations')
  const tCommon = useTranslations('common')

  // State
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [entityFilter, setEntityFilter] = useState<string>('all')
  const [cityFilter, setCityFilter] = useState<string>('all')
  const [regionFilter, setRegionFilter] = useState<'all' | 'Insular' | 'Continental'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Dialog state
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [editingLocation, setEditingLocation] = useState<EntityLocation | null>(null)
  const [deletingLocation, setDeletingLocation] = useState<EntityLocation | null>(null)

  // Infinite scroll ref
  const tableContainerRef = useRef<HTMLDivElement>(null)
  const [allLoadedItems, setAllLoadedItems] = useState<EntityLocation[]>([])

  // Fetch cities and entities from API
  const { data: apiCities } = useCitiesSimple(true)
  const { data: apiEntities } = useEntitiesSimple(true)

  // Build query params
  const queryParams = useMemo(
    () => ({
      entity_code: entityFilter !== 'all' ? entityFilter : undefined,
      city: cityFilter !== 'all' ? cityFilter : undefined,
      region: regionFilter !== 'all' ? regionFilter : undefined,
      is_active: statusFilter === 'all' ? undefined : statusFilter === 'active',
      page,
      page_size: pageSize,
    }),
    [entityFilter, cityFilter, regionFilter, statusFilter, page, pageSize]
  )

  // Queries
  const { data, isLoading, error, refetch } = useEntityLocations(queryParams)

  // Mutations
  const createMutation = useCreateEntityLocation()
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
  const handleCreate = async (formData: EntityLocationCreate) => {
    await createMutation.mutateAsync(formData)
    setIsCreateDialogOpen(false)
    toast.success(t('createSuccess'))
  }

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
    toast.success(t('updateSuccess'))
  }

  const handleDelete = async () => {
    if (!deletingLocation) return
    await deleteMutation.mutateAsync(deletingLocation.id)
    setDeletingLocation(null)
    toast.success(t('deleteSuccess'))
  }

  const handleToggleActive = async (location: EntityLocation) => {
    await toggleActiveMutation.mutateAsync(location.id)
    toast.success(location.is_active ? t('deactivated') : t('activated'))
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
  }, [entityFilter, cityFilter, regionFilter, statusFilter])

  // City options from API
  const cityOptions = useMemo(() => {
    if (apiCities && apiCities.length > 0) {
      return apiCities.map(c => ({ name: c.name, region: c.region }))
    }
    return []
  }, [apiCities])

  // Entity options from API
  const entityOptions = useMemo(() => {
    if (apiEntities && apiEntities.length > 0) {
      return apiEntities.map(e => ({ code: e.code, name: e.name }))
    }
    return []
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
  if (isLoading && page === 1) {
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
            {tCommon('retry') || 'Retry'}
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
            <CardTitle className="text-sm font-medium">{t('stats.total')}</CardTitle>
            <Building className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              {stats.active} {t('stats.active')}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('stats.insular')}</CardTitle>
            <MapPin className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.insular}</div>
            <p className="text-xs text-muted-foreground">Malabo</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('stats.continental')}</CardTitle>
            <MapPin className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.continental}</div>
            <p className="text-xs text-muted-foreground">Bata, Mongomo...</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('stats.entities')}</CardTitle>
            <Building className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{entityOptions.length}</div>
            <p className="text-xs text-muted-foreground">{t('stats.registeredEntities')}</p>
          </CardContent>
        </Card>
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
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {tCommon('refresh') || 'Refresh'}
              </Button>
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {t('addLocation')}
              </Button>
            </div>
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
                <SelectValue placeholder={t('filters.city')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('filters.allCities')}</SelectItem>
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
                <SelectValue placeholder={t('filters.entity')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('filters.allEntities')}</SelectItem>
                {entityOptions.map((entity) => (
                  <SelectItem key={entity.code} value={entity.code}>
                    {entity.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={regionFilter}
              onValueChange={(v) => {
                setRegionFilter(v as 'all' | 'Insular' | 'Continental')
                setPage(1)
                setAllLoadedItems([])
              }}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder={t('filters.region')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('filters.allRegions')}</SelectItem>
                <SelectItem value="Insular">Insular</SelectItem>
                <SelectItem value="Continental">Continental</SelectItem>
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
                <SelectValue placeholder={t('filters.status')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('filters.allStatus')}</SelectItem>
                <SelectItem value="active">{t('filters.activeOnly')}</SelectItem>
                <SelectItem value="inactive">{t('filters.inactiveOnly')}</SelectItem>
              </SelectContent>
            </Select>

            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('filters.searchPlaceholder')}
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
              <p className="text-lg font-medium mb-2">{t('empty.title')}</p>
              <p className="text-sm mb-4">{t('empty.description')}</p>
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {t('empty.createFirst')}
              </Button>
            </div>
          ) : (
            <>
              <div
                ref={tableContainerRef}
                className="border rounded-md max-h-[500px] overflow-auto"
              >
                <Table>
                  <TableHeader className="sticky top-0 bg-background z-10">
                    <TableRow>
                      <TableHead>{t('table.entity')}</TableHead>
                      <TableHead>{t('table.city')}</TableHead>
                      <TableHead className="hidden md:table-cell">{t('table.region')}</TableHead>
                      <TableHead>{t('table.name')}</TableHead>
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
                        <TableCell className="hidden md:table-cell">
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
                          <Badge
                            variant="outline"
                            className={
                              location.is_active
                                ? 'bg-green-100 text-green-700'
                                : 'bg-gray-100 text-gray-700'
                            }
                          >
                            {location.is_active ? t('status.active') : t('status.inactive')}
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
                                {tCommon('edit') || 'Edit'}
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => handleToggleActive(location)}>
                                <Power className="mr-2 h-4 w-4" />
                                {location.is_active ? t('actions.deactivate') : t('actions.activate')}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => setDeletingLocation(location)}
                                className="text-destructive"
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                {tCommon('delete') || 'Delete'}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination Info */}
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
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage(prev => prev + 1)}
                      >
                        {t('pagination.loadMore')}
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('form.createTitle')}</DialogTitle>
            <DialogDescription>{t('form.createDescription')}</DialogDescription>
          </DialogHeader>
          <EntityLocationForm
            onSubmit={handleCreate}
            onCancel={() => setIsCreateDialogOpen(false)}
            isLoading={createMutation.isPending}
          />
        </DialogContent>
      </Dialog>

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
            <AlertDialogCancel>{tCommon('cancel') || 'Cancel'}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              {tCommon('delete') || 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
