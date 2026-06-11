'use client'

/**
 * Entities Admin Page
 * Central management for entities, locations, and cities
 *
 * Tabs:
 * - Entidades: CRUD for entities with workflow_codes
 * - Ubicaciones: CRUD for entity locations
 * - Ciudades: CRUD for cities
 *
 * @module dashboard/admin/entities
 */

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useSearchParams } from 'next/navigation'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Building, MapPin, Globe } from 'lucide-react'
import EntitiesTabContent from './components/EntitiesTabContent'
import LocationsTabContent from './components/LocationsTabContent'
import CitiesTabContent from './components/CitiesTabContent'

export default function EntitiesPage() {
  const t = useTranslations('admin.entities')
  const searchParams = useSearchParams()

  // Get initial tab from URL or default to 'entities'
  const initialTab = searchParams.get('tab') || 'entities'
  const [activeTab, setActiveTab] = useState(initialTab)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          {t('pageTitle')}
        </h1>
        <p className="text-muted-foreground mt-2">
          {t('pageSubtitle')}
        </p>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-3 lg:w-[600px]">
          <TabsTrigger value="entities" className="flex items-center justify-center gap-2 px-4 py-2">
            <Building className="h-4 w-4" />
            <span className="hidden sm:inline">{t('tabs.entities')}</span>
          </TabsTrigger>
          <TabsTrigger value="locations" className="flex items-center justify-center gap-2 px-4 py-2">
            <MapPin className="h-4 w-4" />
            <span className="hidden sm:inline">{t('tabs.locations')}</span>
          </TabsTrigger>
          <TabsTrigger value="cities" className="flex items-center justify-center gap-2 px-4 py-2">
            <Globe className="h-4 w-4" />
            <span className="hidden sm:inline">{t('tabs.cities')}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="entities" className="mt-6">
          <EntitiesTabContent />
        </TabsContent>

        <TabsContent value="locations" className="mt-6">
          <LocationsTabContent />
        </TabsContent>

        <TabsContent value="cities" className="mt-6">
          <CitiesTabContent />
        </TabsContent>
      </Tabs>
    </div>
  )
}
