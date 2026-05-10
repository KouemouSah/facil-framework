/**
 * Invite Member Dialog Component
 * Dialog for adding members to a company
 *
 * @module companies/components
 * @author Claude Code
 * @date 2025-12-03
 */

'use client'

import * as React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, AlertCircle, UserPlus } from 'lucide-react'
import { useAddCompanyMember } from '../hooks/useCompanyMembers'
import { MemberRoleSelector } from './MemberRoleSelector'
import { addMemberSchema, type AddMemberInput } from '../validations/members'
import type { CompanyMemberRole as _CompanyMemberRole } from '../types'

// =============================================================================
// TYPES
// =============================================================================

interface InviteMemberDialogProps {
  companyId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

// =============================================================================
// COMPONENT
// =============================================================================

export function InviteMemberDialog({
  companyId,
  open,
  onOpenChange,
}: InviteMemberDialogProps) {
  const addMember = useAddCompanyMember(companyId)
  const [error, setError] = React.useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setValue,
    watch,
  } = useForm<AddMemberInput>({
    resolver: zodResolver(addMemberSchema),
    defaultValues: {
      memberUserId: '',
      role: 'company_member',
    },
  })

  const selectedRole = watch('role')

  // Reset form when dialog closes
  React.useEffect(() => {
    if (!open) {
      reset()
      setError(null)
    }
  }, [open, reset])

  const onSubmit = async (data: AddMemberInput) => {
    try {
      setError(null)
      await addMember.mutateAsync({
        memberUserId: data.memberUserId,
        role: data.role,
      })
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add member')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="h-5 w-5" />
            Add Member to Company
          </DialogTitle>
          <DialogDescription>
            Add an existing user to this company by their user ID. They will receive
            access based on the role you assign.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* User ID Input */}
          <div className="space-y-2">
            <Label htmlFor="memberUserId">
              User ID <span className="text-destructive">*</span>
            </Label>
            <Input
              id="memberUserId"
              type="text"
              placeholder="00000000-0000-0000-0000-000000000000"
              {...register('memberUserId')}
              disabled={isSubmitting}
            />
            {errors.memberUserId && (
              <p className="text-sm text-destructive">{errors.memberUserId.message}</p>
            )}
            <p className="text-xs text-muted-foreground">
              Enter the UUID of the user you want to add
            </p>
          </div>

          {/* Role Selector */}
          <MemberRoleSelector
            label={
              <>
                Role <span className="text-destructive">*</span>
              </>
            }
            value={selectedRole}
            onChange={(role) => setValue('role', role)}
            disabled={isSubmitting}
            excludeRoles={['company_owner']}
          />
          {errors.role && (
            <p className="text-sm text-destructive">{errors.role.message}</p>
          )}

          {/* Info Box */}
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-xs">
              <strong>Note:</strong> The user must already be registered in the system.
              Email-based invitations are coming in a future update.
            </AlertDescription>
          </Alert>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isSubmitting ? 'Adding...' : 'Add Member'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// =============================================================================
// ALTERNATIVE: EMAIL-BASED INVITE (Future Feature)
// =============================================================================

/**
 * This component can be used when the backend supports email-based invitations
 * Currently commented out as the backend doesn't have this feature yet
 */
/*
export function InviteMemberByEmailDialog({
  companyId,
  open,
  onOpenChange,
}: InviteMemberDialogProps) {
  const [error, setError] = React.useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setValue,
    watch,
  } = useForm<InviteMemberInput>({
    resolver: zodResolver(inviteMemberSchema),
    defaultValues: {
      email: '',
      role: 'company_member',
      message: '',
    },
  })

  const selectedRole = watch('role')

  React.useEffect(() => {
    if (!open) {
      reset()
      setError(null)
    }
  }, [open, reset])

  const onSubmit = async (data: InviteMemberInput) => {
    try {
      setError(null)
      // TODO: Call backend invitation API when available
      // await inviteMember.mutateAsync(data)
      console.log('Invite member:', data)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send invitation')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Invite Member by Email</DialogTitle>
          <DialogDescription>
            Send an invitation email to add a new member to this company
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              placeholder="member@example.com"
              {...register('email')}
              disabled={isSubmitting}
            />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>

          <MemberRoleSelector
            label="Role"
            value={selectedRole}
            onChange={(role) => setValue('role', role)}
            disabled={isSubmitting}
            excludeRoles={['company_owner']}
          />

          <div className="space-y-2">
            <Label htmlFor="message">Optional Message</Label>
            <Textarea
              id="message"
              placeholder="Add a personal message to the invitation..."
              {...register('message')}
              disabled={isSubmitting}
              rows={3}
            />
            {errors.message && (
              <p className="text-sm text-destructive">{errors.message.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isSubmitting ? 'Sending...' : 'Send Invitation'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
*/
