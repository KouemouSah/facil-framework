/**
 * Access Denied Component
 * Displayed when an agent tries to access an entity dashboard they don't have access to
 *
 * @module agent-dashboard/components
 * @date 2026-01-18
 */

'use client';

import { useTranslations } from 'next-intl';
import { useRouter, usePathname } from 'next/navigation';
import { useLocale } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ShieldX, ArrowLeft, Home } from 'lucide-react';
import type { EntityCode } from '../types';

// =============================================================================
// PROPS
// =============================================================================

interface AccessDeniedProps {
  /** The entity the user tried to access */
  requestedEntity: EntityCode;
  /** The user's actual assigned entity */
  userEntity: EntityCode | null;
  /** List of entities the user can access */
  allowedEntities: EntityCode[];
  /** Additional class name */
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function AccessDenied({
  requestedEntity,
  userEntity,
  allowedEntities,
  className,
}: AccessDeniedProps) {
  const t = useTranslations('agent');
  const tCommon = useTranslations('common');
  const locale = useLocale();
  const router = useRouter();
  const _pathname = usePathname();

  // Determine redirect URL based on user's entity
  const getRedirectUrl = (): string => {
    if (allowedEntities.length > 0) {
      // Redirect to first allowed entity
      const firstEntity = allowedEntities[0];
      const entityPath = firstEntity.toLowerCase().replace('_', '-');
      return `/${locale}/dashboard/agent/${entityPath}`;
    }
    // Fallback to main agent dashboard
    return `/${locale}/dashboard/agent`;
  };

  const handleGoBack = () => {
    router.back();
  };

  const handleGoHome = () => {
    router.push(getRedirectUrl());
  };

  return (
    <div className={`flex items-center justify-center min-h-[60vh] ${className || ''}`}>
      <Card className="max-w-md w-full border-red-200 bg-red-50/50">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
            <ShieldX className="h-8 w-8 text-red-600" />
          </div>
          <CardTitle className="text-xl text-red-800">
            {t('accessDenied.title')}
          </CardTitle>
          <CardDescription className="text-red-700">
            {t('accessDenied.description')}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Details */}
          <div className="rounded-lg bg-white/80 p-4 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">
                {t('accessDenied.requestedEntity')}:
              </span>
              <span className="font-medium text-red-700">{requestedEntity}</span>
            </div>
            {userEntity && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">
                  {t('accessDenied.yourEntity')}:
                </span>
                <span className="font-medium text-green-700">{userEntity}</span>
              </div>
            )}
            {allowedEntities.length > 0 && (
              <div className="pt-2 border-t">
                <span className="text-muted-foreground text-xs">
                  {t('accessDenied.allowedEntities')}:
                </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {allowedEntities.map((entity) => (
                    <span
                      key={entity}
                      className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800"
                    >
                      {entity}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Help text */}
          <p className="text-xs text-center text-muted-foreground">
            {t('accessDenied.helpText')}
          </p>

          {/* Actions */}
          <div className="flex flex-col gap-2">
            <Button
              onClick={handleGoHome}
              className="w-full"
              variant="default"
            >
              <Home className="mr-2 h-4 w-4" />
              {t('accessDenied.goToMyDashboard')}
            </Button>
            <Button
              onClick={handleGoBack}
              variant="outline"
              className="w-full"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              {tCommon('goBack')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default AccessDenied;
