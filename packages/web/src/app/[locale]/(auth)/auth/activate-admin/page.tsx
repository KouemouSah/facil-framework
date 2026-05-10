'use client'

/**
 * Admin Account Activation Page
 * Allows invited admins to set their password and activate their account
 *
 * Flow:
 * 1. Admin receives email with activation link containing email and code
 * 2. Admin clicks link, lands here with pre-filled email/code
 * 3. Admin sets their password
 * 4. Account is created and admin can login
 *
 * Backend: POST /api/v1/agents/admin/activate
 */

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { Loader2, CheckCircle, ShieldCheck, Eye, EyeOff } from "lucide-react"
import Header from "@/components/layout/Header"
import Footer from "@/components/layout/Footer"
import { agentCreationApi } from "@/modules/agents-admin/services/api"
import { isPasswordStrong } from "@/core/validations/auth"
import { useLocale, useTranslations } from 'next-intl'

function ActivateAdminContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()
  const locale = useLocale()
  const t = useTranslations('auth.activateAdmin')

  // Form state
  const [email, setEmail] = useState("")
  const [verificationCode, setVerificationCode] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  // UI state
  const [isLoading, setIsLoading] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  const [isActivated, setIsActivated] = useState(false)

  useEffect(() => {
    setIsMounted(true)

    // Pre-fill from URL params if present
    const urlEmail = searchParams?.get('email')
    const urlCode = searchParams?.get('code')

    if (urlEmail) setEmail(urlEmail)
    if (urlCode) setVerificationCode(urlCode)
  }, [searchParams])

  const validateForm = (): boolean => {
    if (!email) {
      toast({
        variant: "destructive",
        title: t('emailRequired'),
        description: t('emailRequiredDesc'),
      })
      return false
    }

    if (verificationCode.length !== 6) {
      toast({
        variant: "destructive",
        title: t('codeInvalid'),
        description: t('codeInvalidDesc'),
      })
      return false
    }

    if (!isPasswordStrong(password)) {
      toast({
        variant: "destructive",
        title: t('passwordWeak'),
        description: t('passwordWeakDesc'),
      })
      return false
    }

    if (password !== confirmPassword) {
      toast({
        variant: "destructive",
        title: t('passwordsMismatch'),
        description: t('passwordsMismatchDesc'),
      })
      return false
    }

    return true
  }

  const handleActivate = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    setIsLoading(true)

    try {
      const response = await agentCreationApi.activateAdmin({
        email,
        verification_code: verificationCode,
        password,
      })

      setIsActivated(true)

      toast({
        title: t('activationSuccess'),
        description: response.message || t('activationSuccessDesc'),
      })

      // Redirect to login after 2 seconds
      setTimeout(() => {
        router.push(`/${locale}/auth`)
      }, 2000)

    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : t('activationError')
      toast({
        variant: "destructive",
        title: t('activationErrorTitle'),
        description: errorMessage,
      })
    } finally {
      setIsLoading(false)
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

  // Show success message
  if (isActivated) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 container mx-auto px-4 py-12">
          <div className="max-w-md mx-auto text-center">
            <div className="flex justify-center mb-4">
              <CheckCircle className="h-16 w-16 text-green-500" />
            </div>
            <h1 className="text-2xl font-bold mb-2">{t('accountActivated')}</h1>
            <p className="text-muted-foreground mb-4">
              {t('accountActivatedDesc')}
            </p>
            <Button onClick={() => router.push(`/${locale}/auth`)}>
              {t('loginNow')}
            </Button>
          </div>
        </main>
        <Footer />
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
              <ShieldCheck className="h-16 w-16 text-primary" />
            </div>
            <h1 className="text-3xl font-bold mb-2">{t('pageTitle')}</h1>
            <p className="text-muted-foreground">
              {t('pageSubtitle')}
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t('cardTitle')}</CardTitle>
              <CardDescription>
                {t('cardDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleActivate} className="space-y-4">
                {/* Email */}
                <div className="space-y-2">
                  <Label htmlFor="email">{t('emailLabel')}</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder={t('emailPlaceholder')}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    maxLength={254}
                    disabled={isLoading || !!searchParams?.get('email')}
                  />
                </div>

                {/* Verification Code */}
                <div className="space-y-2">
                  <Label htmlFor="code">{t('verificationCodeLabel')}</Label>
                  <Input
                    id="code"
                    type="text"
                    placeholder="000000"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    maxLength={6}
                    required
                    disabled={isLoading}
                    className="text-center text-2xl tracking-widest"
                  />
                  <p className="text-sm text-muted-foreground">
                    {t('verificationCodeHint')}
                  </p>
                </div>

                {/* Password */}
                <div className="space-y-2">
                  <Label htmlFor="password">{t('passwordLabel')}</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder={t('passwordPlaceholder')}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      disabled={isLoading}
                      maxLength={100}
                      minLength={8}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Confirm Password */}
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">{t('confirmPasswordLabel')}</Label>
                  <div className="relative">
                    <Input
                      id="confirmPassword"
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder={t('confirmPasswordPlaceholder')}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      disabled={isLoading}
                      maxLength={100}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    >
                      {showConfirmPassword ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Submit Button */}
                <Button
                  type="submit"
                  className="w-full"
                  disabled={isLoading || verificationCode.length !== 6 || !isPasswordStrong(password) || password !== confirmPassword}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('activating')}
                    </>
                  ) : (
                    <>
                      <CheckCircle className="mr-2 h-4 w-4" />
                      {t('activateButton')}
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Help text */}
          <p className="text-sm text-center text-muted-foreground mt-4">
            {t('alreadyHaveAccount')}{' '}
            <Button variant="link" className="p-0" onClick={() => router.push(`/${locale}/auth`)}>
              {t('loginLink')}
            </Button>
          </p>
        </div>
      </main>

      <Footer />
    </div>
  )
}

export default function ActivateAdminPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <ActivateAdminContent />
    </Suspense>
  )
}
