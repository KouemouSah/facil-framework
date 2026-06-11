'use client'

/**
 * LocationFilter — Reusable site/location filter for main-office supervisors.
 *
 * Only renders if the user is_main_office and there are 2+ locations.
 * NEVER renders for AYUNTAMIENTO / CAMARA_COMERCIO (city-scoped entities).
 * Default: supervisor's own location. Dropdown allows switching to other sites.
 *
 * Usage:
 *   const { locationFilter, setLocationFilter } = useLocationFilterState(profile)
 *   <LocationFilter
 *     entityCode={profile.entity_code}
 *     isMainOffice={profile.is_main_office}
 *     value={locationFilter}
 *     onChange={setLocationFilter}
 *   />
 */

// Entities with city-level jurisdiction — NO cross-site visibility
const CITY_SCOPED_ENTITIES = ['AYUNTAMIENTO', 'CAMARA_COMERCIO']

import { useCallback, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslations } from 'next-intl'
import { MapPin } from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import apiClient from '@/core/api/client'

interface EntityLocation {
  id: string
  entity_code: string
  location_name: string
  city: string
  is_main_office: boolean
}

function useEntityLocations(entityCode: string | undefined) {
  return useQuery({
    queryKey: ['entity-locations', entityCode],
    queryFn: async () => {
      if (!entityCode) return []
      try {
        const res = await apiClient.get<EntityLocation[]>(
          `/entity-locations/by-entity/${entityCode}`
        )
        return res.data
      } catch {
        return []
      }
    },
    enabled: !!entityCode,
    staleTime: 5 * 60 * 1000,
  })
}

interface LocationFilterProps {
  entityCode: string | undefined
  isMainOffice: boolean
  value: string // '' = all, UUID = specific location
  onChange: (locationId: string) => void
  className?: string
}

export function LocationFilter({
  entityCode,
  isMainOffice,
  value,
  onChange,
  className,
}: LocationFilterProps) {
  const t = useTranslations('supervisor')

  const { data: locations = [] } = useEntityLocations(entityCode)

  const handleChange = useCallback(
    (val: string) => {
      onChange(val === '_all' ? '' : val)
    },
    [onChange]
  )

  // Never show for city-scoped entities (AYUNTAMIENTO, CAMARA_COMERCIO)
  const isCityScoped = entityCode && CITY_SCOPED_ENTITIES.includes(entityCode)
  if (isCityScoped) return null

  // Only show for main-office supervisors with multiple locations
  if (!isMainOffice || locations.length <= 1) return null

  // Find default location label for placeholder
  const currentLabel =
    value && value !== '_all'
      ? locations.find((l: EntityLocation) => l.id === value)
      : null

  return (
    <div className={`flex items-center gap-2 ${className ?? ''}`}>
      <MapPin className="h-4 w-4 text-muted-foreground" />
      <Select value={value || '_all'} onValueChange={handleChange}>
        <SelectTrigger className="w-[220px]">
          <SelectValue
            placeholder={
              currentLabel
                ? `${currentLabel.location_name} — ${currentLabel.city}`
                : t('allSites', { defaultMessage: 'All sites' })
            }
          />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="_all">
            {t('allSites', { defaultMessage: 'All sites' })}
          </SelectItem>
          {locations.map((loc: EntityLocation) => (
            <SelectItem key={loc.id} value={loc.id}>
              {loc.location_name} — {loc.city}
              {loc.is_main_office ? ' (principal)' : ''}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

/**
 * Hook to manage location filter state with auto-default to supervisor's own site.
 *
 * Usage:
 *   const { locationFilter, setLocationFilter, isReady } = useLocationFilter(agentProfile)
 *   // locationFilter defaults to supervisor's entity_location_id on first load
 *   // supervisor can switch to '' (all) or another site
 */
function useLocationFilterState(profile: {
  entity_location_id?: string | null
  entity_code?: string
  is_main_office?: boolean
} | null | undefined) {
  const [value, setValue] = useState('')
  const [initialized, setInitialized] = useState(false)

  const isCityScoped = profile?.entity_code &&
    CITY_SCOPED_ENTITIES.includes(profile.entity_code)

  useEffect(() => {
    if (!initialized && profile?.entity_location_id) {
      // City-scoped entities: ALWAYS lock to own site
      // Main-office national entities: default to own site (switchable)
      if (isCityScoped || profile?.is_main_office) {
        setValue(profile.entity_location_id)
        setInitialized(true)
      }
    }
  }, [profile, initialized, isCityScoped])

  // City-scoped: setter is a no-op (locked to own site)
  const setLocationFilter = useCallback(
    (v: string) => {
      if (isCityScoped) return // locked
      setValue(v)
    },
    [isCityScoped]
  )

  return { locationFilter: value, setLocationFilter, isReady: initialized }
}

export { useEntityLocations, useLocationFilterState }
export type { EntityLocation }
