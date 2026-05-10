'use client';

/**
 * Agent Dashboard - Main Entry Point
 * Redirects agents to their entity-specific dashboard or shows overview
 *
 * @route /[locale]/dashboard/agent
 * @date 2025-01-18
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useAgentDashboard } from '@/modules/agent-dashboard';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, AlertCircle, Building2, ArrowRight, Users, FileText, ClipboardList } from 'lucide-react';
import Link from 'next/link';

export default function AgentDashboardPage() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('agent');
  const tCommon = useTranslations('common');

  const {
    isLoading,
    isError,
    error,
    context,
    entityCode,
    getBasePath,
    isMinistryAgent,
    ministryEntities,
  } = useAgentDashboard();

  // Auto-redirect to entity dashboard if entity is known
  useEffect(() => {
    if (!isLoading && entityCode) {
      const targetPath = getBasePath();
      router.push(targetPath);
    }
  }, [isLoading, entityCode, getBasePath, locale, router]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">{tCommon('loading')}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (isError || !context) {
    return (
      <div className="space-y-6">
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              {t('errors.profileNotFound')}
            </CardTitle>
            <CardDescription>
              {t('errors.profileNotFoundDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {error?.message || t('errors.contactAdmin')}
            </p>
            <Button variant="outline" onClick={() => router.push(`/${locale}/auth/agent`)}>
              {t('actions.backToLogin')}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // If entity code is known, we're waiting for redirect
  if (entityCode) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">
            {t('redirecting', { entity: context.entityName || context.ministryName || '' })}
          </p>
        </div>
      </div>
    );
  }

  // Generic dashboard for agents without specific entity config
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('dashboard.title')}</h1>
        <p className="text-muted-foreground mt-1">
          {t('dashboard.welcome', { name: context.entityName || context.ministryName || '' })}
        </p>
      </div>

      {/* Agent Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            {t('profile.title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <p className="text-sm text-muted-foreground">{t('profile.entity')}</p>
              <p className="font-medium">{context.entityName || context.ministryName || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('profile.type')}</p>
              <p className="font-medium">
                {context.isSupervisor ? t('profile.supervisor') : t('profile.agent')}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Pending Tasks */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ClipboardList className="h-5 w-5 text-blue-500" />
              {t('quickActions.pendingTasks')}
            </CardTitle>
            <CardDescription>
              {t('quickActions.pendingTasksDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href={getBasePath()}>
              <Button className="w-full">
                {t('quickActions.viewTasks')}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Service Requests */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-green-500" />
              {t('quickActions.serviceRequests')}
            </CardTitle>
            <CardDescription>
              {t('quickActions.serviceRequestsDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href={`${getBasePath()}/requests`}>
              <Button variant="outline" className="w-full">
                {t('quickActions.viewRequests')}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Team (if supervisor) */}
        {context.isSupervisor && (
          <Card className="hover:shadow-md transition-shadow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-purple-500" />
                {t('quickActions.team')}
              </CardTitle>
              <CardDescription>
                {t('quickActions.teamDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link href={`${getBasePath()}/team`}>
                <Button variant="outline" className="w-full">
                  {t('quickActions.viewTeam')}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Ministry Entities (if ministry agent) */}
      {isMinistryAgent && ministryEntities.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t('ministryEntities.title')}</CardTitle>
            <CardDescription>{t('ministryEntities.description')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {ministryEntities.map((entity) => (
                <Link
                  key={entity}
                  href={`/${locale}/dashboard/agent/${entity.toLowerCase()}`}
                  className="block"
                >
                  <Card className="hover:shadow-md transition-shadow cursor-pointer">
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-3">
                        <Building2 className="h-8 w-8 text-primary" />
                        <div>
                          <p className="font-medium">{entity}</p>
                          <p className="text-sm text-muted-foreground">
                            {t('ministryEntities.viewDashboard')}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
