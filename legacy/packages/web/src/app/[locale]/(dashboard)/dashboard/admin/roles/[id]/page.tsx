'use client';

/**
 * Edit Role Page
 * Dedicated page for viewing and editing a role with its permissions
 *
 * @module dashboard/admin/roles/[id]
 * @date 2025-01-14
 * @updated 2026-01-19 - Added collapsible modules, instant checkbox toggle, optimistic updates
 */

import { useState, useMemo, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Shield,
  ArrowLeft,
  Loader2,
  Key,
  Search,
  AlertCircle,
  Lock,
  Trash2,
  Building2,
  Save,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  CheckSquare,
  Square,
  Check,
  X,
  Menu,
} from 'lucide-react';
import { toast } from 'sonner';

import {
  useRoles,
  useRoleWithPermissions,
  useUpdateRole,
  useDeleteRole,
  useAssignPermissions,
  useRemovePermissions,
} from '@/modules/roles-admin';
import type { UpdateRoleRequest, Role } from '@/modules/roles-admin';
import { usePermissions, useModuleNames } from '@/modules/permissions-admin';
import type { Permission } from '@/modules/permissions-admin';

export default function EditRolePage() {
  const router = useRouter();
  const params = useParams();
  const locale = useLocale();
  const roleId = params.id as string;

  // Note: t and tPerm kept for future i18n
  const _t = useTranslations('admin.roles');
  const _tPerm = useTranslations('admin.permissions');

  // Fetch all roles for navigation
  const { data: allRolesData, isLoading: rolesListLoading, error: rolesListError } = useRoles({ page_size: 100 });

  // Debug: Log navigation data issues
  if (typeof window !== 'undefined' && rolesListError) {
    console.error('[RoleEdit] Failed to load roles list for navigation:', rolesListError);
  }

  // Fetch role with permissions
  const {
    data: role,
    isLoading: roleLoading,
    error: roleError,
    refetch: refetchRole,
  } = useRoleWithPermissions(roleId);

  // Navigation between roles
  const navigationData = useMemo(() => {
    const roles = (allRolesData?.roles || []) as Role[];
    if (roles.length === 0) return { prev: null, next: null, currentIndex: -1, total: 0 };

    const currentIndex = roles.findIndex((r) => r.id === roleId);
    const prevRole = currentIndex > 0 ? roles[currentIndex - 1] : null;
    const nextRole = currentIndex < roles.length - 1 ? roles[currentIndex + 1] : null;

    return {
      prev: prevRole,
      next: nextRole,
      currentIndex,
      total: roles.length,
    };
  }, [allRolesData, roleId]);

  const navigateToRole = useCallback((targetRoleId: string) => {
    // Reset form state when navigating
    setFormInitialized(false);
    setExpandedModules(new Set());
    setPendingChanges(new Map());
    router.push(`/${locale}/dashboard/admin/roles/${targetRoleId}`);
  }, [router, locale]);

  // Form state
  const [formData, setFormData] = useState<UpdateRoleRequest>({
    name: '',
    description: '',
  });
  const [formInitialized, setFormInitialized] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [permissionSearch, setPermissionSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState<string>('all');

  // Collapsible modules state - all collapsed by default
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());

  // Optimistic state for instant UI feedback
  const [pendingChanges, setPendingChanges] = useState<Map<string, boolean>>(new Map());

  // Mutations
  const updateMutation = useUpdateRole();
  const deleteMutation = useDeleteRole();
  const assignMutation = useAssignPermissions();
  const removeMutation = useRemovePermissions();

  // Fetch all permissions
  const { data: allPermissions = [], isLoading: permissionsLoading } = usePermissions({
    module_name: moduleFilter === 'all' ? undefined : moduleFilter,
    search: permissionSearch || undefined,
  });
  const modules = useModuleNames();

  // Initialize form when role data loads
  if (role && !formInitialized) {
    setFormData({
      name: role.name,
      description: role.description || '',
    });
    setFormInitialized(true);
  }

  // Current permissions (names from role) with optimistic updates
  const currentPermissionNames = useMemo(() => {
    const baseSet = new Set(role?.permissions || []);
    // Apply pending changes optimistically
    pendingChanges.forEach((shouldHave, permName) => {
      if (shouldHave) {
        baseSet.add(permName);
      } else {
        baseSet.delete(permName);
      }
    });
    return baseSet;
  }, [role?.permissions, pendingChanges]);

  // Group permissions by module
  const groupedPermissions = useMemo(() => {
    return allPermissions.reduce((acc, perm) => {
      const module = perm.module_name || 'other';
      if (!acc[module]) acc[module] = [];
      acc[module].push(perm);
      return acc;
    }, {} as Record<string, Permission[]>);
  }, [allPermissions]);

  // Toggle module collapse/expand
  const toggleModule = useCallback((module: string) => {
    setExpandedModules((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(module)) {
        newSet.delete(module);
      } else {
        newSet.add(module);
      }
      return newSet;
    });
  }, []);

  // Expand all modules
  const expandAllModules = useCallback(() => {
    setExpandedModules(new Set(Object.keys(groupedPermissions)));
  }, [groupedPermissions]);

  // Collapse all modules
  const collapseAllModules = useCallback(() => {
    setExpandedModules(new Set());
  }, []);

  // Handle update with detailed feedback
  const handleUpdate = async () => {
    if (!role || role.is_system) return;

    // Validation
    if (!formData.name?.trim()) {
      toast.error('Validation Error', {
        description: 'Role name is required. Please enter a valid name.',
        icon: <X className="h-5 w-5" />,
      });
      return;
    }

    try {
      await updateMutation.mutateAsync({
        id: roleId,
        data: formData,
      });
      toast.success('Role Updated', {
        description: `The role "${formData.name}" has been updated successfully.`,
        icon: <Check className="h-5 w-5" />,
      });
      refetchRole();
    } catch (err) {
      // Parse error for user-friendly message
      let errorMessage = 'An unexpected error occurred while updating the role.';
      let errorDetail = '';

      if (err instanceof Error) {
        const msg = err.message.toLowerCase();
        if (msg.includes('duplicate') || msg.includes('already exists')) {
          errorMessage = 'Name Already Exists';
          errorDetail = 'A role with this name already exists. Please choose a different name.';
        } else if (msg.includes('permission') || msg.includes('denied') || msg.includes('403')) {
          errorMessage = 'Permission Denied';
          errorDetail = 'You do not have permission to update this role.';
        } else if (msg.includes('network') || msg.includes('fetch')) {
          errorMessage = 'Network Error';
          errorDetail = 'Unable to connect to the server. Please check your internet connection.';
        } else if (msg.includes('not found') || msg.includes('404')) {
          errorMessage = 'Role Not Found';
          errorDetail = 'This role may have been deleted. Please refresh the page.';
        } else {
          errorMessage = 'Update Failed';
          errorDetail = err.message;
        }
      }

      toast.error(errorMessage, {
        description: errorDetail,
        icon: <AlertCircle className="h-5 w-5" />,
        duration: 5000,
      });
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!role || role.is_system) return;

    try {
      await deleteMutation.mutateAsync(roleId);
      toast.success('Role deleted successfully');
      router.push(`/${locale}/dashboard/admin/roles`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Error deleting role');
    }
  };

  // Handle permission toggle with optimistic update
  const handleTogglePermission = useCallback(async (permission: Permission, e?: React.MouseEvent) => {
    // Stop propagation to prevent double-firing from parent onClick
    if (e) {
      e.stopPropagation();
    }

    if (!role || role.is_system) return;

    const hasPermission = currentPermissionNames.has(permission.name);
    const newValue = !hasPermission;

    // Optimistic update - instant UI feedback
    setPendingChanges((prev) => {
      const newMap = new Map(prev);
      newMap.set(permission.name, newValue);
      return newMap;
    });

    try {
      if (hasPermission) {
        await removeMutation.mutateAsync({
          roleId,
          data: { permission_ids: [permission.id] },
        });
      } else {
        await assignMutation.mutateAsync({
          roleId,
          data: { permission_ids: [permission.id], granted: true },
        });
      }
      // Clear pending change after success
      setPendingChanges((prev) => {
        const newMap = new Map(prev);
        newMap.delete(permission.name);
        return newMap;
      });
      refetchRole();
    } catch (err) {
      // Revert optimistic update on error
      setPendingChanges((prev) => {
        const newMap = new Map(prev);
        newMap.delete(permission.name);
        return newMap;
      });
      toast.error(err instanceof Error ? err.message : 'Error updating permission');
    }
  }, [role, roleId, currentPermissionNames, assignMutation, removeMutation, refetchRole]);

  // Select all permissions in a module
  const handleSelectAllInModule = useCallback(async (module: string) => {
    if (!role || role.is_system) return;

    const modulePerms = groupedPermissions[module] || [];
    const unassignedPerms = modulePerms.filter((p) => !currentPermissionNames.has(p.name));

    if (unassignedPerms.length === 0) return;

    // Optimistic update
    unassignedPerms.forEach((p) => {
      setPendingChanges((prev) => new Map(prev).set(p.name, true));
    });

    try {
      await assignMutation.mutateAsync({
        roleId,
        data: { permission_ids: unassignedPerms.map((p) => p.id), granted: true },
      });
      // Clear pending changes
      unassignedPerms.forEach((p) => {
        setPendingChanges((prev) => {
          const newMap = new Map(prev);
          newMap.delete(p.name);
          return newMap;
        });
      });
      toast.success(`${unassignedPerms.length} permissions assigned`);
      refetchRole();
    } catch (err) {
      // Revert on error
      unassignedPerms.forEach((p) => {
        setPendingChanges((prev) => {
          const newMap = new Map(prev);
          newMap.delete(p.name);
          return newMap;
        });
      });
      toast.error(err instanceof Error ? err.message : 'Error assigning permissions');
    }
  }, [role, roleId, groupedPermissions, currentPermissionNames, assignMutation, refetchRole]);

  // Deselect all permissions in a module
  const handleDeselectAllInModule = useCallback(async (module: string) => {
    if (!role || role.is_system) return;

    const modulePerms = groupedPermissions[module] || [];
    const assignedPerms = modulePerms.filter((p) => currentPermissionNames.has(p.name));

    if (assignedPerms.length === 0) return;

    // Optimistic update
    assignedPerms.forEach((p) => {
      setPendingChanges((prev) => new Map(prev).set(p.name, false));
    });

    try {
      await removeMutation.mutateAsync({
        roleId,
        data: { permission_ids: assignedPerms.map((p) => p.id) },
      });
      // Clear pending changes
      assignedPerms.forEach((p) => {
        setPendingChanges((prev) => {
          const newMap = new Map(prev);
          newMap.delete(p.name);
          return newMap;
        });
      });
      toast.success(`${assignedPerms.length} permissions removed`);
      refetchRole();
    } catch (err) {
      // Revert on error
      assignedPerms.forEach((p) => {
        setPendingChanges((prev) => {
          const newMap = new Map(prev);
          newMap.delete(p.name);
          return newMap;
        });
      });
      toast.error(err instanceof Error ? err.message : 'Error removing permissions');
    }
  }, [role, roleId, groupedPermissions, currentPermissionNames, removeMutation, refetchRole]);

  // Loading state
  if (roleLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (roleError || !role) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href={`/${locale}/dashboard/admin/roles`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold">Role not found</h1>
        </div>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>
                {roleError instanceof Error ? roleError.message : 'Role not found or access denied'}
              </span>
            </div>
            <Link href={`/${locale}/dashboard/admin/roles`}>
              <Button variant="outline" className="mt-4">
                Return to roles
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`/${locale}/dashboard/admin/roles`}>
            <Button variant="ghost" size="icon" title="Back to roles list">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <Shield className="h-8 w-8" />
                {role.name}
              </h1>
              {role.is_system && (
                <Badge variant="default" className="gap-1">
                  <Lock className="h-3 w-3" />
                  System
                </Badge>
              )}
              {role.entity_type && (
                <Badge variant="outline" className="gap-1">
                  <Building2 className="h-3 w-3" />
                  {role.entity_type}
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground mt-1">
              <code className="bg-muted px-2 py-1 rounded text-sm">{role.code}</code>
              {' - '}
              {role.permissions_count} permissions
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Role Navigation */}
          <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigationData.prev && navigateToRole(navigationData.prev.id)}
              disabled={!navigationData.prev || rolesListLoading}
              title={navigationData.prev ? `Previous: ${navigationData.prev.name}` : 'No previous role'}
              className="h-8 px-2"
            >
              <ChevronLeft className="h-4 w-4" />
              <span className="sr-only md:not-sr-only md:ml-1 text-xs">Prev</span>
            </Button>
            <span className="text-xs text-muted-foreground px-2 min-w-[60px] text-center">
              {rolesListLoading ? (
                <Loader2 className="h-3 w-3 animate-spin inline" />
              ) : rolesListError ? (
                <span className="text-destructive" title="Failed to load roles list">!</span>
              ) : navigationData.currentIndex >= 0 ? (
                `${navigationData.currentIndex + 1} / ${navigationData.total}`
              ) : (
                '- / -'
              )}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigationData.next && navigateToRole(navigationData.next.id)}
              disabled={!navigationData.next || rolesListLoading}
              title={navigationData.next ? `Next: ${navigationData.next.name}` : 'No next role'}
              className="h-8 px-2"
            >
              <span className="sr-only md:not-sr-only md:mr-1 text-xs">Next</span>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>

          {/* Menu Config Button */}
          <Link href={`/${locale}/dashboard/admin/roles/${roleId}/menu-config`}>
            <Button variant="outline">
              <Menu className="mr-2 h-4 w-4" />
              Menu Config
            </Button>
          </Link>

          {!role.is_system && (
            <Button
              variant="destructive"
              onClick={() => setIsDeleteDialogOpen(true)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete Role
            </Button>
          )}
        </div>
      </div>

      {/* System role warning */}
      {role.is_system && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-amber-700">
              <Lock className="h-5 w-5" />
              <p className="text-sm">
                <strong>System Role.</strong> This role is managed by the system and cannot be modified.
                You can only view its permissions.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column - Role Information */}
        <Card>
          <CardHeader>
            <CardTitle>Role Information</CardTitle>
            <CardDescription>
              {role.is_system ? 'View role details' : 'Update role name and description'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Name */}
            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                disabled={role.is_system}
              />
            </div>

            {/* Code (read-only) */}
            <div className="grid gap-2">
              <Label htmlFor="code">Code</Label>
              <Input id="code" value={role.code} disabled className="bg-muted" />
              <p className="text-xs text-muted-foreground">
                Code cannot be changed after creation
              </p>
            </div>

            {/* Entity Type (read-only) */}
            <div className="grid gap-2">
              <Label>Entity Type</Label>
              <Input
                value={role.entity_type || 'Global (no restriction)'}
                disabled
                className="bg-muted"
              />
            </div>

            {/* Description */}
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                disabled={role.is_system}
                rows={4}
              />
            </div>

            {/* Save button */}
            {!role.is_system && (
              <Button
                onClick={handleUpdate}
                disabled={updateMutation.isPending}
                className="w-full"
              >
                {updateMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </Button>
            )}
          </CardContent>
        </Card>

        {/* Right Column - Permissions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Permissions
            </CardTitle>
            <CardDescription>
              {role.is_system
                ? `${role.permissions_count} permissions assigned (read-only)`
                : `Manage permissions for this role (${role.permissions_count} assigned)`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Filters */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search permissions..."
                  value={permissionSearch}
                  onChange={(e) => setPermissionSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={moduleFilter} onValueChange={setModuleFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All modules</SelectItem>
                  {modules.map((mod: string | null) => mod && (
                    <SelectItem key={mod} value={mod}>
                      {mod}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Expand/Collapse All Buttons */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={expandAllModules}
                disabled={expandedModules.size === Object.keys(groupedPermissions).length}
              >
                Expand All
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={collapseAllModules}
                disabled={expandedModules.size === 0}
              >
                Collapse All
              </Button>
            </div>

            {/* Permissions List with Collapsible Modules */}
            <div className="border rounded-md max-h-[500px] overflow-y-auto">
              {permissionsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : allPermissions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <AlertCircle className="h-8 w-8 mb-2" />
                  <p>No permissions found</p>
                </div>
              ) : (
                Object.entries(groupedPermissions)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([module, perms]) => {
                    const isExpanded = expandedModules.has(module);
                    const assignedCount = perms.filter((p) => currentPermissionNames.has(p.name)).length;
                    const allAssigned = assignedCount === perms.length;
                    const noneAssigned = assignedCount === 0;

                    return (
                      <Collapsible
                        key={module}
                        open={isExpanded}
                        onOpenChange={() => toggleModule(module)}
                      >
                        <div className="sticky top-0 bg-muted border-b z-10">
                          <CollapsibleTrigger asChild>
                            <button
                              type="button"
                              className="w-full px-3 py-2 flex items-center justify-between hover:bg-muted/80 transition-colors"
                            >
                              <div className="flex items-center gap-2">
                                {isExpanded ? (
                                  <ChevronDown className="h-4 w-4" />
                                ) : (
                                  <ChevronRight className="h-4 w-4" />
                                )}
                                <span className="font-medium text-sm">{module}</span>
                              </div>
                              <Badge
                                variant={allAssigned ? 'default' : noneAssigned ? 'outline' : 'secondary'}
                                className="text-xs"
                              >
                                {assignedCount}/{perms.length}
                              </Badge>
                            </button>
                          </CollapsibleTrigger>

                          {/* Select All / Deselect All for this module */}
                          {!role.is_system && isExpanded && (
                            <div className="px-3 pb-2 flex gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSelectAllInModule(module);
                                }}
                                disabled={allAssigned || assignMutation.isPending}
                              >
                                <CheckSquare className="h-3 w-3 mr-1" />
                                Select All
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeselectAllInModule(module);
                                }}
                                disabled={noneAssigned || removeMutation.isPending}
                              >
                                <Square className="h-3 w-3 mr-1" />
                                Deselect All
                              </Button>
                            </div>
                          )}
                        </div>

                        <CollapsibleContent>
                          {perms.map((perm) => {
                            const hasPermission = currentPermissionNames.has(perm.name);
                            const isPending = pendingChanges.has(perm.name);

                            return (
                              <div
                                key={perm.id}
                                className={`flex items-center gap-3 px-3 py-2 hover:bg-muted/50 border-b border-muted/50 last:border-0 ${
                                  isPending ? 'opacity-70' : ''
                                }`}
                              >
                                <Checkbox
                                  checked={hasPermission}
                                  disabled={role.is_system || isPending}
                                  onCheckedChange={() => handleTogglePermission(perm)}
                                  className="cursor-pointer"
                                />
                                <div
                                  className={`flex-1 min-w-0 ${!role.is_system ? 'cursor-pointer' : ''}`}
                                  onClick={() => !role.is_system && !isPending && handleTogglePermission(perm)}
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">{perm.name}</span>
                                    {perm.is_critical && (
                                      <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                                        Critical
                                      </Badge>
                                    )}
                                    {isPending && (
                                      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                                    )}
                                  </div>
                                  {perm.description && (
                                    <p className="text-xs text-muted-foreground truncate">
                                      {perm.description}
                                    </p>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </CollapsibleContent>
                      </Collapsible>
                    );
                  })
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Role</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the role &quot;{role.name}&quot;?
              This action cannot be undone. Users assigned to this role will lose
              their associated permissions.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
