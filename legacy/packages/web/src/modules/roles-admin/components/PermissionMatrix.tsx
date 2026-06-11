'use client';

/**
 * PermissionMatrix Component
 * Visual grid: roles (columns) × permissions (rows) with checkboxes
 *
 * Features:
 * - Module filter (required — prevents 5000+ cell grids)
 * - Scrollable table with sticky headers
 * - Batch toggle per role (column) or permission (row)
 * - Critical permission visual indicator
 */

import { useState, useMemo, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Grid3X3,
  Loader2,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  usePermissionMatrix,
  useAssignPermissions,
  useRemovePermissions,
} from '@/modules/roles-admin';
import { useModuleNames } from '@/modules/permissions-admin';

export function PermissionMatrix() {
  const t = useTranslations('admin.roles');
  const tPerm = useTranslations('admin.permissions');
  const moduleNames = useModuleNames();

  const [selectedModule, setSelectedModule] = useState<string>(moduleNames[0] || '');

  const { data: matrix, isLoading, error, refetch } = usePermissionMatrix(
    selectedModule || undefined
  );

  const assignMutation = useAssignPermissions();
  const removeMutation = useRemovePermissions();

  const isMutating = assignMutation.isPending || removeMutation.isPending;

  // Check if a role has a specific permission
  const hasPermission = useCallback((roleId: string, permId: string): boolean => {
    if (!matrix) return false;
    return matrix.assignments[`${roleId}:${permId}`] === true;
  }, [matrix]);

  // Toggle a single cell
  const handleToggle = useCallback(async (roleId: string, permId: string, currentlyGranted: boolean) => {
    try {
      if (currentlyGranted) {
        await removeMutation.mutateAsync({
          roleId,
          data: { permission_ids: [permId] },
        });
      } else {
        await assignMutation.mutateAsync({
          roleId,
          data: { permission_ids: [permId], granted: true },
        });
      }
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Error');
    }
  }, [assignMutation, removeMutation, refetch]);

  // Toggle entire column (all permissions for a role)
  const handleToggleColumn = useCallback(async (roleId: string) => {
    if (!matrix) return;
    const allGranted = matrix.permissions.every(p => hasPermission(roleId, p.id));
    try {
      if (allGranted) {
        // Remove all
        await removeMutation.mutateAsync({
          roleId,
          data: { permission_ids: matrix.permissions.map(p => p.id) },
        });
      } else {
        // Grant all missing
        const missingIds = matrix.permissions
          .filter(p => !hasPermission(roleId, p.id))
          .map(p => p.id);
        if (missingIds.length > 0) {
          await assignMutation.mutateAsync({
            roleId,
            data: { permission_ids: missingIds, granted: true },
          });
        }
      }
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Error');
    }
  }, [matrix, hasPermission, assignMutation, removeMutation, refetch]);

  // Count granted permissions per role for this module
  const roleGrantCounts = useMemo(() => {
    if (!matrix) return {};
    const counts: Record<string, number> = {};
    for (const role of matrix.roles) {
      counts[role.id] = matrix.permissions.filter(p =>
        hasPermission(role.id, p.id)
      ).length;
    }
    return counts;
  }, [matrix, hasPermission]);

  if (!selectedModule && moduleNames.length > 0) {
    setSelectedModule(moduleNames[0]);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Grid3X3 className="h-5 w-5" />
              {t('permissionsTab')} — Matrix
            </CardTitle>
            <CardDescription>
              {matrix
                ? `${matrix.roles.length} roles × ${matrix.permissions.length} permissions`
                : tPerm('filterDesc')}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Select value={selectedModule} onValueChange={setSelectedModule}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder={tPerm('module')} />
              </SelectTrigger>
              <SelectContent>
                {moduleNames.map((mod) => (
                  <SelectItem key={mod} value={mod}>
                    {mod}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" onClick={() => refetch()} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-destructive py-8 justify-center">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : 'Error'}</span>
          </div>
        )}

        {matrix && !isLoading && (
          <TooltipProvider delayDuration={200}>
            <div className="overflow-auto max-h-[70vh] border rounded-md">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-background">
                  <tr className="border-b">
                    <th className="sticky left-0 z-20 bg-muted/80 backdrop-blur-sm px-3 py-2 text-left font-medium min-w-[200px]">
                      Permission
                    </th>
                    {matrix.roles.map((role) => (
                      <th key={role.id} className="px-2 py-2 text-center min-w-[80px]">
                        <div className="flex flex-col items-center gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                className="text-xs font-medium hover:text-primary truncate max-w-[80px]"
                                onClick={() => handleToggleColumn(role.id)}
                                disabled={isMutating}
                              >
                                {role.code}
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="font-medium">{role.name}</p>
                              <p className="text-xs">{roleGrantCounts[role.id] || 0}/{matrix.permissions.length}</p>
                            </TooltipContent>
                          </Tooltip>
                          <Badge variant="outline" className="text-[10px] px-1 py-0">
                            {roleGrantCounts[role.id] || 0}
                          </Badge>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix.permissions.map((perm) => (
                    <tr key={perm.id} className="border-b hover:bg-muted/30">
                      <td className="sticky left-0 z-10 bg-background px-3 py-1.5 border-r">
                        <div className="flex items-center gap-2">
                          {perm.is_critical && (
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
                          )}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="font-mono text-xs truncate max-w-[180px] cursor-help">
                                {perm.name}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent side="right" className="max-w-xs">
                              <p className="font-medium">{perm.name}</p>
                              {perm.description && (
                                <p className="text-xs text-muted-foreground">{perm.description}</p>
                              )}
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      </td>
                      {matrix.roles.map((role) => {
                        const granted = hasPermission(role.id, perm.id);
                        return (
                          <td key={role.id} className="px-2 py-1.5 text-center">
                            <Checkbox
                              checked={granted}
                              onCheckedChange={() => handleToggle(role.id, perm.id, granted)}
                              disabled={isMutating}
                              className="mx-auto"
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TooltipProvider>
        )}

        {matrix && matrix.permissions.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            {tPerm('noPermissions')}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
