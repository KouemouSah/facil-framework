'use client';

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import type { ChartOptions } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Shield } from 'lucide-react';
import type { SLABreakdown } from '../types';

ChartJS.register(ArcElement, Tooltip, Legend);

interface SLAComplianceDonutProps {
  data: SLABreakdown;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export function SLAComplianceDonut({ data, t }: SLAComplianceDonutProps) {
  const total = data.onTime + data.breached + data.noSla;

  const chartData = useMemo(() => ({
    labels: [t('workload.onTime'), t('workload.breached'), t('workload.noSla')],
    datasets: [{
      data: [data.onTime, data.breached, data.noSla],
      backgroundColor: ['rgb(16, 185, 129)', 'rgb(239, 68, 68)', 'rgb(156, 163, 175)'],
      borderWidth: 0,
      hoverOffset: 4,
    }],
  }), [data, t]);

  const options = useMemo<ChartOptions<'doughnut'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    cutout: '65%',
    plugins: {
      legend: {
        position: 'bottom',
        labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, padding: 12 },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : '0';
            return `${ctx.label}: ${ctx.parsed} (${pct}%)`;
          },
        },
      },
    },
  }), [total]);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-emerald-500" />
            <CardTitle className="text-base">{t('workload.slaCompliance')}</CardTitle>
          </div>
          <span className={`text-lg font-bold ${data.compliancePct >= 80 ? 'text-green-600' : data.compliancePct >= 50 ? 'text-orange-600' : 'text-red-600'}`}>
            {data.compliancePct}%
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[170px]">
          {total > 0 ? (
            <Doughnut data={chartData} options={options} />
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
