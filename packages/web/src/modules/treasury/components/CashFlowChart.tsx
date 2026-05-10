'use client';

import { useMemo, useState } from 'react';
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
import { Button } from '@/components/ui/button';
import type { PaymentFlowPoint } from '../types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

const MOVING_AVERAGE_DAYS = 7;

interface CashFlowChartProps {
  data: PaymentFlowPoint[];
  periodDays: number;
  onPeriodChange?: (days: number) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

function formatXAF(value: number): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'decimal',
    maximumFractionDigits: 0,
  }).format(value) + ' XAF';
}

export function CashFlowChart({ data, periodDays, onPeriodChange, t }: CashFlowChartProps) {
  const [showCumulative, setShowCumulative] = useState(false);

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return { labels: [], datasets: [] };

    const labels = data.map(d => {
      const date = new Date(d.date);
      return date.toLocaleDateString('es-GQ', { day: '2-digit', month: 'short' });
    });

    const amounts = data.map(d => d.amount);

    let cumulative = 0;
    const cumulativeAmounts = amounts.map(a => {
      cumulative += a;
      return cumulative;
    });

    const movingAvg = amounts.map((_, idx) => {
      const start = Math.max(0, idx - (MOVING_AVERAGE_DAYS - 1));
      const slice = amounts.slice(start, idx + 1);
      return slice.reduce((s, v) => s + v, 0) / slice.length;
    });

    return {
      labels,
      datasets: showCumulative
        ? [
            {
              label: t('overview.cumulativeLabel'),
              data: cumulativeAmounts,
              borderColor: 'rgb(59, 130, 246)',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              fill: true,
              tension: 0.3,
              pointRadius: 2,
            },
          ]
        : [
            {
              label: t('overview.dailyRevenue'),
              data: amounts,
              borderColor: 'rgb(16, 185, 129)',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              fill: true,
              tension: 0.3,
              pointRadius: 2,
            },
            {
              label: t('overview.movingAvg'),
              data: movingAvg,
              borderColor: 'rgb(245, 158, 11)',
              borderDash: [5, 5],
              fill: false,
              tension: 0.4,
              pointRadius: 0,
            },
          ],
    };
  }, [data, showCumulative, t]);

  const options = useMemo<ChartOptions<'line'>>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${formatXAF(ctx.parsed.y ?? 0)}`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: (value) => {
              if (value == null) return '';
              const num = typeof value === 'string' ? parseFloat(value) : value;
              return num >= 1000 ? `${(num / 1000).toFixed(0)}K` : String(num);
            },
          },
        },
      },
    }),
    []
  );

  const totalAmount = data.reduce((sum, d) => sum + d.amount, 0);
  const totalCount = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{t('overview.cashFlow')}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {formatXAF(totalAmount)} {t('overview.totalLabel')} &middot; {totalCount} {t('overview.transactionsLabel')}
            </p>
          </div>
          <div className="flex gap-1">
            {[7, 30, 90].map(d => (
              <Button
                key={d}
                size="sm"
                variant={periodDays === d ? 'default' : 'outline'}
                onClick={() => onPeriodChange?.(d)}
                className="h-7 text-xs"
              >
                {d}d
              </Button>
            ))}
            <Button
              size="sm"
              variant={showCumulative ? 'default' : 'outline'}
              onClick={() => setShowCumulative(!showCumulative)}
              className="h-7 text-xs ml-1"
            >
              {showCumulative ? t('overview.daily') : t('overview.cumulative')}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[180px]">
          {data.length > 0 ? (
            <Line data={chartData} options={options} />
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground">{t('overview.noData')}</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
