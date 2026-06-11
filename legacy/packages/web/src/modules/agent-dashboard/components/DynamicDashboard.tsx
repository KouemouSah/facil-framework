/**
 * DynamicDashboard Component
 *
 * Renders dynamic dashboard widgets based on configuration from backend API.
 * Supports grid, list, and custom layouts with configurable widget sizes.
 *
 * @module agent-dashboard/components
 * @date 2026-01-19
 */

'use client';

import React, { useMemo } from 'react';
import { useTranslations } from 'next-intl';
import { cn } from '@/core/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Clock,
  CheckCircle,
  Loader2,
  TrendingUp,
  Activity,
  FileText,
  CreditCard,
  BarChart3,
  Download,
  ShieldAlert,
  History,
  type LucideIcon,
} from 'lucide-react';
import type { DashboardConfig, WidgetConfig, WidgetSize } from '../types/menu-config';

// =============================================================================
// PROPS INTERFACE
// =============================================================================

interface DynamicDashboardProps {
  /** Dashboard configuration from API */
  config: DashboardConfig;
  /** Widget data (key = widget id, value = widget data) */
  widgetData?: Record<string, WidgetData>;
  /** Loading state */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Custom widget renderer */
  renderWidget?: (widget: WidgetConfig, data?: WidgetData) => React.ReactNode;
}

interface WidgetData {
  value?: number | string;
  label?: string;
  trend?: number;
  status?: 'success' | 'warning' | 'error' | 'info';
  items?: Array<{ id: string; label: string; value: string | number }>;
}

// =============================================================================
// WIDGET ICON MAP
// =============================================================================

const WIDGET_ICONS: Record<string, LucideIcon> = {
  pending_requests: Clock,
  pending_payments: Clock,
  in_progress: Loader2,
  in_progress_payments: Loader2,
  completed_today: CheckCircle,
  completed_payments: CheckCircle,
  total_amount_today: CreditCard,
  recent_activity: History,
  performance_chart: BarChart3,
  anomaly_alerts: ShieldAlert,
  stats_card: TrendingUp,
  stats: TrendingUp,
  analytics: Activity,
  audit: FileText,
  exports: Download,
};

// =============================================================================
// SIZE CLASSES
// =============================================================================

const SIZE_CLASSES: Record<WidgetSize, string> = {
  small: 'col-span-1',
  medium: 'col-span-1 md:col-span-2',
  large: 'col-span-1 md:col-span-2 lg:col-span-3',
  full: 'col-span-full',
};

const SIZE_MIN_HEIGHT: Record<WidgetSize, string> = {
  small: 'min-h-[120px]',
  medium: 'min-h-[180px]',
  large: 'min-h-[240px]',
  full: 'min-h-[300px]',
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function DynamicDashboard({
  config,
  widgetData = {},
  isLoading = false,
  className,
  renderWidget,
}: DynamicDashboardProps) {
  const t = useTranslations('agent');

  // Sort widgets by position and filter visible ones
  const sortedWidgets = useMemo(() => {
    return config.widgets
      .filter((widget) => widget.visible)
      .sort((a, b) => a.position - b.position);
  }, [config.widgets]);

  // Layout classes based on config
  const layoutClasses = useMemo(() => {
    switch (config.layout) {
      case 'list':
        return 'flex flex-col gap-4';
      case 'custom':
        return 'grid gap-4'; // Custom layout uses CSS Grid with custom positioning
      case 'grid':
      default:
        return 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4';
    }
  }, [config.layout]);

  if (!sortedWidgets.length) {
    return (
      <div className={cn('text-center py-8 text-muted-foreground', className)}>
        {t('dashboard.noWidgets')}
      </div>
    );
  }

  return (
    <div className={cn(layoutClasses, className)}>
      {sortedWidgets.map((widget) => {
        const data = widgetData[widget.id];

        // Use custom renderer if provided
        if (renderWidget) {
          const customWidget = renderWidget(widget, data);
          if (customWidget) {
            return (
              <div key={widget.id} className={cn(SIZE_CLASSES[widget.size], 'h-full')}>
                {customWidget}
              </div>
            );
          }
        }

        // Default widget rendering
        return (
          <DefaultWidget
            key={widget.id}
            widget={widget}
            data={data}
            isLoading={isLoading}
          />
        );
      })}
    </div>
  );
}

// =============================================================================
// DEFAULT WIDGET COMPONENT
// =============================================================================

interface DefaultWidgetProps {
  widget: WidgetConfig;
  data?: WidgetData;
  isLoading?: boolean;
}

function DefaultWidget({ widget, data, isLoading }: DefaultWidgetProps) {
  const t = useTranslations('agent');
  const Icon = WIDGET_ICONS[widget.id] || FileText;

  // Get translated title
  const getTitle = (): string => {
    try {
      return t(`dashboard.widgets.${widget.id}`);
    } catch {
      // Fallback: convert widget id to readable format
      return widget.id
        .split('_')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    }
  };

  // Determine status color
  const getStatusColor = (status?: string): string => {
    switch (status) {
      case 'success':
        return 'text-green-600';
      case 'warning':
        return 'text-yellow-600';
      case 'error':
        return 'text-red-600';
      case 'info':
      default:
        return 'text-blue-600';
    }
  };

  return (
    <Card
      className={cn(
        SIZE_CLASSES[widget.size],
        SIZE_MIN_HEIGHT[widget.size],
        'transition-shadow hover:shadow-md'
      )}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{getTitle()}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <WidgetSkeleton size={widget.size} />
        ) : (
          <WidgetContent widget={widget} data={data} getStatusColor={getStatusColor} />
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// WIDGET CONTENT
// =============================================================================

interface WidgetContentProps {
  widget: WidgetConfig;
  data?: WidgetData;
  getStatusColor: (status?: string) => string;
}

function WidgetContent({ widget, data, getStatusColor }: WidgetContentProps) {
  const t = useTranslations('agent');

  if (!data) {
    return (
      <div className="text-2xl font-bold text-muted-foreground">--</div>
    );
  }

  // Small widget: just show value
  if (widget.size === 'small') {
    return (
      <div className="space-y-1">
        <div className={cn('text-2xl font-bold', getStatusColor(data.status))}>
          {data.value ?? '--'}
        </div>
        {data.label && (
          <p className="text-xs text-muted-foreground">{data.label}</p>
        )}
        {data.trend !== undefined && (
          <TrendIndicator value={data.trend} />
        )}
      </div>
    );
  }

  // Medium/Large widgets: show value + items list
  return (
    <div className="space-y-3">
      {data.value !== undefined && (
        <div className={cn('text-2xl font-bold', getStatusColor(data.status))}>
          {data.value}
        </div>
      )}
      {data.label && (
        <p className="text-sm text-muted-foreground">{data.label}</p>
      )}
      {data.trend !== undefined && (
        <TrendIndicator value={data.trend} />
      )}
      {data.items && data.items.length > 0 && (
        <div className="space-y-2 pt-2 border-t">
          {data.items.slice(0, widget.size === 'large' ? 10 : 5).map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-muted-foreground truncate">{item.label}</span>
              <span className="font-medium">{item.value}</span>
            </div>
          ))}
          {data.items.length > (widget.size === 'large' ? 10 : 5) && (
            <p className="text-xs text-muted-foreground text-center pt-1">
              {t('dashboard.moreItems', { count: data.items.length - (widget.size === 'large' ? 10 : 5) })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// TREND INDICATOR
// =============================================================================

interface TrendIndicatorProps {
  value: number;
}

function TrendIndicator({ value }: TrendIndicatorProps) {
  const isPositive = value >= 0;

  return (
    <div
      className={cn(
        'flex items-center text-xs',
        isPositive ? 'text-green-600' : 'text-red-600'
      )}
    >
      <TrendingUp
        className={cn('h-3 w-3 mr-1', !isPositive && 'rotate-180')}
      />
      <span>
        {isPositive ? '+' : ''}
        {value}%
      </span>
    </div>
  );
}

// =============================================================================
// WIDGET SKELETON
// =============================================================================

interface WidgetSkeletonProps {
  size: WidgetSize;
}

function WidgetSkeleton({ size }: WidgetSkeletonProps) {
  return (
    <div className="space-y-2 animate-pulse">
      <div className="h-8 w-16 bg-muted rounded" />
      {size !== 'small' && (
        <>
          <div className="h-4 w-24 bg-muted rounded" />
          {(size === 'large' || size === 'full') && (
            <div className="space-y-2 pt-2">
              <div className="h-3 w-full bg-muted rounded" />
              <div className="h-3 w-3/4 bg-muted rounded" />
              <div className="h-3 w-1/2 bg-muted rounded" />
            </div>
          )}
        </>
      )}
    </div>
  );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default DynamicDashboard;

export type { DynamicDashboardProps, WidgetData };
