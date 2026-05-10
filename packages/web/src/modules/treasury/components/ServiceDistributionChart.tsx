'use client';

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { TopServiceItem } from '../types';

ChartJS.register(ArcElement, Tooltip, Legend);

interface ServiceDistributionChartProps {
  data: TopServiceItem[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

const COLORS = [
  'rgb(59, 130, 246)',   // blue
  'rgb(16, 185, 129)',   // emerald
  'rgb(245, 158, 11)',   // amber
  'rgb(139, 92, 246)',   // violet
  'rgb(236, 72, 153)',   // pink
  'rgb(107, 114, 128)',  // gray (Otros)
];

function formatXAF(value: number): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'decimal',
    maximumFractionDigits: 0,
  }).format(value) + ' XAF';
}

export function ServiceDistributionChart({ data, t }: ServiceDistributionChartProps) {
  const totalAmount = data.reduce((sum, d) => sum + d.amount, 0);

  const chartData = useMemo(() => ({
    labels: data.map(d => d.serviceName),
    datasets: [
      {
        data: data.map(d => d.amount),
        backgroundColor: COLORS.slice(0, data.length),
        borderWidth: 2,
        borderColor: 'white',
      },
    ],
  }), [data]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    cutout: '60%',
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { label: string; parsed: number }) =>
            `${ctx.label}: ${formatXAF(ctx.parsed)}`,
        },
      },
    },
  }), []);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{t('overview.serviceDistribution')}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {formatXAF(totalAmount)} {t('overview.totalLabel')}
        </p>
      </CardHeader>
      <CardContent>
        <div className="h-[180px] flex items-center justify-center">
          {data.length > 0 ? (
            <Doughnut data={chartData} options={options} />
          ) : (
            <p className="text-sm text-muted-foreground">{t('overview.noData')}</p>
          )}
        </div>
        {data.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {data.map((item, idx) => (
              <div key={item.workflowCode} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2 min-w-0">
                  <div
                    className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: COLORS[idx] || COLORS[5] }}
                  />
                  <span className="truncate">{item.serviceName}</span>
                </div>
                <div className="flex items-center gap-2 ml-2">
                  <span className="text-muted-foreground text-xs">{item.count}</span>
                  <span className="font-medium tabular-nums">
                    {totalAmount > 0
                      ? `${Math.round((item.amount / totalAmount) * 100)}%`
                      : '0%'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
