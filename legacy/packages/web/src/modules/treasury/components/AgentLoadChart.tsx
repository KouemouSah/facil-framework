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
import { Users } from 'lucide-react';
import type { WorkloadAgentLoad } from '../types';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface AgentLoadChartProps {
  data: WorkloadAgentLoad[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

export function AgentLoadChart({ data, t }: AgentLoadChartProps) {
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
          label: t('workload.completedPeriod'),
          data: data.map(a => a.completedPeriod),
          backgroundColor: 'rgb(16, 185, 129)',
          borderRadius: 4,
        },
        {
          label: t('workload.pending'),
          data: data.map(a => a.pending + a.inProgress),
          backgroundColor: 'rgb(245, 158, 11)',
          borderRadius: 4,
        },
      ],
    };
  }, [data, t]);

  const options = useMemo<ChartOptions<'bar'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
    },
    scales: {
      x: { beginAtZero: true, stacked: false, ticks: { stepSize: 1 } },
      y: { stacked: false },
    },
  }), []);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-blue-500" />
          <CardTitle className="text-base">{t('workload.agentLoad')}</CardTitle>
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
