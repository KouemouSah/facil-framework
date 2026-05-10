'use client'

/**
 * GrantPermissionDialog Component
 * Dialog for granting permissions to a user (supports multi-select)
 *
 * @module user-permissions-admin/components
 * @author Claude Code
 * @date 2025-12-04
 * @updated 2026-01-19 - Added multi-select support for bulk permission assignment
 */

import { useState, useMemo } from 'react'
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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2, AlertTriangle, Search, CheckSquare, Square, ChevronDown, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

import { usePermissions } from '@/modules/permissions-admin/hooks/usePermissions'
import { useGrantPermission } from '../hooks/useUserPermissions'
import type { Permission } from '@/modules/permissions-admin/types'
import type { SimpleUser } from '../types'

interface GrantPermissionDialogProps {
  user: SimpleUser | null
  existingPermissionIds: string[]
  open: boolean
  onOpenChange: (open: boolean) => void
}

type DurationType = 'permanent' | '24h' | '7d' | '30d' | 'custom'

export function GrantPermissionDialog({
  user,
  existingPermissionIds,
  open,
  onOpenChange,
}: GrantPermissionDialogProps) {
  const t = useTranslations('admin.userPermissions')
  const tCommon = useTranslations('common')

  // State - Now supports multiple selection
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<Set<string>>(new Set())
  const [granted, setGranted] = useState<boolean>(true)
  const [durationType, setDurationType] = useState<DurationType>('permanent')
  const [customDays, setCustomDays] = useState<number>(7)
  const [reason, setReason] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [isGranting, setIsGranting] = useState(false)
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set())

  // Queries
  const { data: allPermissions = [], isLoading: isLoadingPermissions } = usePermissions()
  const grantMutation = useGrantPermission()

  // Filter permissions: exclude already assigned ones
  const availablePermissions = useMemo(() => {
    return allPermissions.filter((perm) => {
      // Exclude already assigned
      if (existingPermissionIds.includes(perm.id)) return false

      // Apply search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          perm.name.toLowerCase().includes(query) ||
          perm.description.toLowerCase().includes(query) ||
          perm.resource.toLowerCase().includes(query)
        )
      }

      return true
    })
  }, [allPermissions, existingPermissionIds, searchQuery])

  // Group by module
  const groupedPermissions = useMemo(() => {
    const groups: Record<string, Permission[]> = {}
    availablePermissions.forEach((perm) => {
      const module = perm.module_name || 'other'
      if (!groups[module]) groups[module] = []
      groups[module].push(perm)
    })
    return groups
  }, [availablePermissions])

  // Calculate expiration date
  const calculateExpiresAt = (): string | null => {
    if (durationType === 'permanent') return null

    const now = new Date()
    let days = 0

    switch (durationType) {
      case '24h':
        days = 1
        break
      case '7d':
        days = 7
        break
      case '30d':
        days = 30
        break
      case 'custom':
        days = customDays
        break
    }

    now.setDate(now.getDate() + days)
    return now.toISOString()
  }

  // Toggle single permission selection
  const togglePermission = (permId: string) => {
    setSelectedPermissionIds((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(permId)) {
        newSet.delete(permId)
      } else {
        newSet.add(permId)
      }
      return newSet
    })
  }

  // Select all visible permissions (filtered by search)
  const selectAllVisible = () => {
    setSelectedPermissionIds((prev) => {
      const newSet = new Set(prev)
      availablePermissions.forEach((perm) => newSet.add(perm.id))
      return newSet
    })
  }

  // Deselect all
  const deselectAll = () => {
    setSelectedPermissionIds(new Set())
  }

  // Select all in a specific module
  const selectModule = (module: string) => {
    const modulePerms = groupedPermissions[module] || []
    setSelectedPermissionIds((prev) => {
      const newSet = new Set(prev)
      modulePerms.forEach((perm) => newSet.add(perm.id))
      return newSet
    })
  }

  // Toggle module expansion
  const toggleModuleExpanded = (module: string) => {
    setExpandedModules((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(module)) {
        newSet.delete(module)
      } else {
        newSet.add(module)
      }
      return newSet
    })
  }

  // Expand all modules
  const expandAllModules = () => {
    setExpandedModules(new Set(Object.keys(groupedPermissions)))
  }

  // Collapse all modules
  const collapseAllModules = () => {
    setExpandedModules(new Set())
  }

  // Handlers - Now grants multiple permissions
  const handleGrant = async () => {
    if (!user || selectedPermissionIds.size === 0) return

    setIsGranting(true)
    const permIds = Array.from(selectedPermissionIds)
    let successCount = 0
    let failCount = 0
    const errors: string[] = []

    try {
      // Grant each permission sequentially to avoid rate limits
      for (const permId of permIds) {
        try {
          await grantMutation.mutateAsync({
            userId: user.id,
            data: {
              permission_id: permId,
              granted,
              expires_at: calculateExpiresAt(),
              reason: reason.trim() || undefined,
            },
          })
          successCount++
        } catch (error) {
          failCount++
          const permName = allPermissions.find((p) => p.id === permId)?.name || permId
          errors.push(permName)
        }
      }

      if (successCount > 0) {
        toast.success(
          granted
            ? `${successCount} permission(s) granted successfully`
            : `${successCount} permission(s) denied successfully`
        )
      }
      if (failCount > 0) {
        toast.error(`Failed to assign ${failCount} permission(s): ${errors.slice(0, 3).join(', ')}${errors.length > 3 ? '...' : ''}`)
      }
      handleClose()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to grant permissions')
    } finally {
      setIsGranting(false)
    }
  }

  const handleClose = () => {
    setSelectedPermissionIds(new Set())
    setGranted(true)
    setDurationType('permanent')
    setCustomDays(7)
    setReason('')
    setSearchQuery('')
    setExpandedModules(new Set())
    onOpenChange(false)
  }

  // Check if any selected permission is critical
  const hasSelectedCritical = useMemo(() => {
    return allPermissions.some((p) => selectedPermissionIds.has(p.id) && p.is_critical)
  }, [allPermissions, selectedPermissionIds])

  if (!user) return null

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>
            {t('addOverride') || 'Add Override'}
          </DialogTitle>
          <DialogDescription>
            {t('grantPermissionDescription', {
              name: `${user.first_name} ${user.last_name}`,
            }) || `Grant or deny a specific permission to ${user.first_name} ${user.last_name}.`}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4" style={{ maxHeight: 'calc(90vh - 200px)' }}>
          <div className="space-y-4">
          {/* Permission Selection */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>{t('selectPermission') || 'Select Permission'}</Label>
              {selectedPermissionIds.size > 0 && (
                <Badge variant="secondary">
                  {selectedPermissionIds.size} {t('selected') || 'selected'}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('searchPermissions') || 'Search permissions...'}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              {/* Bulk selection buttons */}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={selectAllVisible}
                disabled={availablePermissions.length === 0}
                title={t('selectAll') || 'Select All'}
              >
                <CheckSquare className="h-4 w-4 mr-1" />
                {t('all') || 'All'}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={deselectAll}
                disabled={selectedPermissionIds.size === 0}
                title={t('clearSelection') || 'Clear Selection'}
              >
                <Square className="h-4 w-4 mr-1" />
                {t('none') || 'None'}
              </Button>
            </div>

            {/* Expand/Collapse All */}
            {Object.keys(groupedPermissions).length > 1 && (
              <div className="flex items-center gap-2 text-xs">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs"
                  onClick={expandAllModules}
                >
                  {t('expandAll') || 'Expand All'}
                </Button>
                <span className="text-muted-foreground">|</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs"
                  onClick={collapseAllModules}
                >
                  {t('collapseAll') || 'Collapse All'}
                </Button>
              </div>
            )}

            <ScrollArea className="h-[280px] border rounded-md overflow-auto">
              {isLoadingPermissions ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : availablePermissions.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                  {searchQuery
                    ? t('noPermissionsFound') || 'No permissions found'
                    : t('allPermissionsAssigned') || 'All permissions are already assigned'}
                </div>
              ) : (
                <div className="p-2 space-y-2">
                  {Object.entries(groupedPermissions)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([module, perms]) => {
                      const moduleSelectedCount = perms.filter(p => selectedPermissionIds.has(p.id)).length
                      const isExpanded = expandedModules.has(module)
                      return (
                        <Collapsible
                          key={module}
                          open={isExpanded}
                          onOpenChange={() => toggleModuleExpanded(module)}
                          className="border rounded-md"
                        >
                          <div className="flex items-center justify-between px-3 py-2 bg-muted/50">
                            <CollapsibleTrigger className="flex items-center gap-2 flex-1 text-left">
                              {isExpanded ? (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              )}
                              <span className="text-sm font-medium">
                                {module.replace(/_/g, ' ')}
                              </span>
                              <Badge variant="outline" className="text-xs ml-2">
                                {moduleSelectedCount > 0 ? `${moduleSelectedCount}/` : ''}{perms.length}
                              </Badge>
                            </CollapsibleTrigger>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-6 text-xs"
                              onClick={(e) => {
                                e.stopPropagation()
                                selectModule(module)
                              }}
                            >
                              {moduleSelectedCount === perms.length
                                ? (t('allSelected') || 'All selected')
                                : (t('selectAllModule') || 'Select all')}
                            </Button>
                          </div>
                          <CollapsibleContent>
                            <div className="p-2 space-y-1">
                              {perms.map((perm) => {
                                const isSelected = selectedPermissionIds.has(perm.id)
                                return (
                                  <button
                                    key={perm.id}
                                    type="button"
                                    onClick={() => togglePermission(perm.id)}
                                    className={`w-full text-left p-2 rounded-md transition-colors flex items-start gap-2 ${
                                      isSelected
                                        ? 'bg-primary/10 border border-primary'
                                        : 'hover:bg-muted border border-transparent'
                                    }`}
                                  >
                                    <Checkbox
                                      checked={isSelected}
                                      className="mt-0.5"
                                      onCheckedChange={() => togglePermission(perm.id)}
                                    />
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                          {perm.name}
                                        </code>
                                        {perm.is_critical && (
                                          <Badge variant="destructive" className="text-xs gap-1">
                                            <AlertTriangle className="h-3 w-3" />
                                            {t('critical') || 'Critical'}
                                          </Badge>
                                        )}
                                      </div>
                                      <p className="text-xs text-muted-foreground mt-1 truncate">
                                        {perm.description}
                                      </p>
                                    </div>
                                  </button>
                                )
                              })}
                            </div>
                          </CollapsibleContent>
                        </Collapsible>
                      )
                    })}
                </div>
              )}
            </ScrollArea>
          </div>

          {/* Selected Permission Warning */}
          {hasSelectedCritical && (
            <div className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-md text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span className="text-sm">
                {t('criticalPermissionWarning') ||
                  'One or more critical permissions are selected. Make sure you understand the implications.'}
              </span>
            </div>
          )}

          {/* Grant/Deny Toggle */}
          <div className="space-y-2">
            <Label>{t('action') || 'Action'}</Label>
            <RadioGroup
              value={granted ? 'grant' : 'deny'}
              onValueChange={(v) => setGranted(v === 'grant')}
              className="flex gap-4"
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="grant" id="grant" />
                <Label htmlFor="grant" className="cursor-pointer">
                  {t('grant') || 'Grant'} - {t('allowAccess') || 'Allow access'}
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="deny" id="deny" />
                <Label htmlFor="deny" className="cursor-pointer">
                  {t('deny') || 'Deny'} - {t('blockAccess') || 'Block access'}
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Duration */}
          <div className="space-y-2">
            <Label>{t('duration') || 'Duration'}</Label>
            <Select value={durationType} onValueChange={(v) => setDurationType(v as DurationType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="permanent">{t('permanent') || 'Permanent'}</SelectItem>
                <SelectItem value="24h">{t('24hours') || '24 hours'}</SelectItem>
                <SelectItem value="7d">{t('7days') || '7 days'}</SelectItem>
                <SelectItem value="30d">{t('30days') || '30 days'}</SelectItem>
                <SelectItem value="custom">{t('custom') || 'Custom'}</SelectItem>
              </SelectContent>
            </Select>

            {durationType === 'custom' && (
              <div className="flex items-center gap-2 mt-2">
                <Input
                  type="number"
                  min={1}
                  max={365}
                  value={customDays}
                  onChange={(e) => setCustomDays(parseInt(e.target.value) || 1)}
                  className="w-24"
                />
                <span className="text-sm text-muted-foreground">{t('days') || 'days'}</span>
              </div>
            )}
          </div>

          {/* Reason */}
          <div className="space-y-2">
            <Label htmlFor="reason">{t('reason') || 'Reason'} ({t('optional') || 'optional'})</Label>
            <Textarea
              id="reason"
              placeholder={t('reasonPlaceholder') || 'Why is this permission being granted/denied?'}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
            />
          </div>
          </div>
        </ScrollArea>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isGranting}>
            {tCommon('cancel') || 'Cancel'}
          </Button>
          <Button
            onClick={handleGrant}
            disabled={selectedPermissionIds.size === 0 || isGranting}
            variant={granted ? 'default' : 'destructive'}
          >
            {isGranting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {granted
              ? `${t('grantPermissions') || 'Grant'} ${selectedPermissionIds.size > 0 ? `(${selectedPermissionIds.size})` : ''}`
              : `${t('denyPermissions') || 'Deny'} ${selectedPermissionIds.size > 0 ? `(${selectedPermissionIds.size})` : ''}`
            }
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default GrantPermissionDialog
