'use client';

/**
 * UserPermissionsTab Component
 * Individual user permission overrides (RBAC grants/denies per user)
 *
 * Extracted from monolithic roles/page.tsx for maintainability
 */

import { useState } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Shield,
  Plus,
  Loader2,
  AlertCircle,
  RefreshCw,
  Users,
} from 'lucide-react';
import {
  UserSelector,
  UserPermissionList,
  useUserPermissions,
} from '@/modules/user-permissions-admin';
import type { SimpleUser } from '@/modules/user-permissions-admin';

export function UserPermissionsTab() {
  const t = useTranslations('admin.userPermissions');
  const locale = useLocale();

  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<SimpleUser | null>(null);

  const { data: userPermissionsData, isLoading, error, refetch } = useUserPermissions(selectedUserId);

  const handleUserSelect = (userId: string | null, user: SimpleUser | null) => {
    setSelectedUserId(userId);
    setSelectedUser(user);
  };

  const grantPermissionUrl = selectedUser
    ? `/${locale}/dashboard/admin/roles/grant-permission?userId=${selectedUser.id}&userName=${encodeURIComponent(`${selectedUser.first_name} ${selectedUser.last_name}`)}&userEmail=${encodeURIComponent(selectedUser.email)}`
    : null;

  return (
    <div className="space-y-4">
      {/* Agent Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            {t('selectUser')}
          </CardTitle>
          <CardDescription>
            {t('selectUserDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex-1 max-w-md">
              <UserSelector
                value={selectedUserId}
                onValueChange={handleUserSelect}
                roleFilter="agent"
                placeholder={t('searchUsers')}
                searchPlaceholder={t('typeToSearch')}
                emptyLabel={t('noUsersFound')}
              />
            </div>
            {selectedUserId && (
              <Button
                variant="outline"
                size="icon"
                onClick={() => refetch()}
                disabled={isLoading}
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* User Permissions */}
      {selectedUserId && selectedUser && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  {t('permissionsFor', { name: `${selectedUser.first_name} ${selectedUser.last_name}` })}
                </CardTitle>
                <CardDescription className="flex items-center gap-2 mt-1">
                  <span>{selectedUser.email}</span>
                  <Badge variant="secondary">{selectedUser.role}</Badge>
                </CardDescription>
              </div>
              {grantPermissionUrl && (
                <Link href={grantPermissionUrl}>
                  <Button>
                    <Plus className="mr-2 h-4 w-4" />
                    {t('grantPermission')}
                  </Button>
                </Link>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="flex items-center gap-2 text-destructive py-8 justify-center">
                <AlertCircle className="h-5 w-5" />
                <span>{error instanceof Error ? error.message : 'Error'}</span>
              </div>
            ) : (
              <Tabs defaultValue="overrides">
                <TabsList>
                  <TabsTrigger value="overrides">
                    {t('overridesTab')}
                    {userPermissionsData?.user_permissions && (
                      <Badge variant="secondary" className="ml-2">
                        {userPermissionsData.user_permissions.length}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="effective">{t('effectiveTab')}</TabsTrigger>
                  <TabsTrigger value="role">{t('roleTab')}</TabsTrigger>
                </TabsList>

                <TabsContent value="overrides" className="mt-4">
                  <UserPermissionList
                    permissions={userPermissionsData?.user_permissions || []}
                    userId={selectedUserId}
                    isLoading={isLoading}
                    onRefresh={() => refetch()}
                  />
                </TabsContent>

                <TabsContent value="effective" className="mt-4">
                  {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <p className="text-sm text-muted-foreground">
                        {t('effectiveDescription')}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {userPermissionsData?.effective_permissions?.length ? (
                          userPermissionsData.effective_permissions.map((perm) => (
                            <Badge key={perm} variant="outline" className="text-xs">
                              {perm}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-muted-foreground">{t('noEffectivePermissions')}</span>
                        )}
                      </div>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="role" className="mt-4">
                  {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{t('roleLabel')}:</span>
                        <Badge variant="secondary">
                          {userPermissionsData?.role_name || selectedUser.role}
                        </Badge>
                      </div>
                      <Separator />
                      <p className="text-sm text-muted-foreground">
                        {t('rolePermissionsDescription')}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {userPermissionsData?.role_permissions?.length ? (
                          userPermissionsData.role_permissions.map((perm) => (
                            <Badge key={perm} variant="outline" className="text-xs">
                              {perm}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-muted-foreground">{t('noRolePermissions')}</span>
                        )}
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!selectedUserId && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <Users className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
              <p className="text-lg font-medium text-foreground">{t('selectUser')}</p>
              <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
                {t('selectUserDescription')}
              </p>
              <Separator className="my-6 max-w-xs mx-auto" />
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                {t('noOverridesHint')}
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
