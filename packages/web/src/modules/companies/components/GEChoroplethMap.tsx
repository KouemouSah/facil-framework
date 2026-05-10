'use client'

/**
 * GE Choropleth Map — Leaflet + GeoJSON (Interactive)
 *
 * Interactive map of Equatorial Guinea's 12 commerce zones.
 * Click zone → drill-down panel with zone details.
 * Hover → tooltip with KPIs.
 * Color-coded by metric (companies/debt/recovery).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ZoneStats } from '../types'

import 'leaflet/dist/leaflet.css'

import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet'
import type { GeoJSON as LeafletGeoJSON, Layer, PathOptions } from 'leaflet'
import type { Feature, FeatureCollection, Geometry } from 'geojson'

export type MapMetric = 'companies' | 'debt' | 'recovery'

interface Props {
  zones: ZoneStats[]
  metric?: MapMetric
  height?: string
  onZoneClick?: (zoneCode: string, zoneStats: ZoneStats | undefined) => void
  selectedZone?: string | null
}

function getColor(value: number, max: number, metric: MapMetric): string {
  if (max === 0) return '#e5e7eb'
  const ratio = Math.min(value / max, 1)

  if (metric === 'recovery') {
    if (ratio >= 0.8) return '#15803d'
    if (ratio >= 0.6) return '#65a30d'
    if (ratio >= 0.4) return '#ca8a04'
    if (ratio >= 0.2) return '#ea580c'
    return '#dc2626'
  }

  const colors = ['#dbeafe', '#93c5fd', '#60a5fa', '#2563eb', '#1e3a8a']
  return colors[Math.min(Math.floor(ratio * colors.length), colors.length - 1)]
}

function getMetricValue(zone: ZoneStats, metric: MapMetric): number {
  switch (metric) {
    case 'companies': return zone.total_companies
    case 'debt': return zone.total_debt
    case 'recovery': return zone.recovery_rate_pct
  }
}

function formatVal(value: number, metric: MapMetric): string {
  if (metric === 'recovery') return `${value}%`
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`
  return value.toLocaleString()
}

export default function GEChoroplethMap({
  zones, metric = 'companies', height = '400px', onZoneClick, selectedZone,
}: Props) {
  const [geoData, setGeoData] = useState<FeatureCollection | null>(null)
  const geoRef = useRef<LeafletGeoJSON>(null)

  const zoneMap = useMemo(() => new Map(zones.map(z => [z.zone_code, z])), [zones])
  const maxValue = useMemo(
    () => Math.max(...zones.map(z => getMetricValue(z, metric)), 1),
    [zones, metric]
  )

  useEffect(() => {
    fetch('/geo/ge-zones.geojson')
      .then(r => r.json())
      .then(setGeoData)
      .catch(console.error)
  }, [])

  const style = useCallback((feature: Feature<Geometry> | undefined): PathOptions => {
    const code = feature?.properties?.zone_code
    const zone = code ? zoneMap.get(code) : undefined
    const value = zone ? getMetricValue(zone, metric) : 0
    const isSelected = code === selectedZone

    return {
      fillColor: getColor(value, maxValue, metric),
      weight: isSelected ? 4 : 2,
      opacity: 1,
      color: isSelected ? '#1d4ed8' : '#374151',
      fillOpacity: isSelected ? 0.9 : 0.7,
      dashArray: isSelected ? '' : '3',
    }
  }, [zoneMap, maxValue, metric, selectedZone])

  const onEachFeature = useCallback((feature: Feature, layer: Layer) => {
    const code = feature.properties?.zone_code
    const zone = code ? zoneMap.get(code) : undefined
    const props = feature.properties || {}

    if (zone) {
      const lines = [
        `<div style="font-size:13px;line-height:1.4">`,
        `<strong>${zone.zone_code} — ${zone.zone_name}</strong>`,
        `<div style="color:#666;font-size:11px">${props.provincia || ''} · ${props.city || ''}</div>`,
        `<hr style="margin:4px 0;border-color:#e5e7eb"/>`,
        `<div>🏢 ${zone.total_companies} (${zone.active_companies} activas)</div>`,
        `<div>📊 Bundle: ${zone.bundle_count} · Decl: ${zone.declarativo_count}</div>`,
        `<div>💰 ${formatVal(zone.total_obligations_amount, 'debt')}</div>`,
        `<div>✅ ${formatVal(zone.total_paid_amount, 'debt')} · ❌ ${formatVal(zone.total_debt, 'debt')}</div>`,
        `<div style="font-weight:bold;color:${zone.recovery_rate_pct >= 60 ? '#15803d' : '#dc2626'}">`,
        `📈 ${zone.recovery_rate_pct}%</div>`,
        `</div>`,
      ]
      layer.bindTooltip(lines.join(''), { sticky: true, direction: 'top', className: 'leaflet-tooltip-custom' })
    } else {
      layer.bindTooltip(`<strong>${code || 'Unknown'}</strong><br/>${props.name || ''}`, { sticky: true })
    }

    layer.on({
      mouseover: (e) => {
        const l = e.target
        l.setStyle({ weight: 4, fillOpacity: 0.9, dashArray: '' })
        l.bringToFront()
      },
      mouseout: () => {
        geoRef.current?.resetStyle()
      },
      click: () => {
        if (onZoneClick && code) {
          onZoneClick(code, zone)
        }
      },
    })
  }, [zoneMap, onZoneClick])

  if (!geoData) {
    return (
      <div style={{ height }} className="flex items-center justify-center bg-muted/30 rounded border animate-pulse">
        <p className="text-sm text-muted-foreground">Cargando mapa...</p>
      </div>
    )
  }

  return (
    <div style={{ height }} className="rounded overflow-hidden border relative">
      <MapContainer
        center={[1.8, 10.0]}
        zoom={7}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON
          key={`${metric}-${selectedZone}-${zones.length}`}
          ref={geoRef}
          data={geoData}
          style={style}
          onEachFeature={onEachFeature}
        />
      </MapContainer>
      {/* Legend */}
      <div className="absolute bottom-2 right-2 bg-white/90 rounded shadow px-2 py-1 text-[10px] z-[1000]">
        <div className="flex items-center gap-1 mb-0.5 font-semibold">
          {metric === 'companies' ? '🏢 Empresas' : metric === 'debt' ? '💰 Deuda' : '📈 Cobro'}
        </div>
        <div className="flex gap-0.5">
          {(metric === 'recovery'
            ? ['#dc2626', '#ea580c', '#ca8a04', '#65a30d', '#15803d']
            : ['#dbeafe', '#93c5fd', '#60a5fa', '#2563eb', '#1e3a8a']
          ).map((c, i) => (
            <div key={i} className="w-4 h-3 rounded-sm" style={{ backgroundColor: c }} />
          ))}
        </div>
        <div className="flex justify-between text-[9px] text-muted-foreground">
          <span>{metric === 'recovery' ? '0%' : 'Min'}</span>
          <span>{metric === 'recovery' ? '100%' : 'Max'}</span>
        </div>
      </div>
    </div>
  )
}
