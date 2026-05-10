/**
 * Member List Component
 * Displays company members in a table with actions
 *
 * @module companies/components
 * @author Claude Code
 * @date 2025-12-03
 */

'use client'

import * as React from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { MoreHorizontal, Trash2, Shield, UserX } from 'lucide-react'
import { useCompanyMembers, useRemoveCompanyMember } from '../hooks/useCompanyMembers'
import { getRoleLabel } from './MemberRoleSelector'
import type { CompanyMember } from '../types'
import { format } from 'date-fns'

// =============================================================================
// TYPES
// =============================================================================

interface MemberListProps {
  companyId: string
  currentUserId?: string
  onChangeRole?: (member: CompanyMember) => void
  canManageMembers?: boolean
}

// =============================================================================
// COMPONENT
// =============================================================================

export function MemberList({
  companyId,
  currentUserId,
  onChangeRole,
  canManageMembers = false,
}: MemberListProps) {
  const { data: members, isLoading, error } = useCompanyMembers(companyId)
  const removeMember = useRemoveCompanyMember(companyId)

  const [memberToRemove, setMemberToRemove] = React.useState<CompanyMember | null>(null)

  // Handle remove confirmation
  const handleRemoveConfirm = async () => {
    if (memberToRemove) {
      await removeMember.mutateAsync(memberToRemove.user_id)
      setMemberToRemove(null)
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-lg border border-destructive bg-destructive/10 p-4">
        <p className="text-sm text-destructive">
          Failed to load members: {error instanceof Error ? error.message : 'Unknown error'}
        </p>
      </div>
    )
  }

  // Empty state
  if (!members || members.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center">
        <UserX className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">No members yet</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Add members to collaborate on company tasks
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Member</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Joined</TableHead>
              {canManageMembers && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((member) => {
              const isCurrentUser = currentUserId === member.user_id
              const isOwner = member.role === 'company_owner'
              const canRemove = canManageMembers && !isOwner && !isCurrentUser

              return (
                <TableRow key={member.user_id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {member.user_name || 'Unknown User'}
                      {isCurrentUser && (
                        <Badge variant="secondary" className="text-xs">
                          You
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {member.user_email || 'N/A'}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {isOwner && <Shield className="h-4 w-4 text-primary" />}
                      <span>{getRoleLabel(member.role)}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={member.is_active ? 'default' : 'secondary'}>
                      {member.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {member.assigned_at
                      ? format(new Date(member.assigned_at), 'MMM d, yyyy')
                      : 'N/A'}
                  </TableCell>
                  {canManageMembers && (
                    <TableCell className="text-right">
                      {canRemove ? (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreHorizontal className="h-4 w-4" />
                              <span className="sr-only">Open menu</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuSeparator />
                            {onChangeRole && (
                              <DropdownMenuItem
                                onClick={() => onChangeRole(member)}
                              >
                                <Shield className="mr-2 h-4 w-4" />
                                Change Role
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => setMemberToRemove(member)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Remove Member
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          {isOwner ? 'Owner' : 'You'}
                        </span>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {/* Remove Member Confirmation Dialog */}
      <AlertDialog
        open={!!memberToRemove}
        onOpenChange={(open) => !open && setMemberToRemove(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Member?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove{' '}
              <strong>{memberToRemove?.user_name || memberToRemove?.user_email}</strong> from
              this company? They will lose access to all company data and will need to be
              re-invited to regain access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {removeMember.isPending ? 'Removing...' : 'Remove Member'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
