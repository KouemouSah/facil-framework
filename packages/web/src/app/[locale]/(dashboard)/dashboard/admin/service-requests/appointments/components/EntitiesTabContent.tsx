'use client'

/**
 * Entities Tab Content
 *
 * Displays entity locations from the entity_locations table as the primary source.
 * Enriches with slot statistics from appointment_slot_configs.
 */

import { useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter, useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Building,
  MapPin,
  Plus,
  Loader2,
  AlertCircle,
  CalendarClock,
  Globe,
  Phone,
  Mail,
  Edit,
  ExternalLink,
} from 'lucide-react'
import { useSlotConfigs } from '@/modules/service-requests-admin'
import { useEntityLocations } from '@/modules/entity-locations'
import { useEntitiesSimple } from '@/modules/cities'

interface LocationWithStats {
  id: string
  entity_code: string
  entity_name: string
  city: string
  region: string
  location_name: string
  location_address: string | null
  phone: string | null
  email: string | null
  is_main_office: boolean
  is_active: boolean
  slotCount: number
  activeSlotCount: number
}

export default function EntitiesTabContent() {
  const t = useTranslations('admin.serviceRequests.appointments.entities')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string

  // Fetch entity locations as primary source
  const {
    data: locationsData,
    isLoading: locationsLoading,
    error: locationsError,
    refetch: refetchLocations,
  } = useEntityLocations({ page_size: 100 })

  // Fetch slot configs for slot statistics
  const { data: slotConfigs, isLoading: slotsLoading } = useSlotConfigs()

  // Fetch entities for name resolution
  const { data: entities } = useEntitiesSimple(true)

  const isLoading = locationsLoading || slotsLoading

  // Build entity code -> name map
  const entityNameMap = useMemo(() => {
    const map = new Map<string, string>()
    if (entities) {
      for (const entity of entities) {
        map.set(entity.code, entity.name)
      }
    }
    return map
  }, [entities])

  // Build location_id -> slot counts map from slot configs
  const slotCountsMap = useMemo(() => {
    const map = new Map<string, { total: number; active: number }>()
    if (slotConfigs) {
      for (const slot of slotConfigs) {
        if (slot.entity_location_id) {
          const existing = map.get(slot.entity_location_id) || { total: 0, active: 0 }
          existing.total++
          if (slot.is_active) {
            existing.active++
          }
          map.set(slot.entity_location_id, existing)
        }
      }
    }
    return map
  }, [slotConfigs])

  // Combine entity locations with slot statistics
  const locationsWithStats: LocationWithStats[] = useMemo(() => {
    if (!locationsData?.items) return []

    return locationsData.items.map((loc) => {
      const slotStats = slotCountsMap.get(loc.id) || { total: 0, active: 0 }
      return {
        id: loc.id,
        entity_code: loc.entity_code,
        entity_name: entityNameMap.get(loc.entity_code) || loc.entity_code,
        city: loc.city,
        region: loc.region,
        location_name: loc.location_name,
        location_address: loc.location_address,
        phone: loc.phone,
        email: loc.email,
        is_main_office: loc.is_main_office,
        is_active: loc.is_active,
        slotCount: slotStats.total,
        activeSlotCount: slotStats.active,
      }
    }).sort((a, b) => {
      if (a.entity_code !== b.entity_code) {
        return a.entity_code.localeCompare(b.entity_code)
      }
      return a.city.localeCompare(b.city)
    })
  }, [locationsData, slotCountsMap, entityNameMap])

  // Stats
  const uniqueEntities = useMemo(() => {
    return new Set(locationsWithStats.map((e) => e.entity_code)).size
  }, [locationsWithStats])

  const totalActiveSlots = locationsWithStats.reduce((sum, e) => sum + e.activeSlotCount, 0)
  const totalSlots = locationsWithStats.reduce((sum, e) => sum + e.slotCount, 0)
  const locationsWithoutSlots = locationsWithStats.filter((e) => e.slotCount === 0).length

  // Navigate to create new slot with pre-filled location
  const handleCreateSlotForLocation = (locationId: string) => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments/slots/new?location=${locationId}`)
  }

  // Navigate to create new slot
  const handleCreateNew = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments/slots/new`)
  }

  // Navigate to view slots filtered by location
  const handleViewSlots = (locationId: string) => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments?tab=slots&location=${locationId}`)
  }

  // Navigate to entity locations admin page
  const handleManageLocations = () => {
    router.push(`/${locale}/dashboard/admin/entity-locations`)
  }

  // Render loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Render error state
  if (locationsError) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{locationsError instanceof Error ? locationsError.message : 'Error loading data'}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={() => refetchLocations()}>
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
            <CardTitle className="text-sm font-medium">{t('totalEntities')}</CardTitle>
            <Building className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{uniqueEntities}</div>
            <p className="text-xs text-muted-foreground">{t('entitiesWithSlots')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('totalLocations')}</CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{locationsWithStats.length}</div>
            <p className="text-xs text-muted-foreground">
              {locationsWithoutSlots > 0 && (
                <span className="text-amber-600">{locationsWithoutSlots} sin slots</span>
              )}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('totalSlots')}</CardTitle>
            <CalendarClock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {totalActiveSlots}/{totalSlots}
            </div>
            <p className="text-xs text-muted-foreground">{t('activeSlotsTotal')}</p>
          </CardContent>
        </Card>
        <Card className="bg-muted/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Gestión</CardTitle>
            <Edit className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Button size="sm" variant="outline" onClick={handleManageLocations} className="w-full">
              <ExternalLink className="h-3 w-3 mr-1" />
              Administrar Locations
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Entity Locations Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5" />
                {t('title')}
              </CardTitle>
              <CardDescription>{t('subtitle')}</CardDescription>
            </div>
            <Button onClick={handleCreateNew}>
              <Plus className="mr-2 h-4 w-4" />
              {t('createSlot')}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {locationsWithStats.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Building className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium mb-2">{t('noEntities')}</p>
              <p className="text-sm mb-4">{t('noEntitiesDescription')}</p>
              <div className="flex gap-2 justify-center">
                <Button variant="outline" onClick={handleManageLocations}>
                  <MapPin className="mr-2 h-4 w-4" />
                  Crear Location
                </Button>
                <Button onClick={handleCreateNew}>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('createFirstSlot')}
                </Button>
              </div>
            </div>
          ) : (
            <div className="border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('entityCode')}</TableHead>
                    <TableHead>{t('city')}</TableHead>
                    <TableHead>{t('region')}</TableHead>
                    <TableHead>{t('location')}</TableHead>
                    <TableHead>Contacto</TableHead>
                    <TableHead className="text-center">{t('slots')}</TableHead>
                    <TableHead className="text-center">Estado</TableHead>
                    <TableHead className="text-right">{t('actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {locationsWithStats.map((location) => (
                    <TableRow key={location.id} className={!location.is_active ? 'opacity-50' : ''}>
                      <TableCell>
                        <div>
                          <div className="font-medium">{location.entity_code}</div>
                          <div className="text-xs text-muted-foreground max-w-[180px] truncate">
                            {location.entity_name}
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
                        <Badge variant="secondary">{location.region}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-[180px]">
                          <div className="font-medium truncate flex items-center gap-1">
                            {location.location_name}
                            {location.is_main_office && (
                              <Badge variant="default" className="text-[10px] px-1 py-0">
                                Principal
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
                        <div className="text-xs space-y-0.5">
                          {location.phone && (
                            <div className="flex items-center gap-1 text-muted-foreground">
                              <Phone className="h-3 w-3" />
                              {location.phone}
                            </div>
                          )}
                          {location.email && (
                            <div className="flex items-center gap-1 text-muted-foreground">
                              <Mail className="h-3 w-3" />
                              {location.email}
                            </div>
                          )}
                          {!location.phone && !location.email && (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <div className="flex flex-col items-center">
                          {location.slotCount === 0 ? (
                            <span className="text-amber-600 font-medium">Sin slots</span>
                          ) : (
                            <>
                              <span className="font-medium">{location.activeSlotCount}</span>
                              <span className="text-xs text-muted-foreground">
                                / {location.slotCount} {t('total')}
                              </span>
                            </>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge
                          variant="outline"
                          className={
                            location.is_active
                              ? 'bg-green-100 text-green-700 border-green-300'
                              : 'bg-gray-100 text-gray-500 border-gray-300'
                          }
                        >
                          {location.is_active ? 'Activo' : 'Inactivo'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          {location.slotCount > 0 && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleViewSlots(location.id)}
                            >
                              {t('viewSlots')}
                            </Button>
                          )}
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() => handleCreateSlotForLocation(location.id)}
                          >
                            <Plus className="mr-1 h-3 w-3" />
                            {t('addSlot')}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertCircle className="h-4 w-4" />
            {t('aboutEntities')}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>{t('entityInfo1')}</p>
          <p>{t('entityInfo2')}</p>
          <p className="text-xs">
            <strong>Nota:</strong> Las locations se gestionan desde la página{' '}
            <Button variant="link" className="p-0 h-auto text-xs" onClick={handleManageLocations}>
              Administrar Entity Locations
            </Button>
            . Los slots de citas se asignan a cada location.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
