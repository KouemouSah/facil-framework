'use client'

/**
 * UserPermissionList Component
 * Displays the list of permission overrides for a user
 *
 * @module user-permissions-admin/components
 * @author Claude Code
 * @date 2025-12-04
 */

import { useTranslations } from 'next-intl'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Loader2, Trash2, AlertTriangle, Check, X, Clock, Info } from 'lucide-react'
import { toast } from 'sonner'
import { useState } from 'react'
import { formatDistanceToNow, format, isPast } from 'date-fns'

import { useRevokePermission } from '../hooks/useUserPermissions'
import type { UserPermission } from '../types'

interface UserPermissionListProps {
  permissions: UserPermission[]
  userId: string
  isLoading?: boolean
  onRefresh?: () => void
}

export function UserPermissionList({
  permissions,
  userId,
  isLoading = false,
  onRefresh,
}: UserPermissionListProps) {
  const t = useTranslations('admin.userPermissions')
  const tCommon = useTranslations('common')

  const [permissionToRevoke, setPermissionToRevoke] = useState<UserPermission | null>(null)
  const revokeMutation = useRevokePermission()

  const handleRevoke = async () => {
    if (!permissionToRevoke) return

    try {
      await revokeMutation.mutateAsync({
        userId,
        permissionId: permissionToRevoke.permission_id,
      })
      toast.success(t('permissionRevoked') || 'Permission revoked successfully')
      setPermissionToRevoke(null)
      onRefresh?.()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to revoke permission')
    }
  }

  const isExpired = (expiresAt: string | null): boolean => {
    if (!expiresAt) return false
    return isPast(new Date(expiresAt))
  }

  const formatExpiresAt = (expiresAt: string | null): string => {
    if (!expiresAt) return t('permanent') || 'Permanent'
    const date = new Date(expiresAt)
    if (isPast(date)) {
      return t('expired') || 'Expired'
    }
    return formatDistanceToNow(date, { addSuffix: true })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (permissions.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Info className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>{t('noOverrides') || 'No permission overrides for this user.'}</p>
        <p className="text-sm mt-2">
          {t('noOverridesHint') || 'This user only has permissions from their assigned role.'}
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('permission') || 'Permission'}</TableHead>
              <TableHead>{t('status') || 'Status'}</TableHead>
              <TableHead>{t('expires') || 'Expires'}</TableHead>
              <TableHead>{t('reason') || 'Reason'}</TableHead>
              <TableHead className="text-right">{t('actions') || 'Actions'}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {permissions.map((perm) => {
              const expired = isExpired(perm.expires_at)

              return (
                <TableRow key={perm.id} className={expired ? 'opacity-50' : ''}>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <code className="text-sm bg-muted px-1.5 py-0.5 rounded">
                          {perm.permission_name}
                        </code>
                        {perm.is_critical && (
                          <Badge variant="destructive" className="text-xs gap-1">
                            <AlertTriangle className="h-3 w-3" />
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground truncate max-w-[300px]">
                        {perm.permission_description}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {perm.granted ? (
                      <Badge variant="default" className="gap-1">
                        <Check className="h-3 w-3" />
                        {t('granted') || 'Granted'}
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="gap-1">
                        <X className="h-3 w-3" />
                        {t('denied') || 'Denied'}
                      </Badge>
                    )}
                    {expired && (
                      <Badge variant="outline" className="ml-2 text-amber-600 border-amber-300">
                        {t('expired') || 'Expired'}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {perm.expires_at ? (
                        <>
                          <Clock className="h-4 w-4 text-muted-foreground" />
                          <span
                            className={expired ? 'text-amber-600 cursor-help' : 'cursor-help'}
                            title={format(new Date(perm.expires_at), 'PPpp')}
                          >
                            {formatExpiresAt(perm.expires_at)}
                          </span>
                        </>
                      ) : (
                        <span className="text-muted-foreground">
                          {t('permanent') || 'Permanent'}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {perm.reason ? (
                      <span
                        className="text-sm truncate max-w-[200px] block cursor-help"
                        title={perm.reason}
                      >
                        {perm.reason}
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-sm">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setPermissionToRevoke(perm)}
                      className="text-destructive hover:text-destructive"
                      title={t('revoke') || 'Revoke'}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {/* Revoke Confirmation Dialog */}
      <AlertDialog
        open={!!permissionToRevoke}
        onOpenChange={(open) => !open && setPermissionToRevoke(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('revokePermission') || 'Revoke Permission'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('revokePermissionConfirmation', {
                permission: permissionToRevoke?.permission_name,
              }) ||
                `Are you sure you want to revoke "${permissionToRevoke?.permission_name}"? The user will lose this permission override.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel') || 'Cancel'}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRevoke}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {revokeMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {t('revoke') || 'Revoke'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default UserPermissionList
