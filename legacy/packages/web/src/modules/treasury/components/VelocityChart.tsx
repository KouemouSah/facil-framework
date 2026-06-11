'use client';

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import type { ChartOptions } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp } from 'lucide-react';
import type { DailyVelocityPoint } from '../types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

const COLORS = [
  { border: 'rgb(59, 130, 246)', bg: 'rgba(59, 130, 246, 0.15)' },   // blue
  { border: 'rgb(16, 185, 129)', bg: 'rgba(16, 185, 129, 0.15)' },   // emerald
  { border: 'rgb(245, 158, 11)', bg: 'rgba(245, 158, 11, 0.15)' },   // amber
  { border: 'rgb(139, 92, 246)', bg: 'rgba(139, 92, 246, 0.15)' },   // violet
  { border: 'rgb(236, 72, 153)', bg: 'rgba(236, 72, 153, 0.15)' },   // pink
];

interface VelocityChartProps {
  data: DailyVelocityPoint[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

export function VelocityChart({ data, t }: VelocityChartProps) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return { labels: [], datasets: [] };

    const dates = Array.from(new Set(data.map(d => d.date))).sort();
    const agents = Array.from(new Set(data.map(d => d.agentName)));
    const labels = dates.map(d => {
      const dt = new Date(d);
      return dt.toLocaleDateString('es-GQ', { day: '2-digit', month: 'short' });
    });

    const datasets = agents.map((agent, idx) => {
      const color = COLORS[idx % COLORS.length];
      const agentData = dates.map(date => {
        const point = data.find(d => d.date === date && d.agentName === agent);
        return (point?.approved ?? 0) + (point?.rejected ?? 0);
      });
      return {
        label: agent,
        data: agentData,
        borderColor: color.border,
        backgroundColor: color.bg,
        fill: false,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 5,
      };
    });

    return { labels, datasets };
  }, [data]);

  const options = useMemo<ChartOptions<'line'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} ${t('workload.validated')}`,
        },
      },
    },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } },
    },
  }), [t]);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-blue-500" />
          <CardTitle className="text-base">{t('workload.velocity')}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          {data.length > 0 ? (
            <Line data={chartData} options={options} />
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground">{t('workload.noAgents')}</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
