/**
 * WorkflowDistributionWidget
 * Displays distribution of requests by workflow type as horizontal bar chart
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-01-26
 */

'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useTranslations } from 'next-intl';
import { BarChart3 } from 'lucide-react';
import { useWorkflowDistribution } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface WorkflowDistributionWidgetProps {
  entityCode: EntityCode;
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const BAR_COLORS = [
  'bg-blue-500',
  'bg-green-500',
  'bg-orange-500',
  'bg-purple-500',
  'bg-pink-500',
  'bg-teal-500',
  'bg-indigo-500',
  'bg-red-500',
];

// =============================================================================
// COMPONENT
// =============================================================================

export function WorkflowDistributionWidget({
  entityCode,
  className,
}: WorkflowDistributionWidgetProps) {
  const t = useTranslations('agent');
  const { data, isLoading, isError } = useWorkflowDistribution(entityCode);

  // Loading state
  if (isLoading) {
    return (
      <Card className={`h-full ${className || ""}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            {t('widgets.distributionByType', { defaultValue: 'Distribución por Tipo' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-12" />
                </div>
                <Skeleton className="h-3 w-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card className={`h-full ${className || ""}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            {t('widgets.distributionByType', { defaultValue: 'Distribución por Tipo' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.loadError', { defaultValue: 'Error al cargar datos' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const { items, total } = data || { items: [], total: 0 };

  return (
    <Card className={`h-full ${className || ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            {t('widgets.distributionByType', { defaultValue: 'Distribución por Tipo' })}
          </CardTitle>
          <span className="text-sm text-muted-foreground">
            Total: {total}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <BarChart3 className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('widgets.noActiveRequests', { defaultValue: 'Sin solicitudes activas' })}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item, index) => (
              <DistributionBar
                key={`${item.workflow_code}-${item.solicitud_type}`}
                label={item.label}
                count={item.count}
                percentage={item.percentage}
                colorClass={BAR_COLORS[index % BAR_COLORS.length]}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// DISTRIBUTION BAR
// =============================================================================

interface DistributionBarProps {
  label: string;
  count: number;
  percentage: number;
  colorClass: string;
}

function DistributionBar({
  label,
  count,
  percentage,
  colorClass,
}: DistributionBarProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">
          {count} ({percentage}%)
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClass} rounded-full transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export default WorkflowDistributionWidget;
