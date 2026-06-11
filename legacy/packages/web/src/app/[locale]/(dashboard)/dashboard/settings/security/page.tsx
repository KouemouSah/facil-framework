'use client'

/**
 * Security Settings Page
 * Centralized security management:
 * - Password change
 * - Two-Factor Authentication (2FA)
 * - Active sessions
 */

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useToast } from '@/hooks/use-toast'
import { Shield, Lock } from 'lucide-react'
import { getAuthData, clearAuthData } from '@/core/auth/storage'
import TwoFactorToggle from '@/components/security/TwoFactorToggle'
import type { User as UserType } from '@/types/auth'
import { useLocale, useTranslations } from 'next-intl'

export default function SecuritySettingsPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('settings')
  const { toast } = useToast()
  const [user, setUser] = useState<UserType | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordChangeLoading, setPasswordChangeLoading] = useState(false)

  useEffect(() => {
    const authData = getAuthData()

    if (!authData) {
      router.push(`/${locale}/auth`)
      return
    }

    setUser(authData.user)
    setIsLoading(false)
  }, [router, locale])

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()

    // Validation
    if (newPassword !== confirmPassword) {
      toast({
        variant: 'destructive',
        title: t('passwordError'),
        description: t('passwordMismatch'),
      })
      return
    }

    if (newPassword.length < 8) {
      toast({
        variant: 'destructive',
        title: t('passwordTooShort'),
        description: t('passwordTooShortMessage'),
      })
      return
    }

    // Password strength validation
    if (!/[A-Z]/.test(newPassword)) {
      toast({
        variant: 'destructive',
        title: t('passwordWeak'),
        description: t('passwordNoUppercase'),
      })
      return
    }
    if (!/[a-z]/.test(newPassword)) {
      toast({
        variant: 'destructive',
        title: t('passwordWeak'),
        description: t('passwordNoLowercase'),
      })
      return
    }
    if (!/[0-9]/.test(newPassword)) {
      toast({
        variant: 'destructive',
        title: t('passwordWeak'),
        description: t('passwordNoNumber'),
      })
      return
    }
    if (!/[^A-Za-z0-9]/.test(newPassword)) {
      toast({
        variant: 'destructive',
        title: t('passwordWeak'),
        description: t('passwordNoSpecialChar'),
      })
      return
    }

    setPasswordChangeLoading(true)

    try {
      // Direct password change (no verification code step)
      // Calls POST /api/v1/users/profile/change-password
      // Backend sends email + SMS notifications after successful change
      const { profileApi } = await import('@/modules/users')
      await profileApi.changePassword({
        old_password: currentPassword,
        new_password: newPassword,
      })

      // Success - password changed directly
      toast({
        title: t('passwordChangedSuccess'),
        description: t('passwordChangedMessage'),
      })

      // Reset form fields
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')

      // For security: logout user and redirect to login page
      // Wait 2 seconds for user to read the success message
      setTimeout(() => {
        clearAuthData()
        router.push(`/${locale}/auth`)
      }, 2000)

    } catch (error: unknown) {
      toast({
        variant: 'destructive',
        title: t('passwordError'),
        description: error instanceof Error ? error.message : t('passwordChangeFailed'),
      })
    } finally {
      setPasswordChangeLoading(false)
    }
  }

  if (isLoading || !user) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto"></div>
          <p className="text-muted-foreground">{t('loading')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
          {t('securityTitle')}
        </h1>
        <p className="text-muted-foreground mt-2">
          {t('securitySubtitle')}
        </p>
      </div>

      {/* 2 Blocs côte à côte : Mot de passe | Authentification 2FA */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bloc 1 : Mot de passe */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" />
              {t('passwordCardTitle')}
            </CardTitle>
            <CardDescription>
              {t('passwordCardDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordChange} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="current-password">{t('currentPassword')}</Label>
                <Input
                  id="current-password"
                  type="password"
                  autoComplete="current-password"
                  placeholder={t('currentPasswordPlaceholder')}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="new-password">{t('newPassword')}</Label>
                <Input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder={t('newPasswordPlaceholder')}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  {t('passwordRequirements')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm-password">{t('confirmPassword')}</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder={t('confirmPasswordPlaceholder')}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>

              <Button type="submit" className="w-full" disabled={passwordChangeLoading}>
                {passwordChangeLoading ? t('changePasswordButtonLoading') : t('changePasswordButton')}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Bloc 2 : Authentification 2FA */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              {t('twoFactorCardTitle')}
            </CardTitle>
            <CardDescription>
              {t('twoFactorCardDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TwoFactorToggle
              initialEnabled={user.two_factor_enabled || false}
              onStatusChange={(enabled) => {
                setUser(prev => prev ? { ...prev, two_factor_enabled: enabled } : null)
              }}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
