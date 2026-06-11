'use client'

/**
 * Password Reset Confirm Page
 * Allows users to set a new password using their reset token
 * Backend: POST /auth/password/reset/confirm
 * URL: /auth/reset-password/confirm?token=xxx
 */

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { Loader2, CheckCircle, Lock } from "lucide-react"
import Header from "@/components/layout/Header"
import Footer from "@/components/layout/Footer"
import { authApi } from "@/core/api/auth"
import { useLocale, useTranslations } from 'next-intl'

function ResetPasswordConfirmContent() {
  const router = useRouter()
  const { toast } = useToast()
  const searchParams = useSearchParams()
  const locale = useLocale()
  const t = useTranslations('auth')

  const [token, setToken] = useState<string | null>(null)
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [passwordErrors, setPasswordErrors] = useState<string[]>([])

  useEffect(() => {
    const tokenParam = searchParams.get('token')
    if (!tokenParam) {
      toast({
        variant: "destructive",
        title: t('tokenMissing'),
        description: t('tokenMissingMessage'),
      })
      router.push(`/${locale}/auth/reset-password`)
    } else {
      setToken(tokenParam)
    }
  }, [searchParams, router, toast, locale, t])

  const validatePassword = (password: string): string[] => {
    const errors: string[] = []

    if (password.length < 8) {
      errors.push(t('minCharacters'))
    }
    if (!/[A-Z]/.test(password)) {
      errors.push(t('oneUppercase'))
    }
    if (!/[a-z]/.test(password)) {
      errors.push(t('oneLowercase'))
    }
    if (!/[0-9]/.test(password)) {
      errors.push(t('oneNumber'))
    }

    return errors
  }

  const handlePasswordChange = (value: string) => {
    setNewPassword(value)
    setPasswordErrors(validatePassword(value))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!token) {
      toast({
        variant: "destructive",
        title: t('resendError'),
        description: t('invalidToken'),
      })
      return
    }

    const errors = validatePassword(newPassword)
    if (errors.length > 0) {
      toast({
        variant: "destructive",
        title: t('weakPassword'),
        description: errors.join(", "),
      })
      return
    }

    if (newPassword !== confirmPassword) {
      toast({
        variant: "destructive",
        title: t('passwordMismatch'),
        description: t('passwordMismatchMessage'),
      })
      return
    }

    setIsLoading(true)

    try {
      await authApi.confirmPasswordReset({
        token,
        new_password: newPassword,
      })

      toast({
        title: t('passwordResetSuccess'),
        description: t('passwordResetSuccessMessage'),
      })

      setTimeout(() => {
        router.push(`/${locale}/auth`)
      }, 2000)
    } catch (error: unknown) {
      toast({
        variant: "destructive",
        title: t('passwordResetError'),
        description: error instanceof Error ? error.message : t('passwordResetErrorMessage'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 container mx-auto px-4 py-12">
        <div className="max-w-md mx-auto">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="h-16 w-16 bg-primary/10 rounded-full flex items-center justify-center">
                <Lock className="h-8 w-8 text-primary" />
              </div>
            </div>
            <h1 className="text-4xl font-bold mb-2">{t('resetPasswordConfirmTitle')}</h1>
            <p className="text-muted-foreground">
              {t('resetPasswordConfirmSubtitle')}
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t('resetPasswordConfirmCardTitle')}</CardTitle>
              <CardDescription>
                {t('resetPasswordConfirmCardDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="new-password">{t('newPassword')}</Label>
                  <Input
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder={t('passwordPlaceholder')}
                    value={newPassword}
                    onChange={(e) => handlePasswordChange(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                  {newPassword && (
                    <div className="text-sm space-y-1">
                      <p className={passwordErrors.length === 0 ? "text-green-600" : "text-muted-foreground"}>
                        {t('securityCriteria')}
                      </p>
                      <ul className="list-disc list-inside space-y-1">
                        <li className={newPassword.length >= 8 ? "text-green-600" : "text-muted-foreground"}>
                          {t('minCharacters')} {newPassword.length >= 8 && "✓"}
                        </li>
                        <li className={/[A-Z]/.test(newPassword) ? "text-green-600" : "text-muted-foreground"}>
                          {t('oneUppercase')} {/[A-Z]/.test(newPassword) && "✓"}
                        </li>
                        <li className={/[a-z]/.test(newPassword) ? "text-green-600" : "text-muted-foreground"}>
                          {t('oneLowercase')} {/[a-z]/.test(newPassword) && "✓"}
                        </li>
                        <li className={/[0-9]/.test(newPassword) ? "text-green-600" : "text-muted-foreground"}>
                          {t('oneNumber')} {/[0-9]/.test(newPassword) && "✓"}
                        </li>
                      </ul>
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirm-password">{t('confirmNewPassword')}</Label>
                  <Input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder={t('passwordPlaceholder')}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                  {confirmPassword && (
                    <p className={newPassword === confirmPassword ? "text-green-600 text-sm" : "text-destructive text-sm"}>
                      {newPassword === confirmPassword ? t('passwordsMatch') : t('passwordsDontMatch')}
                    </p>
                  )}
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isLoading || passwordErrors.length > 0 || newPassword !== confirmPassword}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('resettingButton')}
                    </>
                  ) : (
                    <>
                      <CheckCircle className="mr-2 h-4 w-4" />
                      {t('resetPasswordButton')}
                    </>
                  )}
                </Button>

                <div className="text-center pt-2">
                  <Link href={`/${locale}/auth`}>
                    <Button variant="link" className="text-sm">
                      {t('cancelButton')}
                    </Button>
                  </Link>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  )
}

export default function ResetPasswordConfirmPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <ResetPasswordConfirmContent />
    </Suspense>
  )
}
