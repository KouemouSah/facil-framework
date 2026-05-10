/**
 * Generic Entity Dashboard Component
 * Reusable dashboard for any entity type
 *
 * @module agent-dashboard/components
 * @date 2026-01-18
 *
 * Security: Includes entity access verification to prevent unauthorized access
 */

'use client';

import { useTranslations } from 'next-intl';
import Link from 'next/link';
// useLocale removed - hrefs are already locale-prefixed by useAgentDashboard hook
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  Clock,
  Loader2,
  AlertCircle,
  CheckCircle,
  Users,
  BarChart3,
  ClipboardList,
  History,
  Calendar,
  Car,
  Globe,
  FileSignature,
  Plane,
  Truck,
  BadgeCheck,
  Briefcase,
  FileText,
  LayoutDashboard,
  MapPin,
} from 'lucide-react';
import { useAgentDashboard, useEntityAccess, useMenuConfig } from '../hooks';
import { useEntityStats } from '../hooks/useEntityStats';
import { AccessDenied } from './AccessDenied';
import { DynamicDashboard } from './DynamicDashboard';
import { renderWidget, DEFAULT_ENTITY_WIDGETS } from './widgets';
import type { EntityCode, MenuItem } from '../types';
import { isMenuGroup } from '../types';
import type { DashboardConfig } from '../types/menu-config';
import { isDynamicMenuGroup } from '../types/menu-config';

// =============================================================================
// PROPS
// =============================================================================

interface GenericEntityDashboardProps {
  /** The entity code for this dashboard */
  entityCode: EntityCode;
  /** Optional: Custom stats component */
  statsComponent?: React.ReactNode;
  /** Optional: Additional class name */
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function GenericEntityDashboard({
  entityCode,
  statsComponent,
  className,
}: GenericEntityDashboardProps) {
  const t = useTranslations('agent');

  // Entity access verification (security check)
  const {
    hasAccess,
    isLoading: accessLoading,
    agentEntityCode,
    allowedEntities,
  } = useEntityAccess(entityCode);

  const {
    isLoading: dashboardLoading,
    isError,
    error,
    context,
    entityName: hookEntityName,
    entityIcon: hookEntityIcon,
    menuItems,
    dynamicMenuItems,
    useDynamicMenus,
    getBasePath,
  } = useAgentDashboard();

  const { isLoading: statsLoading, stats } = useEntityStats(entityCode);

  // Get dashboard_config for widgets from dynamic menu config
  const { dashboardConfig, isLoading: menuConfigLoading } = useMenuConfig();

  const isLoading = accessLoading || dashboardLoading || menuConfigLoading;

  // Determine which widget config to use: from API or default
  const widgetConfig: DashboardConfig = dashboardConfig || {
    version: '1.0',
    layout: 'grid',
    widgets: DEFAULT_ENTITY_WIDGETS,
  };

  // Loading state
  if (isLoading) {
    return (
      <div className={`space-y-6 ${className || ''}`}>
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Access denied state (security check)
  if (!hasAccess) {
    return (
      <AccessDenied
        requestedEntity={entityCode}
        userEntity={agentEntityCode}
        allowedEntities={allowedEntities}
        className={className}
      />
    );
  }

  // Error state
  if (isError || !context) {
    return (
      <div className={`space-y-6 ${className || ''}`}>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">
              {error?.message || t('errors.loadingFailed')}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Entity metadata from backend API (100% dynamic)
  const displayName = hookEntityName || entityCode || 'Agent';

  // Translate i18n keys for dynamic menu titles
  const getTitle = (titleKey: string): string => {
    try {
      return t(titleKey.replace('agent.', '')) || titleKey;
    } catch {
      const parts = titleKey.split('.');
      return parts[parts.length - 1];
    }
  };

  // Icon mapping for entity icon (string → Lucide component)
  const entityIconMap: Record<string, typeof Clock> = {
    Plane, Car, Globe, FileSignature, Truck, BadgeCheck, Briefcase, FileText, LayoutDashboard,
  };
  const EntityIcon = entityIconMap[hookEntityIcon || ''] || FileText;

  // Icon mapping for dynamic menu items (string icon names to Lucide components)
  const iconMap: Record<string, typeof Clock> = {
    Clock,
    CheckCircle,
    History,
    BarChart3,
    ClipboardList,
    AlertCircle,
    Users,
    Calendar,
    Car,
    Globe,
    FileSignature,
    Plane,
    Truck,
    BadgeCheck,
    FileText,
    LayoutDashboard,
  };

  // Extract quick actions - USE DYNAMIC MENUS if available
  const displayActions = (() => {
    // Priority 1: Dynamic menus from API (workflow-based entities with auto-generation)
    if (useDynamicMenus && dynamicMenuItems.length > 0) {
      const dynamicGroupActions: Array<{
        id: string;
        titleKey: string;
        href: string;
        icon: typeof Clock;
      }> = [];

      // Extract sub-menu actions from dynamic menu groups
      for (const item of dynamicMenuItems) {
        if (isDynamicMenuGroup(item)) {
          // Take first 2 items from each group, max 6 total
          const groupItems = item.items.slice(0, 2).map((subItem) => ({
            id: subItem.id,
            titleKey: subItem.titleKey,
            href: subItem.href,
            icon: iconMap[subItem.icon] || Clock,
          }));
          dynamicGroupActions.push(...groupItems);
          if (dynamicGroupActions.length >= 6) break;
        }
      }

      if (dynamicGroupActions.length > 0) {
        return dynamicGroupActions.slice(0, 6);
      }

      // Fallback: top-level items with href (excluding dashboard)
      const dynamicQuickActions = dynamicMenuItems
        .filter((item) => !isDynamicMenuGroup(item) && item.href && item.id !== 'dashboard')
        .slice(0, 3)
        .map((item) => ({
          id: item.id,
          titleKey: item.titleKey,
          href: item.href!,
          icon: iconMap[item.icon] || Clock,
        }));

      if (dynamicQuickActions.length > 0) {
        return dynamicQuickActions;
      }
    }

    // Priority 2: Static menus (legacy/fallback)
    const quickActions = menuItems
      .filter((item) => !isMenuGroup(item) && 'href' in item && item.id !== 'dashboard')
      .slice(0, 3) as (MenuItem & { href: string })[];

    const groupActions = menuItems
      .filter(isMenuGroup)
      .flatMap((group) => group.items.slice(0, 2))
      .slice(0, 6);

    if (groupActions.length > 0) {
      return groupActions;
    }
    if (quickActions.length > 0) {
      return quickActions;
    }

    // Priority 3: Default actions using dynamic basePath
    const basePath = getBasePath();
    return [
      {
        id: 'default-pending',
        titleKey: 'agent.nav.pending',
        href: `${basePath}/pending`,
        icon: Clock,
      },
      {
        id: 'default-validation',
        titleKey: 'agent.nav.validation',
        href: `${basePath}/validation`,
        icon: CheckCircle,
      },
      {
        id: 'default-history',
        titleKey: 'agent.nav.history',
        href: `${basePath}/history`,
        icon: History,
      },
    ];
  })();

  return (
    <div className={`space-y-6 ${className || ''}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <EntityIcon className="h-8 w-8 text-primary" />
            {displayName}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('dashboard.welcome', { name: context.entityName || context.ministryName || entityCode })}
          </p>
        </div>
        {context.locationName && (
          <Badge variant="outline" className="flex items-center gap-1.5 px-3 py-1.5 text-sm self-start">
            <MapPin className="h-3.5 w-3.5" />
            {context.locationName}
          </Badge>
        )}
      </div>

      {/* Quick Actions - Compact button row */}
      {displayActions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {displayActions.map((action) => {
            const ActionIcon = action.icon;
            return (
              <Link key={action.id} href={action.href}>
                <Button variant="outline" size="sm" className="gap-1.5">
                  <ActionIcon className="h-4 w-4" />
                  {getTitle(action.titleKey)}
                </Button>
              </Link>
            );
          })}
        </div>
      )}

      {/* Stats Cards - Custom or Default */}
      {statsComponent || (
        <div className="grid gap-3 grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
          {/* Pending */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {t('stats.pending')}
              </CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stats.pendingCount}</div>
                  <p className="text-xs text-muted-foreground">
                    {t('stats.awaitingReview')}
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* In Progress */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {t('stats.inProgress')}
              </CardTitle>
              <ClipboardList className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stats.inProgressCount}</div>
                  <p className="text-xs text-muted-foreground">
                    {t('stats.beingProcessed')}
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* Completed Today */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {t('stats.completedToday')}
              </CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stats.completedTodayCount}</div>
                  <p className="text-xs text-muted-foreground">
                    {t('stats.processedToday')}
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* SLA Violations */}
          <Card className={stats.slaViolationsCount > 0 ? 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {t('stats.slaViolations')}
              </CardTitle>
              <AlertCircle className={`h-4 w-4 ${stats.slaViolationsCount > 0 ? 'text-red-500' : 'text-muted-foreground'}`} />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <>
                  <div className={`text-2xl font-bold ${stats.slaViolationsCount > 0 ? 'text-red-600 dark:text-red-400' : ''}`}>
                    {stats.slaViolationsCount}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('stats.slaExceeded')}
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* Escalated */}
          <Card className={stats.escalatedCount > 0 ? 'border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {t('stats.escalated')}
              </CardTitle>
              <AlertCircle className={`h-4 w-4 ${stats.escalatedCount > 0 ? 'text-amber-500' : 'text-muted-foreground'}`} />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <>
                  <div className={`text-2xl font-bold ${stats.escalatedCount > 0 ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                    {stats.escalatedCount}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('stats.pendingEscalation')}
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Dynamic Widgets Section */}
      {widgetConfig.widgets.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">{t('dashboard.widgets')}</h2>
          <DynamicDashboard
            config={widgetConfig}
            renderWidget={(widget) => renderWidget(widget.id, entityCode, widget)}
          />
        </div>
      )}


      {/* Agent Info */}
      {context.isSupervisor && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              {t('profile.supervisorAccess')}
            </CardTitle>
            <CardDescription>
              {t('profile.supervisorDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {t('profile.fullAccessMessage')}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default GenericEntityDashboard;
