'use client'

/**
 * Professional SVG Map of Equatorial Guinea — 8 provinces
 *
 * GADM 4.1 real geographic boundaries + OSM Djibloho (2017 province).
 * Mercator-projected SVG paths. Annobón in cartographic inset (350km SW).
 * Color-coded by metric, interactive tooltip, click-to-filter.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import {
  GNQ_PROVINCES as RAW_PROVINCES,
  GNQ_SVG_WIDTH, GNQ_SVG_HEIGHT, GNQ_RENDER_ORDER,
} from '@/modules/companies/utils/gnq-map-data'

export interface ProvinceData {
  provincia: string
  companies: number
  debt: number
  recovery: number
}

interface GEMapProps {
  data: ProvinceData[]
  colorBy: 'companies' | 'debt' | 'recovery'
  selected?: string | null
  onSelect?: (provincia: string | null) => void
}

// Mapping from DB provincia names (uppercase) to map data keys
const PROVINCIA_KEY_MAP: Record<string, string> = {
  'ANNOBON': 'annobon',
  'BIOKO-NORTE': 'bioko_norte',
  'BIOKO-SUR': 'bioko_sur',
  'CENTRO-SUR': 'centro_sur',
  'KIE-NTEM': 'kie_ntem',
  'LITORAL': 'litoral',
  'WELE-NZAS': 'wele_nzas',
  'DJIBLOHO': 'djibloho',
}
const KEY_PROVINCIA_MAP = Object.fromEntries(Object.entries(PROVINCIA_KEY_MAP).map(([k, v]) => [v, k]))

// Color functions (HSL for perceptual uniformity)
function getColor(value: number, max: number, colorBy: string): string {
  if (max === 0) return '#e2e8f0'
  const pct = Math.min(value / max, 1)
  if (colorBy === 'recovery') {
    if (pct >= 0.7) return `hsl(140, ${55 + pct * 20}%, 42%)`
    if (pct >= 0.4) return `hsl(45, 70%, 50%)`
    if (pct > 0) return `hsl(0, ${55 + pct * 30}%, 48%)`
    return '#e2e8f0'
  }
  if (colorBy === 'debt') return `hsl(0, ${50 + pct * 30}%, ${92 - pct * 50}%)`
  return `hsl(217, ${50 + pct * 30}%, ${92 - pct * 48}%)`
}

function fmtK(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

const LEGEND: Record<string, { label: string; colors: string[] }> = {
  companies: { label: 'Empresas', colors: ['#dbeafe', '#3b82f6', '#1e3a8a'] },
  debt: { label: 'Deuda (XAF)', colors: ['#fee2e2', '#ef4444', '#7f1d1d'] },
  recovery: { label: 'Recovery %', colors: ['#ef4444', '#eab308', '#22c55e'] },
}

// Compute bounding box from SVG path d string
// Extracts explicit coordinate pairs after M/L commands and Bézier endpoints
function pathBBox(d: string): { x: number; y: number; w: number; h: number } {
  // Match all coordinate pairs (x y) after path commands
  const pairs: [number, number][] = []
  const re = /([MLCHVSQTAZ])\s*([\d.e+-]+[\s,][\d.e+-]+(?:[\s,][\d.e+-]+[\s,][\d.e+-]+)*)/gi
  let match
  while ((match = re.exec(d)) !== null) {
    const nums = match[2].match(/[\d.e+-]+/g)?.map(Number) ?? []
    for (let i = 0; i < nums.length - 1; i += 2) {
      pairs.push([nums[i], nums[i + 1]])
    }
  }
  if (pairs.length === 0) return { x: 0, y: 0, w: 100, h: 100 }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const [x, y] of pairs) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY }
}

// Parse "x y w h" viewBox string to numbers
function parseVB(vb: string): [number, number, number, number] {
  const p = vb.split(' ').map(Number)
  return [p[0], p[1], p[2], p[3]]
}

// Lerp between two viewBox values
function lerpVB(a: [number, number, number, number], b: [number, number, number, number], t: number): string {
  return `${a[0] + (b[0] - a[0]) * t} ${a[1] + (b[1] - a[1]) * t} ${a[2] + (b[2] - a[2]) * t} ${a[3] + (b[3] - a[3]) * t}`
}

// Ease-in-out cubic
function ease(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

export function GEMapSVG({ data, colorBy, selected, onSelect }: GEMapProps) {
  const [hovered, setHovered] = useState<string | null>(null)
  const [zoomedKey, setZoomedKey] = useState<string | null>(null)

  const DEFAULT_VB = `350 0 ${GNQ_SVG_WIDTH - 300} ${GNQ_SVG_HEIGHT - 280}`
  const [animatedVB, setAnimatedVB] = useState(DEFAULT_VB)
  const animRef = useRef<number>()

  // Map DB provincia name → data
  const dataMap = useMemo(() => {
    const m = new Map<string, ProvinceData>()
    for (const d of data) m.set(d.provincia, d)
    return m
  }, [data])

  const maxVal = useMemo(() => {
    if (colorBy === 'companies') return Math.max(...data.map(d => d.companies), 1)
    if (colorBy === 'debt') return Math.max(...data.map(d => d.debt), 1)
    return 100
  }, [data, colorBy])

  const hoveredProvincia = hovered ? KEY_PROVINCIA_MAP[hovered] : null
  const hoveredData = hoveredProvincia ? dataMap.get(hoveredProvincia) : null
  const selectedKey = selected ? PROVINCIA_KEY_MAP[selected] : null
  const legend = LEGEND[colorBy]

  // Compute target viewBox for zoom
  const targetVB = useMemo(() => {
    if (!zoomedKey || zoomedKey === 'annobon') return DEFAULT_VB
    const prov = RAW_PROVINCES[zoomedKey]
    if (!prov) return DEFAULT_VB
    const bb = pathBBox(prov.path)
    const pad = Math.max(bb.w, bb.h) * 0.25
    return `${bb.x - pad} ${bb.y - pad} ${bb.w + pad * 2} ${bb.h + pad * 2}`
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomedKey])

  // Animate viewBox transition (400ms ease-in-out)
  const animateVB = useCallback((from: string, to: string) => {
    if (animRef.current) cancelAnimationFrame(animRef.current)
    const fromVB = parseVB(from)
    const toVB = parseVB(to)
    const duration = 400
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      setAnimatedVB(lerpVB(fromVB, toVB, ease(t)))
      if (t < 1) animRef.current = requestAnimationFrame(step)
    }
    animRef.current = requestAnimationFrame(step)
  }, [])

  useEffect(() => {
    animateVB(animatedVB, targetVB)
    // Only animate when target changes, not when animatedVB updates
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetVB, animateVB])

  // Sync zoom with parent selection
  useEffect(() => {
    if (!selected && zoomedKey) setZoomedKey(null)
  }, [selected, zoomedKey])

  const handleProvinceClick = (key: string, dbName: string | undefined) => {
    if (zoomedKey === key) {
      setZoomedKey(null)
      onSelect?.(null)
    } else {
      setZoomedKey(key)
      onSelect?.(dbName || key)
    }
  }

  // Annobón inset: scale up and reposition (original ~5x9px at [15,711])
  const ANNOBON_SCALE = 5
  const ANNOBON_INSET_X = 20
  const ANNOBON_INSET_Y = 520

  return (
    <div className="relative">
      {/* Zoom out button */}
      {zoomedKey && (
        <button
          onClick={() => { setZoomedKey(null); onSelect?.(null) }}
          className="absolute top-2 left-2 z-10 bg-white/90 border shadow-sm rounded-md px-2 py-1 text-[10px] font-medium text-gray-600 hover:text-gray-900 transition-colors"
        >
          ← Vista completa
        </button>
      )}
      <svg
        viewBox={animatedVB}
        className="w-full h-auto"
        role="img"
        aria-label="Mapa de Guinea Ecuatorial — Datos GADM 4.1"
      >
        <defs>
          <pattern id="ge-ocean" patternUnits="userSpaceOnUse" width="14" height="14">
            <line x1="0" y1="7" x2="14" y2="7" stroke="#bfdbfe" strokeWidth="0.4" opacity="0.25" />
          </pattern>
          <linearGradient id={`ge-legend-${colorBy}`} x1="0" x2="1" y1="0" y2="0">
            {legend.colors.map((c, i) => (
              <stop key={i} offset={`${(i / (legend.colors.length - 1)) * 100}%`} stopColor={c} />
            ))}
          </linearGradient>
          <clipPath id="annobon-clip">
            <rect x={ANNOBON_INSET_X - 5} y={ANNOBON_INSET_Y - 5} width={55} height={65} />
          </clipPath>
        </defs>

        {/* Ocean */}
        <rect x="350" y="0" width="500" height="460" fill="#f0f7ff" />
        <rect x="350" y="0" width="500" height="460" fill="url(#ge-ocean)" />

        {/* Region labels */}
        <text x="440" y="12" textAnchor="middle" fontSize="7" fontWeight="700" letterSpacing="2" className="fill-gray-400 uppercase">Bioko</text>
        <text x="670" y="220" textAnchor="middle" fontSize="7" fontWeight="700" letterSpacing="2" className="fill-gray-400 uppercase">Río Muni</text>
        <text x="490" y="240" textAnchor="middle" fontSize="7" fontStyle="italic" className="fill-blue-200" transform="rotate(-20 490 240)">Golfo de Guinea</text>

        {/* Provinces (real GADM boundaries) */}
        {GNQ_RENDER_ORDER.filter(k => k !== 'annobon').map(key => {
          const prov = RAW_PROVINCES[key]
          if (!prov) return null
          const dbName = KEY_PROVINCIA_MAP[key]
          const d = dbName ? dataMap.get(dbName) : null
          const val = colorBy === 'companies' ? (d?.companies ?? 0) :
                      colorBy === 'debt' ? (d?.debt ?? 0) : (d?.recovery ?? 0)
          const fill = getColor(val, maxVal, colorBy)
          const isSel = selectedKey === key
          const isHov = hovered === key
          const dimmed = selectedKey != null && !isSel

          return (
            <g key={key}
              onMouseEnter={() => setHovered(key)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => handleProvinceClick(key, dbName)}
              className="cursor-pointer"
            >
              <path d={prov.path} fill={fill}
                stroke={isSel ? '#1e40af' : isHov ? '#3b82f6' : '#64748b'}
                strokeWidth={isSel ? 2 : isHov ? 1.5 : 0.6}
                opacity={dimmed ? 0.3 : 1}
                className="transition-all duration-200" />
              {/* Label + counter */}
              {!dimmed && (
                <>
                  <text x={prov.labelX} y={prov.labelY - 4} textAnchor="middle" fontSize="6" fontWeight="600"
                    className="fill-gray-700 pointer-events-none select-none">{prov.name}</text>
                  {d && (
                    <text x={prov.labelX} y={prov.labelY + 5} textAnchor="middle" fontSize="7.5" fontWeight="700"
                      className="pointer-events-none select-none"
                      fill={colorBy === 'debt' ? '#991b1b' : colorBy === 'recovery' ? '#166534' : '#1e3a8a'}>
                      {colorBy === 'companies' ? d.companies : colorBy === 'debt' ? fmtK(d.debt) : `${d.recovery}%`}
                    </text>
                  )}
                  {/* Capital dot */}
                  <circle cx={prov.labelX} cy={prov.labelY + 10} r="1.2" fill="#1e293b" opacity={0.5} className="pointer-events-none" />
                  <text x={prov.labelX + 4} y={prov.labelY + 12} fontSize="4.5" className="fill-gray-400 pointer-events-none" fontStyle="italic">{prov.capital}</text>
                </>
              )}
            </g>
          )
        })}

        {/* Annobón inset box */}
        <rect x={ANNOBON_INSET_X - 8} y={ANNOBON_INSET_Y - 18} width={60} height={75} rx="3"
          fill="#f8fafc" stroke="#94a3b8" strokeWidth="0.6" strokeDasharray="3,2" />
        <text x={ANNOBON_INSET_X + 22} y={ANNOBON_INSET_Y - 8} textAnchor="middle"
          fontSize="5" className="fill-gray-400">Annobón (encart)</text>

        {/* Annobón province (scaled up in inset) */}
        {(() => {
          const prov = RAW_PROVINCES['annobon']
          if (!prov) return null
          const d = dataMap.get('ANNOBON')
          const val = colorBy === 'companies' ? (d?.companies ?? 0) :
                      colorBy === 'debt' ? (d?.debt ?? 0) : (d?.recovery ?? 0)
          const fill = getColor(val, maxVal, colorBy)
          const isSel = selectedKey === 'annobon'
          const isHov = hovered === 'annobon'
          const dimmed = selectedKey != null && !isSel
          // Transform: translate to inset position, scale up
          const tx = ANNOBON_INSET_X - 15 * ANNOBON_SCALE + 20
          const ty = ANNOBON_INSET_Y - 711 * ANNOBON_SCALE + 20
          return (
            <g
              onMouseEnter={() => setHovered('annobon')}
              onMouseLeave={() => setHovered(null)}
              onClick={() => handleProvinceClick('annobon', 'ANNOBON')}
              className="cursor-pointer"
              clipPath="url(#annobon-clip)"
              transform={`translate(${tx},${ty}) scale(${ANNOBON_SCALE})`}
            >
              <path d={prov.path} fill={fill}
                stroke={isSel ? '#1e40af' : isHov ? '#3b82f6' : '#64748b'}
                strokeWidth={(isSel ? 2 : isHov ? 1.5 : 0.6) / ANNOBON_SCALE}
                opacity={dimmed ? 0.3 : 1}
                className="transition-all duration-200" />
            </g>
          )
        })()}
        {/* Annobón label (outside transform) */}
        {!selectedKey || selectedKey === 'annobon' ? (
          <>
            {dataMap.get('ANNOBON') && (
              <text x={ANNOBON_INSET_X + 22} y={ANNOBON_INSET_Y + 40} textAnchor="middle" fontSize="7" fontWeight="700"
                className="pointer-events-none" fill={colorBy === 'debt' ? '#991b1b' : colorBy === 'recovery' ? '#166534' : '#1e3a8a'}>
                {colorBy === 'companies' ? dataMap.get('ANNOBON')!.companies :
                 colorBy === 'debt' ? fmtK(dataMap.get('ANNOBON')!.debt) :
                 `${dataMap.get('ANNOBON')!.recovery}%`}
              </text>
            )}
          </>
        ) : null}

        {/* North arrow */}
        <g transform="translate(780, 15)">
          <polygon points="0,0 -3,7 3,7" fill="#64748b" />
          <line x1="0" y1="7" x2="0" y2="18" stroke="#64748b" strokeWidth="1" />
          <text x="0" y="26" textAnchor="middle" fontSize="7" fontWeight="700" className="fill-gray-500">N</text>
        </g>

        {/* Legend */}
        <g transform="translate(680, 415)">
          <text x="0" y="0" fontSize="6" fontWeight="600" className="fill-gray-500">{legend.label}</text>
          <rect x="0" y="4" width="90" height="6" rx="1.5" fill={`url(#ge-legend-${colorBy})`} />
          <text x="0" y="18" fontSize="5" className="fill-gray-400">{colorBy === 'recovery' ? '0%' : '0'}</text>
          <text x="90" y="18" textAnchor="end" fontSize="5" className="fill-gray-400">
            {colorBy === 'recovery' ? '100%' : colorBy === 'debt' ? fmtK(maxVal) + ' XAF' : String(maxVal)}
          </text>
        </g>

        {/* Source credit */}
        <text x="790" y="450" textAnchor="end" fontSize="4" className="fill-gray-300">
          GADM 4.1 + OSM · Facil GE
        </text>
      </svg>

      {/* Tooltip */}
      {hoveredData && hoveredProvincia && (
        <div className="absolute top-2 right-2 bg-white/95 backdrop-blur-sm border shadow-lg rounded-lg p-3 text-xs pointer-events-none z-10 min-w-[160px]">
          <p className="font-semibold text-sm mb-1.5">{hoveredProvincia}</p>
          <div className="space-y-1 text-muted-foreground">
            <div className="flex justify-between gap-4">
              <span>Empresas:</span>
              <strong className="text-foreground">{hoveredData.companies}</strong>
            </div>
            <div className="flex justify-between gap-4">
              <span>Deuda:</span>
              <strong className="text-red-600">{fmtK(hoveredData.debt)} XAF</strong>
            </div>
            <div className="flex justify-between gap-4">
              <span>Recovery:</span>
              <Badge className={`text-[9px] px-1.5 py-0 ${
                hoveredData.recovery >= 70 ? 'bg-green-100 text-green-800' :
                hoveredData.recovery >= 40 ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>{hoveredData.recovery}%</Badge>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
