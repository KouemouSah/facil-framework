'use client'

/**
 * Edit User Dialog Component
 * Dialog for editing existing users with full i18n
 *
 * @deprecated As of 2025-01-14, this component is no longer used.
 * - citizen/business/accountant/funcionario manage their own profiles
 * - admin/agent users are edited via /admin/agents/[id]
 * - Kept for reference only
 *
 * PHASE 5.6 - Full i18n + new type system
 * - Pre-populates form with existing user data
 * - Optional password change
 * - Uses UserRole enum from src/types/user.ts
 * - Uses useUserLabels hook for role translation
 * - Aligned with Pydantic UserUpdate model
 *
 * @module users-admin/components
 * @author Claude Code
 * @date 2025-11-25
 */

import { useState, useEffect } from 'react'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import { useUserLabels } from '@/hooks/use-user-labels'
import usersApi from '../services/api'
import { UserRole } from '@/types/user'
import { useRoles } from '@/modules/roles-admin'
import type { Role } from '@/modules/roles-admin'
import type { User } from '../types'

interface EditUserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
  user: User | null
}

/**
 * All 6 user roles can be edited
 * Admin role prevents deletion only, not editing
 */
const EDITABLE_ROLES: UserRole[] = [
  UserRole.CITIZEN,
  UserRole.BUSINESS,
  UserRole.ACCOUNTANT,
  UserRole.ADMIN,
  UserRole.AGENT,
  UserRole.FUNCIONARIO,
]

export function EditUserDialog({ open, onOpenChange, onSuccess, user }: EditUserDialogProps) {
  const t = useTranslations('admin.users')
  const { toast } = useToast()
  const { getRoleLabel } = useUserLabels()

  // Fetch available custom roles
  const { data: rolesData, isLoading: rolesLoading } = useRoles({ is_system: false })
  const customRoles = rolesData?.roles || []

  const [isLoading, setIsLoading] = useState(false)
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    role: UserRole.CITIZEN as UserRole,
    role_id: '' as string | null,  // Custom role ID (optional)
    password: '', // Optional - only update if provided
  })

  // Populate form when user changes
  useEffect(() => {
    if (user) {
      setFormData({
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
        role: user.role as UserRole,
        role_id: user.role_id || '',
        password: '', // Always start empty
      })
    }
  }, [user])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return

    setIsLoading(true)

    try {
      // Build update payload - only include password if it was changed
      const updateData: any = {
        email: formData.email,
        first_name: formData.first_name,
        last_name: formData.last_name,
        role: formData.role,
      }

      // Include role_id if selected (null to clear, string to set)
      if (formData.role_id) {
        updateData.role_id = formData.role_id
      } else {
        updateData.role_id = null  // Explicitly clear custom role
      }

      // Only include password if user entered one
      if (formData.password.trim()) {
        updateData.password = formData.password
      }

      await usersApi.update(user.id, updateData)

      toast({
        title: t('userUpdated'),
        description: t('userUpdatedSuccess', {
          name: `${formData.first_name} ${formData.last_name}`,
        }),
      })

      onSuccess()
      onOpenChange(false)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: error instanceof Error ? error.message : t('errorUpdatingUser'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (!user) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{t('editDialogTitle')}</DialogTitle>
          <DialogDescription>{t('editDialogDescription')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {/* Email */}
            <div className="grid gap-2">
              <Label htmlFor="email">{t('emailRequired')}</Label>
              <Input
                id="email"
                type="email"
                placeholder={t('emailPlaceholder')}
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
              />
            </div>

            {/* First Name */}
            <div className="grid gap-2">
              <Label htmlFor="first_name">{t('firstNameRequired')}</Label>
              <Input
                id="first_name"
                type="text"
                placeholder={t('firstNamePlaceholder')}
                value={formData.first_name}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                required
                minLength={2}
                maxLength={50}
              />
            </div>

            {/* Last Name */}
            <div className="grid gap-2">
              <Label htmlFor="last_name">{t('lastNameRequired')}</Label>
              <Input
                id="last_name"
                type="text"
                placeholder={t('lastNamePlaceholder')}
                value={formData.last_name}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                required
                minLength={2}
                maxLength={50}
              />
            </div>

            {/* Role */}
            <div className="grid gap-2">
              <Label htmlFor="role">{t('roleRequired')}</Label>
              <Select
                value={formData.role}
                onValueChange={(value) => setFormData({ ...formData, role: value as UserRole })}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('selectRole')} />
                </SelectTrigger>
                <SelectContent>
                  {EDITABLE_ROLES.map((role) => (
                    <SelectItem key={role} value={role}>
                      {getRoleLabel(role)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Custom Role (Optional) */}
            <div className="grid gap-2">
              <Label htmlFor="role_id">{t('customRole') || 'Custom Role'}</Label>
              <Select
                value={formData.role_id || 'none'}
                onValueChange={(value) => setFormData({ ...formData, role_id: value === 'none' ? null : value })}
                disabled={rolesLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('selectCustomRole') || 'Select a custom role...'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">
                    {t('noCustomRole') || 'No custom role'}
                  </SelectItem>
                  {customRoles.map((role: Role) => (
                    <SelectItem key={role.id} value={role.id}>
                      {role.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                {t('customRoleDescription') || 'Assign a custom role for granular permissions beyond the base role.'}
              </p>
            </div>

            {/* Password (Optional) */}
            <div className="grid gap-2">
              <Label htmlFor="password">{t('changePasswordOptional')}</Label>
              <Input
                id="password"
                type="password"
                placeholder={t('passwordPlaceholder')}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                minLength={8}
                maxLength={100}
              />
              <p className="text-sm text-muted-foreground">{t('leaveEmptyToKeep')}</p>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isLoading}
            >
              {t('cancel')}
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? t('updating') : t('updateUserButton')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
