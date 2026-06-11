/**
 * Appointments Page
 * Main page with 3 tabs: Today, Schedule, Calendar
 *
 * @module agent-dashboard/components/appointments
 * @date 2026-01-26
 */

'use client';

import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Calendar, CalendarPlus, CalendarDays, MapPin } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { TodayTab } from './TodayTab';
import { ScheduleTab } from './ScheduleTab';
import { CalendarTab } from './CalendarTab';
import { useSlotsDetailed } from '../../hooks/useAppointments';
import { useAgentDashboard } from '../../hooks/useAgentDashboard';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface AppointmentsPageProps {
  entityCode: EntityCode;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function AppointmentsPage({ entityCode }: AppointmentsPageProps) {
  const t = useTranslations('agent.pages.appointments');
  const { context } = useAgentDashboard();
  const [activeTab, setActiveTab] = useState<string>('today');
  const [selectedLocationId, setSelectedLocationId] = useState<string | undefined>(undefined);

  // Agent's own location from profile
  const agentLocationId = context?.entityLocationId;
  const agentIsMainOffice = context?.isMainOffice ?? true;

  // Fetch slots data to get available locations
  const { data: slotsData } = useSlotsDetailed(entityCode, {
    weekOffset: 0,
    locationId: selectedLocationId,
  });

  const locations = slotsData?.locationsAvailable || [];
  const currentLocation = slotsData?.location;

  // Pre-select agent's own site, fallback to first available
  React.useEffect(() => {
    if (!selectedLocationId) {
      if (agentLocationId) {
        setSelectedLocationId(agentLocationId);
      } else if (currentLocation) {
        setSelectedLocationId(currentLocation.id);
      }
    }
  }, [selectedLocationId, agentLocationId, currentLocation]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t('pageTitle')}
          </h1>
          <p className="text-muted-foreground">
            {t('pageSubtitle', { entity: entityCode.replace('_', ' ') })}
          </p>
        </div>

        {/* Location Selector — main-office agents can switch sites, others see fixed badge */}
        {!agentIsMainOffice && currentLocation ? (
          <Badge variant="outline" className="flex items-center gap-1.5 px-3 py-1.5 text-sm">
            <MapPin className="h-3.5 w-3.5" />
            {currentLocation.name}
          </Badge>
        ) : locations.length > 1 ? (
          <Select
            value={selectedLocationId || currentLocation?.id || ''}
            onValueChange={(val) => setSelectedLocationId(val || undefined)}
          >
            <SelectTrigger className="w-[220px]">
              <MapPin className="h-4 w-4 mr-2" />
              <SelectValue placeholder={t('selectLocation')} />
            </SelectTrigger>
            <SelectContent>
              {locations.map((loc) => (
                <SelectItem key={loc.id} value={loc.id}>
                  {loc.name} ({loc.city})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3 lg:w-[400px]">
          <TabsTrigger value="today" className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            <span className="hidden sm:inline">{t('tabs.today')}</span>
            <span className="sm:hidden">{t('tabs.today')}</span>
          </TabsTrigger>
          <TabsTrigger value="schedule" className="flex items-center gap-2">
            <CalendarPlus className="h-4 w-4" />
            <span className="hidden sm:inline">{t('tabs.schedule')}</span>
            <span className="sm:hidden">{t('tabs.schedule')}</span>
          </TabsTrigger>
          <TabsTrigger value="calendar" className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4" />
            <span className="hidden sm:inline">{t('tabs.calendar')}</span>
            <span className="sm:hidden">{t('tabs.calendar')}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="today" className="mt-6">
          <TodayTab
            entityCode={entityCode}
            locationId={selectedLocationId}
          />
        </TabsContent>

        <TabsContent value="schedule" className="mt-6">
          <ScheduleTab
            entityCode={entityCode}
            locationId={selectedLocationId}
            onLocationChange={setSelectedLocationId}
          />
        </TabsContent>

        <TabsContent value="calendar" className="mt-6">
          <CalendarTab
            entityCode={entityCode}
            locationId={selectedLocationId}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default AppointmentsPage;
