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
import { BarChart3 } from 'lucide-react';
import type { VolumeTrendPoint } from '../types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface VolumeTrendChartProps {
  data: VolumeTrendPoint[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

export function VolumeTrendChart({ data, t }: VolumeTrendChartProps) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return { labels: [], datasets: [] };

    const labels = data.map(d => {
      const dt = new Date(d.date);
      return dt.toLocaleDateString('es-GQ', { day: '2-digit', month: 'short' });
    });

    return {
      labels,
      datasets: [
        {
          label: t('workload.incoming'),
          data: data.map(d => d.incoming),
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 2,
        },
        {
          label: t('workload.outgoing'),
          data: data.map(d => d.outgoing),
          borderColor: 'rgb(16, 185, 129)',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 2,
        },
      ],
    };
  }, [data, t]);

  const options = useMemo<ChartOptions<'line'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
    },
    scales: {
      y: { beginAtZero: true, stacked: false, ticks: { stepSize: 1 } },
    },
  }), []);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-violet-500" />
          <CardTitle className="text-base">{t('workload.volumeTrend')}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[180px]">
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
