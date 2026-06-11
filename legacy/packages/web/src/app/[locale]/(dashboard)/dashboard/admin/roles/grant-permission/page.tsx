'use client'

/**
 * Grant Permission Page
 * Dedicated page for granting permissions to a user (replaces dialog)
 *
 * @route /[locale]/dashboard/admin/roles/grant-permission?userId=...
 * @date 2026-01-20
 */

import { useState, useMemo, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import Link from 'next/link'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Loader2,
  AlertTriangle,
  Search,
  CheckSquare,
  Square,
  ChevronDown,
  ChevronRight,
  ArrowLeft,
  Shield,
  Save,
  User,
} from 'lucide-react'
import { toast } from 'sonner'

import { usePermissions } from '@/modules/permissions-admin/hooks/usePermissions'
import { useGrantPermission, useUserPermissions } from '@/modules/user-permissions-admin/hooks/useUserPermissions'
import type { Permission } from '@/modules/permissions-admin/types'

type DurationType = 'permanent' | '24h' | '7d' | '30d' | 'custom'

export default function GrantPermissionPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const locale = useLocale()
  const t = useTranslations('admin.userPermissions')
  const tCommon = useTranslations('common')

  // Get user info from URL params
  const userId = searchParams.get('userId')
  const userName = searchParams.get('userName') || 'Agent'
  const userEmail = searchParams.get('userEmail') || ''

  // State
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
  const { data: userPermissionsData } = useUserPermissions(userId)
  const grantMutation = useGrantPermission()

  // Get existing permission IDs
  const existingPermissionIds = useMemo(() => {
    if (!userPermissionsData?.user_permissions) return []
    return userPermissionsData.user_permissions.map((p) => p.permission_id)
  }, [userPermissionsData])

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

  // Auto-expand first 3 modules on initial load
  useEffect(() => {
    if (Object.keys(groupedPermissions).length > 0 && expandedModules.size === 0) {
      const firstModules = Object.keys(groupedPermissions).sort().slice(0, 3)
      setExpandedModules(new Set(firstModules))
    }
  }, [groupedPermissions, expandedModules.size])

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

  // Select all visible permissions
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

  // Handle grant
  const handleGrant = async () => {
    if (!userId || selectedPermissionIds.size === 0) return

    setIsGranting(true)
    const permIds = Array.from(selectedPermissionIds)
    let successCount = 0
    let failCount = 0
    const errors: string[] = []

    try {
      for (const permId of permIds) {
        try {
          await grantMutation.mutateAsync({
            userId: userId,
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
            ? `${successCount} permission(s) accordée(s) avec succès`
            : `${successCount} permission(s) refusée(s) avec succès`
        )
      }
      if (failCount > 0) {
        toast.error(`Échec pour ${failCount} permission(s): ${errors.slice(0, 3).join(', ')}${errors.length > 3 ? '...' : ''}`)
      }

      // Navigate back to roles page
      router.push(`/${locale}/dashboard/admin/roles?tab=user-permissions`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Erreur lors de l\'attribution')
    } finally {
      setIsGranting(false)
    }
  }

  // Check if any selected permission is critical
  const hasSelectedCritical = useMemo(() => {
    return allPermissions.some((p) => selectedPermissionIds.has(p.id) && p.is_critical)
  }, [allPermissions, selectedPermissionIds])

  // Redirect if no userId
  if (!userId) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto">
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              <span>Aucun utilisateur sélectionné</span>
            </div>
            <Link href={`/${locale}/dashboard/admin/roles?tab=user-permissions`}>
              <Button variant="outline" className="mt-4">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Retour
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/admin/roles?tab=user-permissions`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6" />
            {t('addOverride') || 'Ajouter une dérogation'}
          </h1>
          <p className="text-muted-foreground flex items-center gap-2 mt-1">
            <User className="h-4 w-4" />
            {userName} ({userEmail})
          </p>
        </div>
      </div>

      {/* Permission Selection */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('selectPermission') || 'Sélectionner une permission'}</CardTitle>
              <CardDescription>
                {availablePermissions.length} permissions disponibles
              </CardDescription>
            </div>
            {selectedPermissionIds.size > 0 && (
              <Badge variant="default" className="text-base px-3 py-1">
                {selectedPermissionIds.size} {t('selected') || 'sélectionnée(s)'}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search and bulk actions */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('searchPermissions') || 'Rechercher des permissions...'}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={selectAllVisible}
              disabled={availablePermissions.length === 0}
            >
              <CheckSquare className="h-4 w-4 mr-1" />
              {t('all') || 'Tout'}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={deselectAll}
              disabled={selectedPermissionIds.size === 0}
            >
              <Square className="h-4 w-4 mr-1" />
              {t('none') || 'Aucun'}
            </Button>
          </div>

          {/* Expand/Collapse All */}
          {Object.keys(groupedPermissions).length > 1 && (
            <div className="flex items-center gap-2 text-sm">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={expandAllModules}
              >
                {t('expandAll') || 'Tout déplier'}
              </Button>
              <span className="text-muted-foreground">|</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={collapseAllModules}
              >
                {t('collapseAll') || 'Tout replier'}
              </Button>
            </div>
          )}

          {/* Permissions by module */}
          {isLoadingPermissions ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : availablePermissions.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              {searchQuery
                ? (t('noPermissionsFound') || 'Aucune permission trouvée')
                : (t('allPermissionsAssigned') || 'Toutes les permissions sont déjà assignées')}
            </div>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-y-auto border rounded-md p-2">
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
                            ? (t('allSelected') || 'Tout sélectionné')
                            : (t('selectAllModule') || 'Sélectionner tout')}
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
                                        {t('critical') || 'Critique'}
                                      </Badge>
                                    )}
                                  </div>
                                  <p className="text-xs text-muted-foreground mt-1">
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
        </CardContent>
      </Card>

      {/* Critical Warning */}
      {hasSelectedCritical && (
        <div className="flex items-center gap-2 p-4 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-md text-amber-700 dark:text-amber-400">
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <span>
            {t('criticalPermissionWarning') ||
              'Une ou plusieurs permissions critiques sont sélectionnées. Assurez-vous de comprendre les implications.'}
          </span>
        </div>
      )}

      {/* Action: Grant or Deny */}
      <Card>
        <CardHeader>
          <CardTitle>{t('action') || 'Action'}</CardTitle>
          <CardDescription>
            Choisir si vous voulez accorder ou refuser les permissions sélectionnées
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={granted ? 'grant' : 'deny'}
            onValueChange={(v) => setGranted(v === 'grant')}
            className="flex flex-col sm:flex-row gap-4"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="grant" id="grant" />
              <Label htmlFor="grant" className="cursor-pointer">
                <span className="font-medium">{t('grant') || 'Accorder'}</span>
                <span className="text-muted-foreground ml-2">- {t('allowAccess') || 'Autoriser l\'accès'}</span>
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="deny" id="deny" />
              <Label htmlFor="deny" className="cursor-pointer">
                <span className="font-medium">{t('deny') || 'Refuser'}</span>
                <span className="text-muted-foreground ml-2">- {t('blockAccess') || 'Bloquer l\'accès'}</span>
              </Label>
            </div>
          </RadioGroup>
        </CardContent>
      </Card>

      {/* Duration */}
      <Card>
        <CardHeader>
          <CardTitle>{t('duration') || 'Durée'}</CardTitle>
          <CardDescription>
            Définir la durée de validité de cette dérogation
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select value={durationType} onValueChange={(v) => setDurationType(v as DurationType)}>
            <SelectTrigger className="w-full sm:w-[300px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="permanent">{t('permanent') || 'Permanente'}</SelectItem>
              <SelectItem value="24h">{t('24hours') || '24 heures'}</SelectItem>
              <SelectItem value="7d">{t('7days') || '7 jours'}</SelectItem>
              <SelectItem value="30d">{t('30days') || '30 jours'}</SelectItem>
              <SelectItem value="custom">{t('custom') || 'Personnalisée'}</SelectItem>
            </SelectContent>
          </Select>

          {durationType === 'custom' && (
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={365}
                value={customDays}
                onChange={(e) => setCustomDays(parseInt(e.target.value) || 1)}
                className="w-24"
              />
              <span className="text-sm text-muted-foreground">{t('days') || 'jours'}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Reason */}
      <Card>
        <CardHeader>
          <CardTitle>{t('reason') || 'Motif'} ({t('optional') || 'optionnel'})</CardTitle>
          <CardDescription>
            Expliquer pourquoi cette permission est accordée ou refusée
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            placeholder={t('reasonPlaceholder') || 'Pourquoi cette permission est-elle accordée/refusée ?'}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
          />
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-between gap-3 pb-6">
        <Link href={`/${locale}/dashboard/admin/roles?tab=user-permissions`}>
          <Button type="button" variant="outline">
            {tCommon('cancel') || 'Annuler'}
          </Button>
        </Link>
        <Button
          onClick={handleGrant}
          disabled={selectedPermissionIds.size === 0 || isGranting}
          variant={granted ? 'default' : 'destructive'}
        >
          {isGranting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          <Save className="mr-2 h-4 w-4" />
          {granted
            ? `${t('grantPermissions') || 'Accorder'} ${selectedPermissionIds.size > 0 ? `(${selectedPermissionIds.size})` : ''}`
            : `${t('denyPermissions') || 'Refuser'} ${selectedPermissionIds.size > 0 ? `(${selectedPermissionIds.size})` : ''}`}
        </Button>
      </div>
    </div>
  )
}
