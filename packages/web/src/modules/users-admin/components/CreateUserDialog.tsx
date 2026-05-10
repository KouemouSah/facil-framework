'use client'

/**
 * Create User Dialog Component
 * Dialog for creating new administrative users with full i18n
 *
 * @deprecated As of 2025-01-14, this component is no longer used.
 * - citizen/business/accountant/funcionario users self-register
 * - admin/agent users are created via /admin/agents/new
 * - Kept for reference only
 *
 * MIGRATED: Phase 5.3 - Full i18n + new type system
 * - Uses useTranslations() for all labels
 * - Uses UserRole enum from src/types/user.ts
 * - Uses useUserLabels hook for role translation
 * - Aligned with Pydantic UserCreate model
 *
 * @module users-admin/components
 * @author Claude Code
 * @date 2025-11-25
 */

import { useState } from 'react'
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

interface CreateUserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

/**
 * Administrative roles that can be created via this dialog
 * Excludes citizen and business (those register via public form)
 * Agent type specifics are managed via agent_profiles table
 */
const CREATABLE_ROLES: UserRole[] = [
  UserRole.ADMIN,
  UserRole.AGENT,
  UserRole.ACCOUNTANT,
  UserRole.FUNCIONARIO,
]

export function CreateUserDialog({ open, onOpenChange, onSuccess }: CreateUserDialogProps) {
  const t = useTranslations('admin.users')
  const _tCommon = useTranslations('admin')
  const { toast } = useToast()
  const { getRoleLabel } = useUserLabels()

  const [isLoading, setIsLoading] = useState(false)
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    role: UserRole.AGENT as UserRole,
    password: '',
    is_active: true,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await usersApi.create(formData)

      toast({
        title: t('userCreated'),
        description: t('userCreatedSuccess', {
          name: `${formData.first_name} ${formData.last_name}`,
        }),
      })

      // Reset form
      setFormData({
        email: '',
        first_name: '',
        last_name: '',
        role: UserRole.AGENT,
        password: '',
        is_active: true,
      })

      onSuccess()
      onOpenChange(false)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: error instanceof Error ? error.message : t('errorCreatingUser'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{t('createDialogTitle')}</DialogTitle>
          <DialogDescription>{t('createDialogDescription')}</DialogDescription>
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
                  {CREATABLE_ROLES.map((role) => (
                    <SelectItem key={role} value={role}>
                      {getRoleLabel(role)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">{t('onlyAdminRoles')}</p>
            </div>

            {/* Password */}
            <div className="grid gap-2">
              <Label htmlFor="password">{t('passwordRequired')}</Label>
              <Input
                id="password"
                type="password"
                placeholder={t('passwordPlaceholder')}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                required
                minLength={8}
                maxLength={100}
              />
              <p className="text-sm text-muted-foreground">{t('passwordMinLength')}</p>
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
              {isLoading ? t('creating') : t('createUserButton')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
