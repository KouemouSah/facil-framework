/**
 * Company Members Manager Component
 * Complete UI for managing company members
 *
 * @module companies/components
 * @author Claude Code
 * @date 2025-12-03
 *
 * USAGE EXAMPLE:
 * ```tsx
 * import { CompanyMembersManager } from '@/modules/companies'
 *
 * function CompanyPage({ companyId }: { companyId: string }) {
 *   return (
 *     <div className="container mx-auto p-6">
 *       <CompanyMembersManager
 *         companyId={companyId}
 *         currentUserId={currentUser.id}
 *         canManageMembers={hasPermission('companies.manage_members')}
 *       />
 *     </div>
 *   )
 * }
 * ```
 */

'use client'

import * as React from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { UserPlus } from 'lucide-react'
import { MemberList } from './MemberList'
import { InviteMemberDialog } from './InviteMemberDialog'
import { MemberRoleSelector } from './MemberRoleSelector'
import type { CompanyMember, CompanyMemberRole } from '../types'
import { useUpdateMemberRole } from '../hooks/useCompanyMembers'

// =============================================================================
// TYPES
// =============================================================================

interface CompanyMembersManagerProps {
  companyId: string
  currentUserId?: string
  canManageMembers?: boolean
}

// =============================================================================
// COMPONENT
// =============================================================================

export function CompanyMembersManager({
  companyId,
  currentUserId,
  canManageMembers = false,
}: CompanyMembersManagerProps) {
  const [inviteDialogOpen, setInviteDialogOpen] = React.useState(false)
  const [roleChangeDialog, setRoleChangeDialog] = React.useState<{
    open: boolean
    member: CompanyMember | null
    newRole: CompanyMemberRole | null
  }>({
    open: false,
    member: null,
    newRole: null,
  })

  const updateRole = useUpdateMemberRole(companyId)

  const handleChangeRoleClick = (member: CompanyMember) => {
    setRoleChangeDialog({
      open: true,
      member,
      newRole: member.role,
    })
  }

  const handleRoleChange = async () => {
    if (roleChangeDialog.member && roleChangeDialog.newRole) {
      try {
        await updateRole.mutateAsync({
          userId: roleChangeDialog.member.user_id,
          role: roleChangeDialog.newRole,
        })
        setRoleChangeDialog({ open: false, member: null, newRole: null })
      } catch (error) {
        // Error is handled by the hook with toast
        console.error('Failed to update role:', error)
      }
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Company Members</CardTitle>
              <CardDescription>
                Manage members and their roles in this company
              </CardDescription>
            </div>
            {canManageMembers && (
              <Button onClick={() => setInviteDialogOpen(true)}>
                <UserPlus className="mr-2 h-4 w-4" />
                Add Member
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <MemberList
            companyId={companyId}
            currentUserId={currentUserId}
            onChangeRole={canManageMembers ? handleChangeRoleClick : undefined}
            canManageMembers={canManageMembers}
          />
        </CardContent>
      </Card>

      {/* Add Member Dialog */}
      <InviteMemberDialog
        companyId={companyId}
        open={inviteDialogOpen}
        onOpenChange={setInviteDialogOpen}
      />

      {/* Change Role Dialog */}
      <Dialog
        open={roleChangeDialog.open}
        onOpenChange={(open) =>
          !open && setRoleChangeDialog({ open: false, member: null, newRole: null })
        }
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Member Role</DialogTitle>
            <DialogDescription>
              Update the role for{' '}
              <strong>
                {roleChangeDialog.member?.user_name || roleChangeDialog.member?.user_email}
              </strong>
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {roleChangeDialog.newRole && (
              <MemberRoleSelector
                value={roleChangeDialog.newRole}
                onChange={(role) =>
                  setRoleChangeDialog((prev) => ({ ...prev, newRole: role }))
                }
                label="New Role"
                excludeRoles={['company_owner']}
              />
            )}
          </div>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() =>
                setRoleChangeDialog({ open: false, member: null, newRole: null })
              }
            >
              Cancel
            </Button>
            <Button
              onClick={handleRoleChange}
              disabled={
                updateRole.isPending ||
                roleChangeDialog.newRole === roleChangeDialog.member?.role
              }
            >
              {updateRole.isPending ? 'Updating...' : 'Update Role'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
