/**
 * PersonalStatsWidget
 * Displays personal performance statistics for the current agent
 * Uses v_agent_performance_summary database view
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-01-26
 */

'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import {
  TrendingUp,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Target,
} from 'lucide-react';
import { useTranslations } from 'next-intl';
import { usePersonalStats } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface PersonalStatsWidgetProps {
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function PersonalStatsWidget({ className }: PersonalStatsWidgetProps) {
  const t = useTranslations('agent');
  const { data, isLoading, isError } = usePersonalStats();

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-600" />
            {t('widgets.personalStats', { defaultValue: 'Mis Estadísticas' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-600" />
            {t('widgets.personalStats', { defaultValue: 'Mis Estadísticas' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.statsError', { defaultValue: 'Error al cargar estadísticas' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const stats = data?.stats || {
    current_month_processed: 0,
    current_month_approved: 0,
    current_month_rejected: 0,
    sla_respect_percentage: null,
    approval_rate: null,
    avg_processing_minutes: null,
  };

  const slaPercentage = stats.sla_respect_percentage ?? 0;
  const approvalRate = stats.approval_rate ?? 0;

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-600" />
            {t('widgets.personalStats', { defaultValue: 'Mis Estadísticas' })}
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {data?.period_label || t('widgets.thisMonth', { defaultValue: 'Este mes' })}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Main Stats Grid */}
          <div className="grid grid-cols-2 gap-4">
            {/* Processed */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Target className="h-4 w-4" />
                {t('widgets.processed', { defaultValue: 'Procesadas' })}
              </div>
              <p className="text-2xl font-bold">
                {stats.current_month_processed}
              </p>
            </div>

            {/* Approved */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <CheckCircle className="h-4 w-4 text-green-600" />
                {t('widgets.approved', { defaultValue: 'Aprobadas' })}
              </div>
              <p className="text-2xl font-bold text-green-600">
                {stats.current_month_approved}
              </p>
            </div>

            {/* Rejected */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <XCircle className="h-4 w-4 text-red-600" />
                {t('widgets.rejected', { defaultValue: 'Rechazadas' })}
              </div>
              <p className="text-2xl font-bold text-red-600">
                {stats.current_month_rejected}
              </p>
            </div>

            {/* Avg Time */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Clock className="h-4 w-4" />
                {t('widgets.avgTime', { defaultValue: 'Tiempo Prom.' })}
              </div>
              <p className="text-2xl font-bold">
                {stats.avg_processing_minutes
                  ? `${Math.round(stats.avg_processing_minutes)}m`
                  : '--'}
              </p>
            </div>
          </div>

          {/* SLA Compliance */}
          <div className="space-y-2 pt-2 border-t">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <AlertTriangle className={`h-4 w-4 ${
                  slaPercentage >= 90 ? 'text-green-600' :
                  slaPercentage >= 70 ? 'text-yellow-600' : 'text-red-600'
                }`} />
                {t('widgets.slaCompliance', { defaultValue: 'Cumplimiento SLA' })}
              </span>
              <span className="font-medium">
                {slaPercentage.toFixed(1)}%
              </span>
            </div>
            <Progress
              value={slaPercentage}
              className={`h-2 ${
                slaPercentage >= 90 ? '[&>div]:bg-green-600' :
                slaPercentage >= 70 ? '[&>div]:bg-yellow-600' : '[&>div]:bg-red-600'
              }`}
            />
          </div>

          {/* Approval Rate */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-blue-600" />
                {t('widgets.approvalRate', { defaultValue: 'Tasa de Aprobación' })}
              </span>
              <span className="font-medium">
                {approvalRate.toFixed(1)}%
              </span>
            </div>
            <Progress
              value={approvalRate}
              className="h-2 [&>div]:bg-blue-600"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default PersonalStatsWidget;
