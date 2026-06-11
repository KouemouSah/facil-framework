'use client';

/**
 * Roles & Permissions Admin Page
 * Unified management of roles, permissions catalog, and user overrides
 *
 * Split into 3 tab components for maintainability:
 * - RolesTab: CRUD for custom roles with permission assignment
 * - PermissionsCatalogTab: Read-only view of all system permissions
 * - UserPermissionsTab: Individual user permission overrides
 */

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Shield, Key, Users, Zap } from 'lucide-react';
import { RolesTab, PermissionsCatalogTab, UserPermissionsTab, PermissionSimulatorTab } from '@/modules/roles-admin';

const VALID_TABS = ['roles', 'permissions', 'user-permissions', 'simulator'] as const;

export default function RolesPermissionsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = useLocale();
  const t = useTranslations('admin.roles');

  const tabParam = searchParams.get('tab');
  const initialTab = VALID_TABS.includes(tabParam as typeof VALID_TABS[number]) ? tabParam! : 'roles';
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    if (tabParam && VALID_TABS.includes(tabParam as typeof VALID_TABS[number]) && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabParam]);

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    router.push(`/${locale}/dashboard/admin/roles?tab=${value}`, { scroll: false });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Shield className="h-8 w-8" />
            {t('pageTitle')}
          </h1>
          <p className="text-muted-foreground mt-2">
            {t('pageSubtitle')}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="roles" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            {t('tabRoles')}
          </TabsTrigger>
          <TabsTrigger value="permissions" className="flex items-center gap-2">
            <Key className="h-4 w-4" />
            {t('tabPermissions')}
          </TabsTrigger>
          <TabsTrigger value="user-permissions" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            {t('tabUserPermissions')}
          </TabsTrigger>
          <TabsTrigger value="simulator" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Simulador
          </TabsTrigger>
        </TabsList>

        <TabsContent value="roles" className="mt-6">
          <RolesTab />
        </TabsContent>

        <TabsContent value="permissions" className="mt-6">
          <PermissionsCatalogTab />
        </TabsContent>

        <TabsContent value="user-permissions" className="mt-6">
          <UserPermissionsTab />
        </TabsContent>

        <TabsContent value="simulator" className="mt-6">
          <PermissionSimulatorTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
