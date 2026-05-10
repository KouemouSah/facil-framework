'use client'

/**
 * Dynamic import wrapper for GEChoroplethMap.
 *
 * Leaflet requires window/document which don't exist during SSR.
 * This wrapper uses next/dynamic with ssr: false.
 */

import dynamic from 'next/dynamic'
import type { ZoneStats } from '../types'
import type { MapMetric } from './GEChoroplethMap'

const GEChoroplethMap = dynamic(() => import('./GEChoroplethMap'), {
  ssr: false,
  loading: () => (
    <div className="h-[400px] flex items-center justify-center bg-muted/30 rounded border">
      <p className="text-sm text-muted-foreground">Loading map...</p>
    </div>
  ),
})

interface Props {
  zones: ZoneStats[]
  metric?: MapMetric
  height?: string
  onZoneClick?: (zoneCode: string, zoneStats: ZoneStats | undefined) => void
  selectedZone?: string | null
}

export default function DynamicGEMap(props: Props) {
  return <GEChoroplethMap {...props} />
}
