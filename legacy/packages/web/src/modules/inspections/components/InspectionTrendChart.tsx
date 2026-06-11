'use client'

import { useMemo } from 'react'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  PointElement, LineElement, BarElement, Filler, Tooltip, Legend,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { TrendPoint } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Filler, Tooltip, Legend)

interface InspectionTrendChartProps {
  data: TrendPoint[]
  granularity: string
  onGranularityChange?: (g: 'daily' | 'weekly' | 'monthly') => void
  loading?: boolean
  height?: number
}

const GRANULARITY_OPTIONS = [
  { value: 'daily' as const, label: 'Diario' },
  { value: 'weekly' as const, label: 'Semanal' },
  { value: 'monthly' as const, label: 'Mensual' },
]

export function InspectionTrendChart({
  data, granularity, onGranularityChange, loading, height = 280,
}: InspectionTrendChartProps) {
  const chartData = useMemo(() => ({
    labels: data.map(d => d.period),
    datasets: [
      {
        label: 'Conformes',
        data: data.map(d => d.conforme),
        borderColor: '#28a745',
        backgroundColor: 'rgba(40, 167, 69, 0.1)',
        tension: 0.3,
        fill: true,
        pointRadius: 3,
      },
      {
        label: 'No Conformes',
        data: data.map(d => d.non_conforme),
        borderColor: '#dc3545',
        backgroundColor: 'rgba(220, 53, 69, 0.1)',
        tension: 0.3,
        fill: true,
        pointRadius: 3,
      },
    ],
  }), [data])

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: { position: 'top' as const, labels: { boxWidth: 12, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          title: (items: Array<{ dataIndex: number }>) => {
            const idx = items[0]?.dataIndex
            return idx !== undefined ? data[idx]?.period || '' : ''
          },
          afterBody: (items: Array<{ dataIndex: number }>) => {
            const idx = items[0]?.dataIndex
            if (idx === undefined) return ''
            const pt = data[idx]
            return pt ? `Tasa: ${pt.conformity_rate}% | Cobrado: ${Number(pt.collected_amount).toLocaleString()} XAF` : ''
          },
        },
      },
    },
    scales: {
      y: { beginAtZero: true, ticks: { font: { size: 10 } } },
      x: { ticks: { font: { size: 9 }, maxRotation: 45 } },
    },
  }), [data])

  if (loading) return <Skeleton className="w-full" style={{ height }} />

  return (
    <div>
      {onGranularityChange && (
        <div className="flex gap-1 mb-2">
          {GRANULARITY_OPTIONS.map(g => (
            <Button
              key={g.value}
              size="sm"
              variant={granularity === g.value ? 'default' : 'outline'}
              className="h-6 text-[10px] px-2"
              onClick={() => onGranularityChange(g.value)}
            >
              {g.label}
            </Button>
          ))}
        </div>
      )}
      <div style={{ height }}>
        <Line data={chartData} options={options} />
      </div>
    </div>
  )
}
