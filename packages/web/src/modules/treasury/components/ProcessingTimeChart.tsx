'use client';

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import type { ChartOptions } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Clock } from 'lucide-react';
import type { ProcessingTimeAgent } from '../types';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface ProcessingTimeChartProps {
  data: ProcessingTimeAgent[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

export function ProcessingTimeChart({ data, t }: ProcessingTimeChartProps) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return { labels: [], datasets: [] };

    const labels = data.map(a => {
      const name = a.agentName;
      return name.length > 20 ? name.substring(0, 20) + '...' : name;
    });

    return {
      labels,
      datasets: [
        {
          label: t('workload.minTime'),
          data: data.map(a => a.minHours),
          backgroundColor: 'rgba(16, 185, 129, 0.6)',
          borderRadius: 4,
        },
        {
          label: t('workload.avgTime'),
          data: data.map(a => a.avgHours),
          backgroundColor: 'rgba(59, 130, 246, 0.6)',
          borderRadius: 4,
        },
        {
          label: t('workload.maxTime'),
          data: data.map(a => a.maxHours),
          backgroundColor: 'rgba(239, 68, 68, 0.6)',
          borderRadius: 4,
        },
      ],
    };
  }, [data, t]);

  const options = useMemo<ChartOptions<'bar'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}h`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: { display: true, text: t('workload.hours'), font: { size: 11 } },
      },
    },
  }), [t]);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-orange-500" />
          <CardTitle className="text-base">{t('workload.processingTime')}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          {data.length > 0 ? (
            <Bar data={chartData} options={options} />
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
