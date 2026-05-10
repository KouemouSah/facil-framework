'use client'

/**
 * RolePermissionsDialog Component
 * Dialog for managing permissions assigned to a role
 *
 * @module roles-admin/components
 * @author Claude Code
 * @date 2025-12-04
 */

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Loader2, Search, AlertTriangle, Shield, Lock } from 'lucide-react'
import { toast } from 'sonner'

import { usePermissions } from '@/modules/permissions-admin/hooks/usePermissions'
import { useRoleWithPermissions, useAssignPermissions, useRemovePermissions } from '../hooks/useRoles'
import type { Role } from '../types'
import type { Permission } from '@/modules/permissions-admin/types'

interface RolePermissionsDialogProps {
  role: Role | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function RolePermissionsDialog({
  role,
  open,
  onOpenChange,
}: RolePermissionsDialogProps) {
  const t = useTranslations('admin.roles')
  const tCommon = useTranslations('common')

  // State
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedPermissions, setSelectedPermissions] = useState<Set<string>>(new Set())
  const [initialPermissions, setInitialPermissions] = useState<Set<string>>(new Set())

  // Queries
  const { data: allPermissions = [], isLoading: isLoadingPermissions } = usePermissions()
  const { data: roleWithPermissions, isLoading: isLoadingRole } = useRoleWithPermissions(role?.id || '')

  // Mutations
  const assignMutation = useAssignPermissions()
  const removeMutation = useRemovePermissions()

  const isLoading = isLoadingPermissions || isLoadingRole
  const isSaving = assignMutation.isPending || removeMutation.isPending

  // Initialize selected permissions when role data loads
  useEffect(() => {
    if (roleWithPermissions?.permissions) {
      // roleWithPermissions.permissions contains permission names, not IDs
      // We need to map them to IDs
      const permissionNames = roleWithPermissions.permissions
      const permissionIds = new Set<string>()

      allPermissions.forEach((perm) => {
        if (permissionNames.includes(perm.name)) {
          permissionIds.add(perm.id)
        }
      })

      setSelectedPermissions(permissionIds)
      setInitialPermissions(permissionIds)
    }
  }, [roleWithPermissions, allPermissions])

  // Reset when dialog closes
  useEffect(() => {
    if (!open) {
      setSearchQuery('')
      setSelectedPermissions(new Set())
      setInitialPermissions(new Set())
    }
  }, [open])

  // Group permissions by module_name
  const groupedPermissions = useMemo(() => {
    const groups: Record<string, Permission[]> = {}

    const filteredPermissions = allPermissions.filter((perm) => {
      if (!searchQuery) return true
      const query = searchQuery.toLowerCase()
      return (
        perm.name.toLowerCase().includes(query) ||
        perm.description.toLowerCase().includes(query) ||
        perm.resource.toLowerCase().includes(query)
      )
    })

    filteredPermissions.forEach((perm) => {
      const moduleName = perm.module_name || 'other'
      if (!groups[moduleName]) {
        groups[moduleName] = []
      }
      groups[moduleName].push(perm)
    })

    // Sort permissions within each group by resource then action
    Object.keys(groups).forEach((key) => {
      groups[key].sort((a, b) => {
        if (a.resource !== b.resource) {
          return a.resource.localeCompare(b.resource)
        }
        return a.action.localeCompare(b.action)
      })
    })

    return groups
  }, [allPermissions, searchQuery])

  // Calculate changes
  const changes = useMemo(() => {
    const toAdd: string[] = []
    const toRemove: string[] = []

    selectedPermissions.forEach((id) => {
      if (!initialPermissions.has(id)) {
        toAdd.push(id)
      }
    })

    initialPermissions.forEach((id) => {
      if (!selectedPermissions.has(id)) {
        toRemove.push(id)
      }
    })

    return { toAdd, toRemove, hasChanges: toAdd.length > 0 || toRemove.length > 0 }
  }, [selectedPermissions, initialPermissions])

  // Handlers
  const handleTogglePermission = (permissionId: string) => {
    setSelectedPermissions((prev) => {
      const next = new Set(prev)
      if (next.has(permissionId)) {
        next.delete(permissionId)
      } else {
        next.add(permissionId)
      }
      return next
    })
  }

  const handleToggleModule = (modulePermissions: Permission[], checked: boolean) => {
    setSelectedPermissions((prev) => {
      const next = new Set(prev)
      modulePermissions.forEach((perm) => {
        if (checked) {
          next.add(perm.id)
        } else {
          next.delete(perm.id)
        }
      })
      return next
    })
  }

  const handleSave = async () => {
    if (!role) return

    try {
      // Assign new permissions
      if (changes.toAdd.length > 0) {
        await assignMutation.mutateAsync({
          roleId: role.id,
          data: { permission_ids: changes.toAdd, granted: true },
        })
      }

      // Remove permissions
      if (changes.toRemove.length > 0) {
        await removeMutation.mutateAsync({
          roleId: role.id,
          data: { permission_ids: changes.toRemove },
        })
      }

      toast.success(t('permissionsSaved') || 'Permissions saved successfully')
      onOpenChange(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save permissions')
    }
  }

  // Calculate module-level checkbox state
  const getModuleCheckState = (modulePermissions: Permission[]) => {
    const selectedCount = modulePermissions.filter((p) => selectedPermissions.has(p.id)).length
    if (selectedCount === 0) return { checked: false, indeterminate: false }
    if (selectedCount === modulePermissions.length) return { checked: true, indeterminate: false }
    return { checked: false, indeterminate: true }
  }

  // Count critical permissions selected
  const criticalCount = useMemo(() => {
    return allPermissions.filter((p) => selectedPermissions.has(p.id) && p.is_critical).length
  }, [allPermissions, selectedPermissions])

  if (!role) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            {t('managePermissions') || 'Manage Permissions'}
          </DialogTitle>
          <DialogDescription>
            {t('permissionsDialogDescription', { name: role.name }) ||
              `Configure permissions for the "${role.name}" role.`}
          </DialogDescription>
        </DialogHeader>

        {/* Search and Stats */}
        <div className="flex items-center justify-between gap-4 py-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t('searchPermissions') || 'Search permissions...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{selectedPermissions.size} selected</Badge>
            {criticalCount > 0 && (
              <Badge variant="destructive" className="gap-1">
                <AlertTriangle className="h-3 w-3" />
                {criticalCount} critical
              </Badge>
            )}
          </div>
        </div>

        {/* System role warning */}
        {role.is_system && (
          <div className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-md text-amber-700 dark:text-amber-400">
            <Lock className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm">
              {t('systemRoleWarning') || 'System roles have restricted editing. Some changes may not be allowed.'}
            </span>
          </div>
        )}

        {/* Permissions List */}
        <ScrollArea className="flex-1 -mx-6 px-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : Object.keys(groupedPermissions).length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              {searchQuery
                ? t('noPermissionsFound') || 'No permissions found'
                : t('noPermissionsAvailable') || 'No permissions available'}
            </div>
          ) : (
            <Accordion type="multiple" className="w-full" defaultValue={Object.keys(groupedPermissions)}>
              {Object.entries(groupedPermissions)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([moduleName, permissions]) => {
                  const { checked, indeterminate } = getModuleCheckState(permissions)
                  const criticalInModule = permissions.filter((p) => p.is_critical).length

                  return (
                    <AccordionItem key={moduleName} value={moduleName}>
                      <AccordionTrigger className="hover:no-underline">
                        <div className="flex items-center gap-3 flex-1">
                          <Checkbox
                            checked={checked}
                            ref={(el) => {
                              if (el) {
                                const element = el as HTMLButtonElement & { indeterminate: boolean }
                                element.indeterminate = indeterminate
                              }
                            }}
                            onCheckedChange={(checked) => {
                              handleToggleModule(permissions, checked === true)
                            }}
                            onClick={(e) => e.stopPropagation()}
                            disabled={role.is_system}
                          />
                          <span className="font-medium capitalize">{moduleName.replace(/_/g, ' ')}</span>
                          <Badge variant="secondary" className="ml-auto mr-2">
                            {permissions.filter((p) => selectedPermissions.has(p.id)).length}/{permissions.length}
                          </Badge>
                          {criticalInModule > 0 && (
                            <Badge variant="outline" className="gap-1 text-amber-600 border-amber-300">
                              <AlertTriangle className="h-3 w-3" />
                              {criticalInModule}
                            </Badge>
                          )}
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="grid gap-2 pl-8 pt-2">
                          {permissions.map((permission) => (
                            <label
                              key={permission.id}
                              className={`flex items-start gap-3 p-2 rounded-md hover:bg-muted/50 cursor-pointer ${
                                role.is_system ? 'opacity-60 cursor-not-allowed' : ''
                              }`}
                            >
                              <Checkbox
                                checked={selectedPermissions.has(permission.id)}
                                onCheckedChange={() => handleTogglePermission(permission.id)}
                                disabled={role.is_system}
                                className="mt-0.5"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <code className="text-sm font-mono bg-muted px-1.5 py-0.5 rounded">
                                    {permission.name}
                                  </code>
                                  {permission.is_critical && (
                                    <Badge variant="destructive" className="gap-1 text-xs">
                                      <AlertTriangle className="h-3 w-3" />
                                      {t('critical') || 'Critical'}
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-sm text-muted-foreground mt-1 truncate">
                                  {permission.description}
                                </p>
                              </div>
                            </label>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  )
                })}
            </Accordion>
          )}
        </ScrollArea>

        {/* Footer with changes summary */}
        <DialogFooter className="flex-col sm:flex-row gap-2">
          {changes.hasChanges && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground mr-auto">
              {changes.toAdd.length > 0 && (
                <Badge variant="outline" className="text-green-600 border-green-300">
                  +{changes.toAdd.length} to add
                </Badge>
              )}
              {changes.toRemove.length > 0 && (
                <Badge variant="outline" className="text-red-600 border-red-300">
                  -{changes.toRemove.length} to remove
                </Badge>
              )}
            </div>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            {tCommon('cancel') || 'Cancel'}
          </Button>
          <Button
            onClick={handleSave}
            disabled={!changes.hasChanges || isSaving || role.is_system}
          >
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {tCommon('save') || 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default RolePermissionsDialog
