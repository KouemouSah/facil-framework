'use client'

/**
 * Appointments Admin Page (CITA)
 *
 * Focused on appointment slot management only.
 * Entity/location/city management moved to /admin/entities
 *
 * Tabs:
 * - Slots: Appointment slot configurations
 * - Blocked: Blocked dates management
 * - Delays: Wait time rules
 * - Stats: Appointment statistics
 */

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { useSearchParams, useRouter, usePathname } from 'next/navigation'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CalendarClock, CalendarX, Clock, BarChart3 } from 'lucide-react'

// Import tab content components
import SlotsTabContent from './components/SlotsTabContent'
import BlockedTabContent from './components/BlockedTabContent'
import DelaysTabContent from './components/DelaysTabContent'
import StatsTabContent from './components/StatsTabContent'

const VALID_TABS = ['slots', 'blocked', 'delays', 'stats']

export default function AppointmentsPage() {
  const t = useTranslations('admin.serviceRequests.appointments')
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  // Get initial tab from URL params or default to 'slots'
  const initialTab = searchParams.get('tab') || 'slots'
  const [activeTab, setActiveTab] = useState(initialTab)

  // Update URL when tab changes
  const handleTabChange = (value: string) => {
    setActiveTab(value)
    const params = new URLSearchParams(searchParams.toString())
    params.set('tab', value)
    router.push(`${pathname}?${params.toString()}`, { scroll: false })
  }

  // Sync tab with URL on mount and when URL changes
  useEffect(() => {
    const tabParam = searchParams.get('tab')
    if (tabParam && VALID_TABS.includes(tabParam)) {
      setActiveTab(tabParam)
    }
  }, [searchParams])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground">{t('subtitle')}</p>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
        <TabsList className="grid w-full grid-cols-4 lg:w-[700px] h-auto">
          <TabsTrigger value="slots" className="flex items-center gap-2 px-4 py-2.5">
            <CalendarClock className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline truncate">{t('slots.title')}</span>
            <span className="sm:hidden">{t('tabs.slots')}</span>
          </TabsTrigger>
          <TabsTrigger value="blocked" className="flex items-center gap-2 px-4 py-2.5">
            <CalendarX className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline truncate">{t('blocked.title')}</span>
            <span className="sm:hidden">{t('tabs.blocked')}</span>
          </TabsTrigger>
          <TabsTrigger value="delays" className="flex items-center gap-2 px-4 py-2.5">
            <Clock className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline truncate">{t('delays.title')}</span>
            <span className="sm:hidden">{t('tabs.delays')}</span>
          </TabsTrigger>
          <TabsTrigger value="stats" className="flex items-center gap-2 px-4 py-2.5">
            <BarChart3 className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline truncate">{t('stats.title')}</span>
            <span className="sm:hidden">{t('tabs.stats')}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="slots" className="mt-6">
          <SlotsTabContent />
        </TabsContent>

        <TabsContent value="blocked" className="mt-6">
          <BlockedTabContent />
        </TabsContent>

        <TabsContent value="delays" className="mt-6">
          <DelaysTabContent />
        </TabsContent>

        <TabsContent value="stats" className="mt-6">
          <StatsTabContent />
        </TabsContent>
      </Tabs>
    </div>
  )
}
