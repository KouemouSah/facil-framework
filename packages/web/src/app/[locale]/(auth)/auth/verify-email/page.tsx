'use client'

/**
 * Email Verification Page
 * Allows users to enter their 6-digit verification code
 * Backend: POST /auth/email/verify
 */

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { Loader2, CheckCircle, Mail } from "lucide-react"
import Header from "@/components/layout/Header"
import Footer from "@/components/layout/Footer"
import { authApi } from "@/core/api/auth"
import { getAuthData } from "@/core/auth/storage"
import { useLocale, useTranslations } from 'next-intl'

function VerifyEmailContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()
  const locale = useLocale()
  const t = useTranslations('auth')

  const [verificationCode, setVerificationCode] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isResending, setIsResending] = useState(false)
  const [userEmail, setUserEmail] = useState<string | undefined>(undefined)
  const [isMounted, setIsMounted] = useState(false)
  const [context, setContext] = useState<string>('registration') // registration | password_change | password_reset

  useEffect(() => {
    setIsMounted(true)

    // Get context from URL
    const urlContext = searchParams?.get('context') || 'registration'
    setContext(urlContext)

    // Handle different contexts
    if (urlContext === 'password_change') {
      // Password change context - get email from sessionStorage
      const email = sessionStorage.getItem('password_change_email')
      if (!email) {
        toast({
          variant: 'destructive',
          title: t('sessionExpired'),
          description: t('sessionExpiredMessage'),
        })
        router.push(`/${locale}/dashboard/settings/security`)
        return
      }
      setUserEmail(email)
    } else {
      // Original logic for registration context
      const pendingData = sessionStorage.getItem('pending_registration')
      if (!pendingData) {
        // No pending registration - check if user is already authenticated
        const authData = getAuthData()
        if (!authData) {
          router.push(`/${locale}/auth`)
          return
        }
        setUserEmail(authData.user?.email)
      } else {
        // Has pending registration data - parse and set email
        try {
          const data = JSON.parse(pendingData)
          // Auto-cleanup if data is older than 30 minutes
          if (data._ts && Date.now() - data._ts > 30 * 60 * 1000) {
            sessionStorage.removeItem('pending_registration')
            router.push(`/${locale}/auth`)
            return
          }
          setUserEmail(data.email)
        } catch {
          sessionStorage.removeItem('pending_registration')
          router.push(`/${locale}/auth`)
        }
      }
    }
  }, [router, searchParams, toast, locale, t])

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()

    if (verificationCode.length !== 6) {
      toast({
        variant: "destructive",
        title: t('invalidCode'),
        description: t('invalidCodeMessage'),
      })
      return
    }

    setIsLoading(true)

    try {
      // Handle password change context
      if (context === 'password_change') {
        const email = sessionStorage.getItem('password_change_email')

        // Check empty first
        if (!email || !newPassword) {
          toast({
            variant: 'destructive',
            title: t('sessionExpired'),
            description: t('sessionExpiredMessage'),
          })
          if (!email) router.push(`/${locale}/dashboard/settings/security`)
          setIsLoading(false)
          return
        }

        // Check passwords match
        if (newPassword !== confirmPassword) {
          toast({
            variant: 'destructive',
            title: t('verificationError'),
            description: t('passwordsDoNotMatch'),
          })
          setIsLoading(false)
          return
        }

        // Validate password strength (same rules as registration)
        if (newPassword.length < 8 || !/[A-Z]/.test(newPassword) || !/[a-z]/.test(newPassword) || !/[0-9]/.test(newPassword) || !/[^A-Za-z0-9]/.test(newPassword)) {
          toast({
            variant: 'destructive',
            title: t('verificationError'),
            description: t('passwordRequirements'),
          })
          setIsLoading(false)
          return
        }

        // Verify password change — new password from form input (never sessionStorage)
        const { authApi: passwordApi } = await import('@/core/api/auth')
        await passwordApi.verifyPasswordChange({
          email,
          verification_code: verificationCode,
          new_password: newPassword,
        })

        // Clear sensitive state + session storage
        setNewPassword('')
        setConfirmPassword('')
        sessionStorage.removeItem('password_change_email')

        toast({
          title: t('passwordChangedSuccess'),
          description: t('passwordChangedMessage'),
        })

        setTimeout(() => {
          router.push(`/${locale}/dashboard`)
        }, 1500)
        return
      }

      // Original registration/email verification logic
      const pendingData = sessionStorage.getItem('pending_registration')

      if (pendingData) {
        // NEW USER REGISTRATION - Complete registration with verification code
        const registrationData = JSON.parse(pendingData)

        const response = await authApi.register({
          email: registrationData.email,
          verification_code: verificationCode,
          password: registrationData.password,
          first_name: registrationData.first_name,
          last_name: registrationData.last_name,
          phone: registrationData.phone,
          role: registrationData.role,
        })

        // Store auth tokens
        const { setAuthData } = await import("@/core/auth/storage")
        setAuthData(response)

        // Clear pending registration data
        sessionStorage.removeItem('pending_registration')

        toast({
          title: t('accountCreated'),
          description: t('accountCreatedMessage', {
            firstName: registrationData.first_name,
            lastName: registrationData.last_name
          }),
        })

        setTimeout(() => {
          router.push(`/${locale}/dashboard`)
        }, 1500)
      } else {
        // EXISTING USER - Email verification only
        const authData = getAuthData()

        if (!authData?.access_token) {
          toast({
            variant: "destructive",
            title: t('notAuthenticated'),
            description: t('notAuthenticatedMessage'),
          })
          router.push(`/${locale}/auth`)
          return
        }

        await authApi.verifyEmail({ verification_code: verificationCode }, authData.access_token)

        toast({
          title: t('emailVerified'),
          description: t('emailVerifiedMessage'),
        })

        setTimeout(() => {
          router.push(`/${locale}/dashboard`)
        }, 1500)
      }
    } catch (error: unknown) {
      toast({
        variant: "destructive",
        title: t('verificationError'),
        description: error instanceof Error ? error.message : t('verificationErrorMessage'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleResend = async () => {
    setIsResending(true)

    try {
      // Check if this is from registration or existing user
      const pendingData = sessionStorage.getItem('pending_registration')

      if (pendingData) {
        // NEW USER - Resend verification code for registration
        const registrationData = JSON.parse(pendingData)
        await authApi.requestVerificationCode(registrationData.email)

        toast({
          title: t('codeResent'),
          description: t('codeResentMessage', { email: registrationData.email }),
        })
      } else {
        // EXISTING USER - Resend email verification
        const authData = getAuthData()

        if (!authData?.access_token) {
          toast({
            variant: "destructive",
            title: t('notAuthenticated'),
            description: t('notAuthenticatedMessage'),
          })
          return
        }

        const result = await authApi.resendEmailVerification(authData.access_token)

        toast({
          title: t('codeResent'),
          description: t('codeResentMessage', { email: result.email }),
        })
      }
    } catch (error: unknown) {
      toast({
        variant: "destructive",
        title: t('resendError'),
        description: error instanceof Error ? error.message : t('resendErrorMessage'),
      })
    } finally {
      setIsResending(false)
    }
  }

  // Show loading state during SSR
  if (!isMounted) {
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
              <Mail className="h-16 w-16 text-primary" />
            </div>
            <h1 className="text-4xl font-bold mb-2">{t('verifyEmailTitle')}</h1>
            <p className="text-muted-foreground">
              {t('verifyEmailSubtitle', { email: userEmail })}
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t('verifyEmailCardTitle')}</CardTitle>
              <CardDescription>
                {t('verifyEmailCardDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleVerify} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="code">{t('verificationCodeLabel')}</Label>
                  <Input
                    id="code"
                    type="text"
                    placeholder={t('verificationCodePlaceholder')}
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    maxLength={6}
                    required
                    disabled={isLoading}
                    className="text-center text-2xl tracking-widest"
                  />
                  <p className="text-sm text-muted-foreground">
                    {t('codeExpiry')}
                  </p>
                </div>

                {context === 'password_change' && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="newPassword">{t('newPasswordLabel')}</Label>
                      <Input
                        id="newPassword"
                        type="password"
                        autoComplete="new-password"
                        placeholder={t('newPasswordPlaceholder')}
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        minLength={8}
                        maxLength={100}
                        required
                        disabled={isLoading}
                      />
                      <p className="text-sm text-muted-foreground">
                        {t('passwordRequirements')}
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirmPassword">{t('confirmPasswordLabel')}</Label>
                      <Input
                        id="confirmPassword"
                        type="password"
                        autoComplete="new-password"
                        placeholder={t('newPasswordPlaceholder')}
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        minLength={8}
                        maxLength={100}
                        required
                        disabled={isLoading}
                      />
                    </div>
                  </>
                )}

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isLoading || verificationCode.length !== 6 || (context === 'password_change' && (newPassword.length < 8 || newPassword !== confirmPassword))}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('verifyEmailButtonLoading')}
                    </>
                  ) : (
                    <>
                      <CheckCircle className="mr-2 h-4 w-4" />
                      {t('verifyEmailButton')}
                    </>
                  )}
                </Button>

                <div className="space-y-2 pt-4 border-t">
                  <p className="text-sm text-center text-muted-foreground">
                    {t('didntReceiveCode')}
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleResend}
                    disabled={isResending}
                    className="w-full"
                  >
                    {isResending ? t('resendingButton') : t('resendCodeButton')}
                  </Button>
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

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  )
}
