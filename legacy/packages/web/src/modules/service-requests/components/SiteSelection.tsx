'use client'

/**
 * SiteSelection Component
 * Universal site selection for ALL workflows (including non-appointment).
 *
 * Flow:
 * 1. If 2+ cities → show city filter first
 * 2. Show sites for selected city (or all if single city)
 * 3. User picks a site → saved to session cache
 *
 * For appointment workflows, AppointmentSelection handles site+calendar.
 * This component is for non-appointment workflows only.
 */

import { useState, useEffect, useCallback } from 'react'
import {
  MapPin,
  Building2,
  Loader2,
  AlertCircle,
  CheckCircle,
  ArrowLeft,
  ArrowRight,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

// ============================================================================
// TYPES
// ============================================================================

import type { SiteInfo } from '../types/wizard-session'

interface SiteSelectionProps {
  sessionId: string
  onComplete: () => void
  onBack: () => void
  locale?: 'es' | 'fr' | 'en'

  getAvailableSites: (sessionId: string) => Promise<{
    workflowCode: string
    sites: SiteInfo[]
    cities: Record<string, SiteInfo[]>
    count: number
  }>
  saveSiteSelection: (
    sessionId: string,
    data: {
      entityLocationId: string
      locationName: string
      city: string
      entityCode?: string | null
    },
  ) => Promise<{ success: boolean }>

  /** Pre-selected site (from session cache restore) */
  initialSiteId?: string | null
}

// ============================================================================
// TRANSLATIONS
// ============================================================================

const translations = {
  es: {
    title: 'Seleccione un sitio de tramitacion',
    subtitle: 'Elija la oficina donde desea realizar su tramite',
    cityFilter: 'Seleccione la ciudad',
    selectSite: 'Seleccione la oficina',
    mainOffice: 'Oficina principal',
    loading: 'Cargando sitios disponibles...',
    noSites: 'No hay sitios disponibles para este tramite.',
    error: 'Error al cargar los sitios',
    retry: 'Reintentar',
    back: 'Anterior',
    continue: 'Continuar',
    selected: 'Seleccionado',
    allCities: 'Todas las ciudades',
  },
  fr: {
    title: 'Selectionnez un site de traitement',
    subtitle: 'Choisissez le bureau ou vous souhaitez effectuer votre demarche',
    cityFilter: 'Selectionnez la ville',
    selectSite: 'Selectionnez le bureau',
    mainOffice: 'Bureau principal',
    loading: 'Chargement des sites disponibles...',
    noSites: 'Aucun site disponible pour cette demarche.',
    error: 'Erreur lors du chargement des sites',
    retry: 'Reessayer',
    back: 'Precedent',
    continue: 'Continuer',
    selected: 'Selectionne',
    allCities: 'Toutes les villes',
  },
  en: {
    title: 'Select a processing site',
    subtitle: 'Choose the office where you want to process your request',
    cityFilter: 'Select the city',
    selectSite: 'Select the office',
    mainOffice: 'Main office',
    loading: 'Loading available sites...',
    noSites: 'No sites available for this procedure.',
    error: 'Error loading sites',
    retry: 'Retry',
    back: 'Previous',
    continue: 'Continue',
    selected: 'Selected',
    allCities: 'All cities',
  },
}

// ============================================================================
// COMPONENT
// ============================================================================

export function SiteSelection({
  sessionId,
  onComplete,
  onBack,
  locale = 'es',
  getAvailableSites,
  saveSiteSelection,
  initialSiteId,
}: SiteSelectionProps) {
  const t = translations[locale] || translations.es

  // State
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sites, setSites] = useState<SiteInfo[]>([])
  const [cities, setCities] = useState<Record<string, SiteInfo[]>>({})
  const [selectedCity, setSelectedCity] = useState<string | null>(null)
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(initialSiteId ?? null)

  // Derived
  const cityList = Object.keys(cities).sort()
  const hasMultipleCities = cityList.length > 1
  const visibleSites = selectedCity ? (cities[selectedCity] || []) : sites

  // Load available sites
  const loadSites = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const result = await getAvailableSites(sessionId)
      setSites(result.sites)
      setCities(result.cities)

      // Auto-select city if only one
      const uniqueCities = Object.keys(result.cities)
      if (uniqueCities.length === 1) {
        setSelectedCity(uniqueCities[0])
      }

      // Auto-select and auto-save if only one total site
      if (result.sites.length === 1 && !initialSiteId) {
        const singleSite = result.sites[0]
        setSelectedSiteId(singleSite.id)
        // Auto-save and advance — no need for extra click
        try {
          const saveResult = await saveSiteSelection(sessionId, {
            entityLocationId: singleSite.id,
            locationName: singleSite.locationName,
            city: singleSite.city,
            entityCode: singleSite.entityCode,
          })
          if (saveResult.success) {
            onComplete()
            return
          }
        } catch {
          // If auto-save fails, fall through to manual selection
        }
      }

      // Restore pre-selected site's city
      if (initialSiteId) {
        const preSite = result.sites.find(s => s.id === initialSiteId)
        if (preSite) {
          setSelectedCity(preSite.city)
          setSelectedSiteId(preSite.id)
        }
      }
    } catch (err) {
      setError(t.error)
      console.error('[SiteSelection] Error loading sites:', err)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, getAvailableSites, initialSiteId, t.error])

  useEffect(() => {
    loadSites()
  }, [loadSites])

  // Save and continue
  const handleContinue = useCallback(async () => {
    if (!selectedSiteId) return

    const site = sites.find(s => s.id === selectedSiteId)
    if (!site) return

    try {
      setIsSaving(true)
      setError(null)
      const result = await saveSiteSelection(sessionId, {
        entityLocationId: site.id,
        locationName: site.locationName,
        city: site.city,
        entityCode: site.entityCode,
      })
      if (result.success) {
        onComplete()
      }
    } catch (err) {
      setError(t.error)
      console.error('[SiteSelection] Error saving site:', err)
    } finally {
      setIsSaving(false)
    }
  }, [selectedSiteId, sites, sessionId, saveSiteSelection, onComplete, t.error])

  // ========================================================================
  // RENDER
  // ========================================================================

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>{t.loading}</span>
        </div>
        <div className="grid gap-3">
          {[1, 2, 3].map(i => (
            <Skeleton key={i} className="h-20 w-full rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (error && sites.length === 0) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t.back}
          </Button>
          <Button variant="outline" onClick={loadSites}>
            {t.retry}
          </Button>
        </div>
      </div>
    )
  }

  if (sites.length === 0) {
    return (
      <div className="space-y-4">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{t.noSites}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t.back}
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* City filter (only if 2+ cities) */}
      {hasMultipleCities && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-muted-foreground">
            <MapPin className="inline h-4 w-4 mr-1" />
            {t.cityFilter}
          </h3>
          <div className="flex flex-wrap gap-2">
            {cityList.map(city => (
              <Button
                key={city}
                variant={selectedCity === city ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setSelectedCity(city)
                  // Reset site selection when changing city
                  const citysSites = cities[city] || []
                  if (citysSites.length === 1) {
                    setSelectedSiteId(citysSites[0].id)
                  } else {
                    setSelectedSiteId(null)
                  }
                }}
                className="min-w-[100px]"
              >
                <MapPin className="mr-1 h-3 w-3" />
                {city}
                <Badge variant="secondary" className="ml-2 text-xs">
                  {(cities[city] || []).length}
                </Badge>
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Sites list */}
      {(selectedCity || !hasMultipleCities) && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-muted-foreground">
            <Building2 className="inline h-4 w-4 mr-1" />
            {t.selectSite}
          </h3>
          <RadioGroup
            value={selectedSiteId || ''}
            onValueChange={setSelectedSiteId}
            className="grid gap-3"
          >
            {visibleSites.map(site => (
              <Label
                key={site.id}
                htmlFor={`site-${site.id}`}
                className={cn(
                  'flex items-start gap-3 rounded-lg border p-4 cursor-pointer transition-colors',
                  selectedSiteId === site.id
                    ? 'border-primary bg-primary/5 ring-1 ring-primary'
                    : 'border-border hover:bg-accent/50'
                )}
              >
                <RadioGroupItem value={site.id} id={`site-${site.id}`} className="mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{site.locationName}</span>
                    {site.isMainOffice && (
                      <Badge variant="secondary" className="text-xs">
                        {t.mainOffice}
                      </Badge>
                    )}
                    {selectedSiteId === site.id && (
                      <CheckCircle className="h-4 w-4 text-primary ml-auto flex-shrink-0" />
                    )}
                  </div>
                  {site.locationAddress && (
                    <p className="text-xs text-muted-foreground mt-1">{site.locationAddress}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-0.5">
                    <MapPin className="inline h-3 w-3 mr-0.5" />
                    {site.city}
                  </p>
                </div>
              </Label>
            ))}
          </RadioGroup>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={onBack} disabled={isSaving}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t.back}
        </Button>
        <Button
          onClick={handleContinue}
          disabled={!selectedSiteId || isSaving}
        >
          {isSaving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <ArrowRight className="mr-2 h-4 w-4" />
          )}
          {t.continue}
        </Button>
      </div>
    </div>
  )
}
