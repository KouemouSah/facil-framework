'use client'

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
  ArrowLeft,
  MapPin,
  Building,
  Loader2,
  AlertCircle,
  CalendarClock,
  Users,
  Globe,
} from 'lucide-react'
import { useSlotConfigs } from '@/modules/service-requests-admin'

// City/Region configuration
// In Equatorial Guinea:
// - Malabo (capital) → Insular Region (Bioko Island)
// - Bata → Continental Region (Río Muni)
const CITY_CONFIGS = [
  {
    city: 'Malabo',
    region: 'Insular',
    isCapital: true,
    description: 'Capital city on Bioko Island',
    descriptionEs: 'Capital en la Isla de Bioko',
    descriptionFr: 'Capitale sur l\'île de Bioko',
  },
  {
    city: 'Bata',
    region: 'Continental',
    isCapital: false,
    description: 'Largest city on the mainland',
    descriptionEs: 'Ciudad más grande del continente',
    descriptionFr: 'Plus grande ville du continent',
  },
]

interface CityStats {
  city: string
  region: string
  isCapital: boolean
  description: string
  totalSlots: number
  activeSlots: number
  entitiesCount: number
  entities: string[]
}

export default function LocationsConfigPage() {
  const t = useTranslations('admin.serviceRequests.appointments.locations')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string

  // Fetch all slot configs to calculate stats
  const { data: slotConfigs, isLoading, error, refetch } = useSlotConfigs()

  // Calculate statistics per city
  const cityStats: CityStats[] = useMemo(() => {
    if (!slotConfigs) return []

    return CITY_CONFIGS.map((config) => {
      const citySlots = slotConfigs.filter(
        (slot) => slot.city?.toLowerCase() === config.city.toLowerCase()
      )
      const uniqueEntities = Array.from(new Set(citySlots.map((s) => s.entity_code)))

      // Get description based on locale
      let description = config.description
      if (locale === 'es') description = config.descriptionEs
      else if (locale === 'fr') description = config.descriptionFr

      return {
        city: config.city,
        region: config.region,
        isCapital: config.isCapital,
        description,
        totalSlots: citySlots.length,
        activeSlots: citySlots.filter((s) => s.is_active).length,
        entitiesCount: uniqueEntities.length,
        entities: uniqueEntities,
      }
    })
  }, [slotConfigs, locale])

  // Calculate totals
  const totals = useMemo(() => {
    return {
      totalSlots: cityStats.reduce((sum, city) => sum + city.totalSlots, 0),
      activeSlots: cityStats.reduce((sum, city) => sum + city.activeSlots, 0),
      entitiesCount: Array.from(new Set(slotConfigs?.map((s) => s.entity_code) || [])).length,
    }
  }, [cityStats, slotConfigs])

  // Navigate back
  const handleBack = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments?tab=slots`)
  }

  // Navigate to slots filtered by city
  const handleViewCitySlots = (city: string) => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments?tab=slots&city=${city}`)
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
  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleBack}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
            <p className="text-muted-foreground">{t('subtitle')}</p>
          </div>
        </div>
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
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={handleBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('totalLocations')}</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{cityStats.length}</div>
            <p className="text-xs text-muted-foreground">{t('citiesConfigured')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('totalSlots')}</CardTitle>
            <CalendarClock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {totals.activeSlots}/{totals.totalSlots}
            </div>
            <p className="text-xs text-muted-foreground">{t('activeSlots')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('entitiesWithSlots')}</CardTitle>
            <Building className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totals.entitiesCount}</div>
            <p className="text-xs text-muted-foreground">{t('uniqueEntities')}</p>
          </CardContent>
        </Card>
      </div>

      {/* Cities Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            {t('configuredCities')}
          </CardTitle>
          <CardDescription>{t('citiesDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('city')}</TableHead>
                  <TableHead>{t('region')}</TableHead>
                  <TableHead className="text-center">{t('slots')}</TableHead>
                  <TableHead className="text-center">{t('entities')}</TableHead>
                  <TableHead>{t('entitiesList')}</TableHead>
                  <TableHead className="text-right">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cityStats.map((city) => (
                  <TableRow key={city.city}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <div className="font-medium flex items-center gap-2">
                            {city.city}
                            {city.isCapital && (
                              <Badge variant="secondary" className="text-xs">
                                {t('capital')}
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {city.description}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{city.region}</Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex flex-col items-center">
                        <span className="font-medium">{city.activeSlots}</span>
                        <span className="text-xs text-muted-foreground">
                          / {city.totalSlots} {t('total')}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="secondary">{city.entitiesCount}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {city.entities.length > 0 ? (
                          city.entities.map((entity) => (
                            <Badge key={entity} variant="outline" className="text-xs">
                              {entity}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-muted-foreground text-sm">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleViewCitySlots(city.city)}
                        disabled={city.totalSlots === 0}
                      >
                        <Users className="mr-2 h-4 w-4" />
                        {t('viewSlots')}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertCircle className="h-4 w-4" />
            {t('aboutLocations')}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>{t('locationInfo1')}</p>
          <p>{t('locationInfo2')}</p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li><strong>Malabo</strong> - {t('malaboInfo')}</li>
            <li><strong>Bata</strong> - {t('bataInfo')}</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
