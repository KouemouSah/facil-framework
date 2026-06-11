'use client'

import { useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  BarChart3,
  MapPin,
  Calendar,
  Users,
  Clock,
  Building2,
  TrendingUp,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import {
  useSlotConfigs,
  useBlockedDates,
  useDelayRules,
} from '@/modules/service-requests-admin'
import type { AppointmentSlotConfig } from '@/modules/service-requests-admin'
import { DAY_OF_WEEK_LABELS } from '@/modules/service-requests-admin'
import { DEFAULT_CITIES, DEFAULT_CITY_REGION_MAP, DEFAULT_ENTITY_INFO } from '@/modules/entity-locations'
import { useEntityLocations } from '@/modules/entity-locations'

interface CityStats {
  city: string
  region: string
  totalSlots: number
  activeSlots: number
  inactiveSlots: number
  totalCapacity: number
  entitiesCovered: string[]
  daysWithSlots: number[]
  locationsCount: number
}

interface EntityStats {
  entityCode: string
  label: string
  slotsByCity: Record<string, number>
  totalSlots: number
  totalCapacity: number
  locationsCount: number
}

export default function StatsTabContent() {
  const t = useTranslations('admin.serviceRequests.appointments')

  // Fetch data from hooks
  const { data: slotConfigs, isLoading: loadingSlots, error: slotsError } = useSlotConfigs()
  const { data: blockedDates, isLoading: loadingBlocked } = useBlockedDates()
  const { data: delayRules, isLoading: loadingDelays } = useDelayRules()
  const { data: locationsData, isLoading: loadingLocations } = useEntityLocations({ is_active: true })

  const isLoading = loadingSlots || loadingBlocked || loadingDelays || loadingLocations

  // Get locations array from paginated response - memoized to prevent re-renders
  const locations = useMemo(() => locationsData?.items ?? [], [locationsData?.items])

  // Calculate statistics by city
  const cityStats = useMemo((): CityStats[] => {
    if (!slotConfigs) return []

    const statsByCity: Record<string, CityStats> = {}

    // Initialize stats for each city using imported DEFAULT_CITIES
    DEFAULT_CITIES.forEach(city => {
      statsByCity[city] = {
        city,
        region: DEFAULT_CITY_REGION_MAP[city],
        totalSlots: 0,
        activeSlots: 0,
        inactiveSlots: 0,
        totalCapacity: 0,
        entitiesCovered: [],
        daysWithSlots: [],
        locationsCount: locations.filter(loc => loc.city === city).length,
      }
    })

    // Process slot configurations
    slotConfigs.forEach((slot: AppointmentSlotConfig) => {
      const city = slot.city || 'Unknown'
      if (!statsByCity[city]) {
        statsByCity[city] = {
          city,
          region: slot.region || 'Unknown',
          totalSlots: 0,
          activeSlots: 0,
          inactiveSlots: 0,
          totalCapacity: 0,
          entitiesCovered: [],
          daysWithSlots: [],
          locationsCount: 0,
        }
      }

      const stats = statsByCity[city]
      stats.totalSlots++

      if (slot.is_active) {
        stats.activeSlots++
        stats.totalCapacity += slot.max_appointments_per_slot
      } else {
        stats.inactiveSlots++
      }

      // Track entities
      if (!stats.entitiesCovered.includes(slot.entity_code)) {
        stats.entitiesCovered.push(slot.entity_code)
      }

      // Track days
      if (!stats.daysWithSlots.includes(slot.day_of_week)) {
        stats.daysWithSlots.push(slot.day_of_week)
      }
    })

    // Return all cities that have either slots or locations
    return Object.values(statsByCity).filter(s =>
      DEFAULT_CITIES.includes(s.city as typeof DEFAULT_CITIES[number]) && (s.totalSlots > 0 || s.locationsCount > 0)
    )
  }, [slotConfigs, locations])

  // Calculate statistics by entity
  const entityStats = useMemo((): EntityStats[] => {
    if (!slotConfigs) return []

    const statsByEntity: Record<string, EntityStats> = {}

    slotConfigs.forEach((slot: AppointmentSlotConfig) => {
      const entityCode = slot.entity_code
      if (!statsByEntity[entityCode]) {
        statsByEntity[entityCode] = {
          entityCode,
          label: DEFAULT_ENTITY_INFO[entityCode as keyof typeof DEFAULT_ENTITY_INFO]?.description || entityCode,
          slotsByCity: {},
          totalSlots: 0,
          totalCapacity: 0,
          locationsCount: locations.filter(loc => loc.entity_code === entityCode).length,
        }
        // Initialize all cities to 0
        DEFAULT_CITIES.forEach(city => {
          statsByEntity[entityCode].slotsByCity[city] = 0
        })
      }

      const stats = statsByEntity[entityCode]
      stats.totalSlots++

      if (slot.is_active) {
        stats.totalCapacity += slot.max_appointments_per_slot
      }

      // Increment city counter
      const city = slot.city as string
      if (city && stats.slotsByCity[city] !== undefined) {
        stats.slotsByCity[city]++
      }
    })

    return Object.values(statsByEntity).sort((a, b) => b.totalSlots - a.totalSlots)
  }, [slotConfigs, locations])

  // Calculate overall totals
  const totals = useMemo(() => {
    const total = {
      slots: slotConfigs?.length || 0,
      activeSlots: slotConfigs?.filter((s: AppointmentSlotConfig) => s.is_active).length || 0,
      blockedDates: blockedDates?.length || 0,
      delayRules: delayRules?.length || 0,
      totalCapacity: slotConfigs?.reduce((sum: number, s: AppointmentSlotConfig) =>
        s.is_active ? sum + s.max_appointments_per_slot : sum, 0) || 0,
      entities: Array.from(new Set(slotConfigs?.map((s: AppointmentSlotConfig) => s.entity_code) || [])).length,
      locations: locations.length,
      citiesWithSlots: Array.from(new Set(slotConfigs?.map((s: AppointmentSlotConfig) => s.city).filter(Boolean) || [])).length,
    }
    return total
  }, [slotConfigs, blockedDates, delayRules, locations])

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (slotsError) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>Error loading statistics</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.totalSlots')}
            </CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totals.slots}</div>
            <p className="text-xs text-muted-foreground">
              {totals.activeSlots} {t('stats.active')}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.locations')}
            </CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totals.locations}</div>
            <p className="text-xs text-muted-foreground">
              {totals.citiesWithSlots} {t('stats.cities')}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.dailyCapacity')}
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totals.totalCapacity}</div>
            <p className="text-xs text-muted-foreground">
              {t('stats.appointmentsPerDay')}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.blockedDates')}
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totals.blockedDates}</div>
            <p className="text-xs text-muted-foreground">
              {t('stats.datesBlocked')}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {t('stats.entities')}
            </CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totals.entities}</div>
            <p className="text-xs text-muted-foreground">
              {t('stats.entitiesWithSlots')}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* City/Region Comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            {t('stats.byCity')}
          </CardTitle>
          <CardDescription>
            {t('stats.cityDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {cityStats.map((stats) => (
              <Card key={stats.city} className="bg-muted/50">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{stats.city}</CardTitle>
                    <Badge variant="outline">{stats.region}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Slot and location counts */}
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                      <div className="text-xl font-bold">{stats.locationsCount}</div>
                      <div className="text-xs text-muted-foreground">{t('stats.locations')}</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold">{stats.totalSlots}</div>
                      <div className="text-xs text-muted-foreground">{t('stats.slots')}</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-green-600">{stats.activeSlots}</div>
                      <div className="text-xs text-muted-foreground">{t('stats.active')}</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-muted-foreground">{stats.inactiveSlots}</div>
                      <div className="text-xs text-muted-foreground">{t('stats.inactive')}</div>
                    </div>
                  </div>

                  {/* Progress bar for active ratio */}
                  {stats.totalSlots > 0 && (
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{t('stats.activeRatio')}</span>
                        <span>{Math.round((stats.activeSlots / stats.totalSlots) * 100)}%</span>
                      </div>
                      <Progress
                        value={(stats.activeSlots / stats.totalSlots) * 100}
                        className="h-2"
                      />
                    </div>
                  )}

                  {/* Capacity */}
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      {t('stats.capacity')}
                    </span>
                    <span className="font-medium">{stats.totalCapacity} {t('stats.perDay')}</span>
                  </div>

                  {/* Entities */}
                  {stats.entitiesCovered.length > 0 && (
                    <div>
                      <div className="text-sm mb-2">{t('stats.entitiesServed')}</div>
                      <div className="flex flex-wrap gap-1">
                        {stats.entitiesCovered.map(entity => (
                          <Badge key={entity} variant="secondary" className="text-xs">
                            {entity}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Days with slots */}
                  {stats.daysWithSlots.length > 0 && (
                    <div>
                      <div className="text-sm mb-2">{t('stats.operatingDays')}</div>
                      <div className="flex flex-wrap gap-1">
                        {stats.daysWithSlots.sort((a, b) => a - b).map(day => (
                          <Badge key={day} variant="outline" className="text-xs">
                            {DAY_OF_WEEK_LABELS[day]}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Entity Breakdown Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            {t('stats.byEntity')}
          </CardTitle>
          <CardDescription>
            {t('stats.entityDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('stats.entity')}</TableHead>
                  <TableHead className="text-center">{t('stats.locations')}</TableHead>
                  {DEFAULT_CITIES.map(city => (
                    <TableHead key={city} className="text-center">{city}</TableHead>
                  ))}
                  <TableHead className="text-center">{t('stats.total')}</TableHead>
                  <TableHead className="text-center">{t('stats.capacity')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entityStats.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4 + DEFAULT_CITIES.length} className="text-center text-muted-foreground py-8">
                      {t('stats.noData')}
                    </TableCell>
                  </TableRow>
                ) : (
                  entityStats.map((entity) => (
                    <TableRow key={entity.entityCode}>
                      <TableCell>
                        <div>
                          <div className="font-medium">{entity.entityCode}</div>
                          <div className="text-xs text-muted-foreground truncate max-w-[150px]">
                            {entity.label}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="secondary">
                          {entity.locationsCount}
                        </Badge>
                      </TableCell>
                      {DEFAULT_CITIES.map(city => (
                        <TableCell key={city} className="text-center">
                          {entity.slotsByCity[city] > 0 ? (
                            <Badge variant="outline">
                              {entity.slotsByCity[city]}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      ))}
                      <TableCell className="text-center font-medium">
                        {entity.totalSlots}
                      </TableCell>
                      <TableCell className="text-center">
                        {entity.totalCapacity}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Delay Rules Summary */}
      {delayRules && delayRules.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              {t('stats.delayRules')}
            </CardTitle>
            <CardDescription>
              {t('stats.delayDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-4">
              {delayRules.map((rule) => (
                <div
                  key={rule.id}
                  className={`p-4 rounded-lg border ${rule.is_active ? 'bg-muted/50' : 'bg-muted/20 opacity-50'}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <Badge variant={
                      rule.priority === 'URGENT' ? 'destructive' :
                      rule.priority === 'HIGH' ? 'default' :
                      rule.priority === 'NORMAL' ? 'secondary' : 'outline'
                    }>
                      {rule.priority}
                    </Badge>
                    {!rule.is_active && (
                      <Badge variant="outline" className="text-xs">
                        {t('stats.inactive')}
                      </Badge>
                    )}
                  </div>
                  <div className="text-2xl font-bold">{rule.delay_business_days}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('stats.businessDays')}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
