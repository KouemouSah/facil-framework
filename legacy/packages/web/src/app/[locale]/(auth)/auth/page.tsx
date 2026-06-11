'use client'

/**
 * Page d'authentification unifiée (Login + Register)
 * Design basé sur le template Auth.tsx
 * Backend API: https://taxasge-backend-staging-xrlbgdr5eq-uc.a.run.app/api/v1
 */

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Checkbox } from "@/components/ui/checkbox"
import { useToast } from "@/hooks/use-toast"
import { User, Building2, Shield } from "lucide-react"
import Header from "@/components/layout/Header"
import Footer from "@/components/layout/Footer"
import { authApi } from "@/core/api/auth"
import { setAuthData } from "@/core/auth/storage"
import { loginSchema } from "@/core/validations/auth"
import { z } from "zod"
import { useLocale, useTranslations } from 'next-intl'

export default function AuthPage() {
  const router = useRouter()
  const { toast } = useToast()
  const locale = useLocale()
  const t = useTranslations('auth')

  // État Login
  const [loginEmail, setLoginEmail] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [rememberMe, setRememberMe] = useState(false)
  const [loginLoading, setLoginLoading] = useState(false)
  const [accountLocked, setAccountLocked] = useState(false)
  const [lockoutSecondsRemaining, setLockoutSecondsRemaining] = useState(0)

  // État 2FA
  const [requires2FA, setRequires2FA] = useState(false)
  const [tempToken, setTempToken] = useState("")
  const [twoFactorCode, setTwoFactorCode] = useState("")
  const [twoFactorExpired, setTwoFactorExpired] = useState(false)

  // État Register
  const [registerEmail, setRegisterEmail] = useState("")
  const [registerPassword, setRegisterPassword] = useState("")
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [phone, setPhone] = useState("")
  const [role, setRole] = useState<"citizen" | "business">("citizen")
  const [registerLoading, setRegisterLoading] = useState(false)

  // État erreurs
  const [loginErrors, setLoginErrors] = useState<Record<string, string>>({})
  const [registerErrors, setRegisterErrors] = useState<Record<string, string>>({})

  // Lockout countdown timer
  useEffect(() => {
    // Check for existing lockout on mount
    const checkLockout = () => {
      const lockoutData = localStorage.getItem('account_lockout')
      if (lockoutData) {
        try {
          const { lockedUntil, email } = JSON.parse(lockoutData)
          const lockedUntilDate = new Date(lockedUntil)
          const now = new Date()

          if (now < lockedUntilDate) {
            // Still locked
            const remainingSeconds = Math.floor((lockedUntilDate.getTime() - now.getTime()) / 1000)
            setAccountLocked(true)
            setLockoutSecondsRemaining(remainingSeconds)
            setLoginEmail(email)
          } else {
            // Lockout expired
            localStorage.removeItem('account_lockout')
            setAccountLocked(false)
            setLockoutSecondsRemaining(0)
          }
        } catch {
          // Invalid data, remove it
          localStorage.removeItem('account_lockout')
        }
      }
    }

    checkLockout()

    // Countdown interval
    const interval = setInterval(() => {
      setLockoutSecondsRemaining((prev) => {
        if (prev <= 1) {
          // Lockout expired
          setAccountLocked(false)
          localStorage.removeItem('account_lockout')
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  // Handler Login
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginErrors({})
    setLoginLoading(true)

    try {
      // Validation Zod
      const validated = loginSchema.parse({
        email: loginEmail,
        password: loginPassword,
        remember_me: rememberMe,
      })

      // Appel API
      const response = await authApi.login(validated)

      // Stockage tokens + user
      // Check if 2FA is required
      if ('requires_2fa' in response && response.requires_2fa) {
        // 2FA is enabled - show 2FA code input
        setRequires2FA(true)
        setTwoFactorExpired(false)
        setTempToken(response.temp_token)
        // Auto-expire 2FA form after 5 minutes (matches backend temp_token TTL)
        setTimeout(() => {
          setTwoFactorExpired(true)
        }, 5 * 60 * 1000)
        toast({
          title: t('twoFactorRequiredToast'),
          description: t('twoFactorRequiredMessage'),
        })
        return
      }

      // Standard login (no 2FA) - TypeScript now knows response is TokenResponse
      if ('access_token' in response) {
        // Validate role - agents and admins should use /auth/agent portal
        const staffRoles = ['agent', 'admin']
        if (staffRoles.includes(response.user.role)) {
          toast({
            variant: 'destructive',
            title: t('accessDenied'),
            description: t('userOnlyPortal'),
            action: (
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push(`/${locale}/auth/agent`)}
              >
                {t('useAgentPortal')}
              </Button>
            ),
          })
          setLoginLoading(false)
          return
        }

        setAuthData(response)

        // Toast succès
        toast({
          title: t('loginSuccess'),
          description: t('loginWelcome', { name: response.user.first_name || response.user.email }),
        })

        // Redirect to dashboard
        // Note: Email verification is mandatory during registration,
        // so all accounts are pre-verified. No need to check email_verified here.
        setTimeout(() => {
          router.push(`/${locale}/dashboard`)
        }, 500)
      }
    } catch (error: unknown) {
      if (error instanceof z.ZodError) {
        // Erreurs validation
        const errors: Record<string, string> = {}
        error.errors.forEach((err) => {
          if (err.path[0]) {
            errors[err.path[0].toString()] = err.message
          }
        })
        setLoginErrors(errors)
      } else {
        // Erreurs API
        const errorMessage = error instanceof Error ? error.message : t('invalidCredentials')

        // Check for account lockout error (handles both "minute" and "minutes")
        const lockoutMatch = errorMessage.match(/Account locked\. Try again in (\d+) minutes?\./)
        if (lockoutMatch) {
          const remainingMinutes = parseInt(lockoutMatch[1])
          const remainingSeconds = remainingMinutes * 60
          const lockedUntil = new Date(Date.now() + remainingSeconds * 1000)

          // Store lockout info in localStorage
          localStorage.setItem('account_lockout', JSON.stringify({
            email: loginEmail,
            lockedUntil: lockedUntil.toISOString()
          }))

          // Update UI state
          setAccountLocked(true)
          setLockoutSecondsRemaining(remainingSeconds)

          toast({
            variant: "destructive",
            title: t('accountLockedTitle'),
            description: t('accountLockedError', { minutes: remainingMinutes }),
          })
        } else {
          toast({
            variant: "destructive",
            title: t('loginError'),
            description: errorMessage,
          })
        }
      }
    } finally {
      setLoginLoading(false)
    }
  }

  // Handler 2FA Verification
  const handle2FAVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginLoading(true)

    try {
      // Check if temp_token has expired (5min backend TTL)
      if (twoFactorExpired) {
        toast({
          variant: "destructive",
          title: t('sessionExpired') || "Sesión expirada",
          description: t('twoFactorExpiredMessage') || "El código temporal ha expirado. Inicie sesión nuevamente.",
        })
        setRequires2FA(false)
        setTempToken("")
        setTwoFactorCode("")
        setLoginLoading(false)
        return
      }

      // Validate 2FA code
      if (twoFactorCode.length !== 6) {
        toast({
          variant: "destructive",
          title: t('invalidCode'),
          description: t('invalidCodeMessage'),
        })
        setLoginLoading(false)
        return
      }

      // Call 2FA verification API
      const response = await authApi.verify2FA({
        temp_token: tempToken,
        code: twoFactorCode,
      })

      // Validate role - agents and admins should use /auth/agent portal
      const staffRoles = ['agent', 'admin']
      if (staffRoles.includes(response.user.role)) {
        toast({
          variant: 'destructive',
          title: t('accessDenied'),
          description: t('userOnlyPortal'),
          action: (
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push(`/${locale}/auth/agent`)}
            >
              {t('useAgentPortal')}
            </Button>
          ),
        })
        setLoginLoading(false)
        setRequires2FA(false)
        setTempToken('')
        setTwoFactorCode('')
        return
      }

      // Store tokens and user data
      setAuthData(response)

      // Success toast
      toast({
        title: t('loginSuccess'),
        description: t('loginWelcome', { name: response.user.first_name || response.user.email }),
      })

      // Redirect to dashboard
      setTimeout(() => {
        router.push(`/${locale}/dashboard`)
      }, 500)
    } catch (error: unknown) {
      toast({
        variant: "destructive",
        title: t('invalidTwoFactorCode'),
        description: error instanceof Error ? error.message : t('invalidTwoFactorMessage'),
      })
    } finally {
      setLoginLoading(false)
    }
  }

  // Handler Register: Send verification code and redirect to verify-email page
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setRegisterErrors({})
    setRegisterLoading(true)

    try {
      // Validate all required fields
      if (!registerEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registerEmail)) {
        setRegisterErrors({ email: t('validationEmailInvalid') })
        setRegisterLoading(false)
        return
      }
      if (!firstName || firstName.length < 2) {
        setRegisterErrors({ first_name: t('validationFirstName') })
        setRegisterLoading(false)
        return
      }
      if (!lastName || lastName.length < 2) {
        setRegisterErrors({ last_name: t('validationLastName') })
        setRegisterLoading(false)
        return
      }
      if (!phone || !/^(222|555|551|333)\d{6}$/.test(phone)) {
        setRegisterErrors({ phone: t('validationPhone') })
        setRegisterLoading(false)
        return
      }
      if (!registerPassword || registerPassword.length < 8) {
        setRegisterErrors({ password: t('validationPasswordLength') })
        setRegisterLoading(false)
        return
      }

      // Password strength validation
      if (!/[A-Z]/.test(registerPassword)) {
        setRegisterErrors({ password: t('validationPasswordUppercase') })
        setRegisterLoading(false)
        return
      }
      if (!/[a-z]/.test(registerPassword)) {
        setRegisterErrors({ password: t('validationPasswordLowercase') })
        setRegisterLoading(false)
        return
      }
      if (!/[0-9]/.test(registerPassword)) {
        setRegisterErrors({ password: t('validationPasswordNumber') })
        setRegisterLoading(false)
        return
      }
      if (!/[^A-Za-z0-9]/.test(registerPassword)) {
        setRegisterErrors({ password: t('validationPasswordSpecial') })
        setRegisterLoading(false)
        return
      }

      // Store registration data in sessionStorage (NOT localStorage — avoids XSS exposure)
      // Password stored temporarily — cleared after successful registration or after 30min
      sessionStorage.setItem('pending_registration', JSON.stringify({
        email: registerEmail,
        password: registerPassword,
        first_name: firstName,
        last_name: lastName,
        phone: phone,
        role: role,
        _ts: Date.now(),
      }))

      // Request verification code (automatically sends email)
      await authApi.requestVerificationCode(registerEmail)

      // Redirect to verify-email page immediately
      router.push(`/${locale}/auth/verify-email`)

      // Show success toast after redirect starts
      toast({
        title: t('registrationCodeSent'),
        description: t('registrationCodeSentMessage', { email: registerEmail }),
      })
    } catch (error: unknown) {
      // If email sending fails, show appropriate error message
      const errorMsg = error instanceof Error ? error.message : t('registrationError')

      // Check if error is email-related
      if (errorMsg.includes('email') || errorMsg.includes('SMTP') || errorMsg.includes('envoi')) {
        toast({
          variant: "destructive",
          title: t('registrationEmailError'),
          description: t('registrationEmailErrorMessage'),
        })
      } else {
        toast({
          variant: "destructive",
          title: t('registrationError'),
          description: errorMsg,
        })
      }
    } finally {
      setRegisterLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* Main Content */}
      <main className="flex-1 container mx-auto px-4 py-12">
        <div className="max-w-md mx-auto">
          {/* Header Text */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold mb-2">{t('welcome')}</h1>
            <p className="text-muted-foreground">
              {t('welcomeSubtitle')}
            </p>
          </div>

          {/* Auth Card */}
          <Card>
            <CardHeader>
              <CardTitle>{t('authenticationTitle')}</CardTitle>
              <CardDescription>
                {t('authenticationDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="login" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="login">{t('loginTab')}</TabsTrigger>
                  <TabsTrigger value="register">{t('registerTab')}</TabsTrigger>
                </TabsList>

                {/* TAB LOGIN */}
                <TabsContent value="login">
                  {!requires2FA ? (
                    // Standard Login Form
                    <form onSubmit={handleLogin} className="space-y-4">
                      {/* Account Lockout Warning */}
                      {accountLocked && lockoutSecondsRemaining > 0 && (
                        <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
                          <h3 className="font-semibold text-destructive mb-2">{t('accountLockedTitle')}</h3>
                          <p className="text-sm text-muted-foreground mb-3">
                            {t('accountLockedMessage')}
                          </p>
                          <div className="text-center">
                            <div className="text-3xl font-bold text-destructive">
                              {Math.floor(lockoutSecondsRemaining / 60)}:{String(lockoutSecondsRemaining % 60).padStart(2, '0')}
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">{t('minutesRemaining')}</p>
                          </div>
                        </div>
                      )}

                      <div className="space-y-2">
                        <Label htmlFor="login-email">{t('email')}</Label>
                        <Input
                          id="login-email"
                          type="email"
                          placeholder={t('emailPlaceholder')}
                          value={loginEmail}
                          onChange={(e) => setLoginEmail(e.target.value)}
                          maxLength={254}
                          required
                          disabled={accountLocked}
                        />
                        {loginErrors.email && (
                          <p className="text-sm text-destructive">{loginErrors.email}</p>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="login-password">{t('password')}</Label>
                        <Input
                          id="login-password"
                          type="password"
                          autoComplete="current-password"
                          placeholder={t('passwordPlaceholder')}
                          value={loginPassword}
                          onChange={(e) => setLoginPassword(e.target.value)}
                          maxLength={100}
                          required
                          disabled={accountLocked}
                        />
                        {loginErrors.password && (
                          <p className="text-sm text-destructive">{loginErrors.password}</p>
                        )}
                      </div>

                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="remember-me"
                          checked={rememberMe}
                          onCheckedChange={(checked) => setRememberMe(checked as boolean)}
                          disabled={accountLocked}
                        />
                        <Label
                          htmlFor="remember-me"
                          className="text-sm font-normal cursor-pointer"
                        >
                          {t('rememberMe')}
                        </Label>
                      </div>

                      <Button type="submit" className="w-full" disabled={loginLoading || accountLocked}>
                        {loginLoading ? t('loginButtonLoading') : accountLocked ? t('accountLocked') : t('loginButton')}
                      </Button>

                      <div className="text-center">
                        <Link
                          href={`/${locale}/auth/forgot-password`}
                          className="text-sm text-primary hover:underline"
                        >
                          {t('forgotPasswordLink')}
                        </Link>
                      </div>
                    </form>
                  ) : (
                    // 2FA Verification Form
                    <form onSubmit={handle2FAVerify} className="space-y-4">
                      <div className="text-center mb-4">
                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-3">
                          <Shield className="h-8 w-8 text-primary" />
                        </div>
                        <h3 className="text-lg font-semibold mb-1">{t('twoFactorRequired')}</h3>
                        <p className="text-sm text-muted-foreground">
                          {t('twoFactorDescription')}
                        </p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="2fa-code">{t('verificationCodeLabel')}</Label>
                        <Input
                          id="2fa-code"
                          type="text"
                          inputMode="numeric"
                          maxLength={6}
                          placeholder={t('verificationCodePlaceholder')}
                          value={twoFactorCode}
                          onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, ''))}
                          className="text-center text-2xl tracking-widest"
                          required
                          autoFocus
                        />
                      </div>

                      <Button type="submit" className="w-full" disabled={loginLoading}>
                        {loginLoading ? t('verifyButtonLoading') : t('verifyButton')}
                      </Button>

                      <Button
                        type="button"
                        variant="outline"
                        className="w-full"
                        onClick={() => {
                          setRequires2FA(false)
                          setTempToken("")
                          setTwoFactorCode("")
                        }}
                      >
                        {t('backButton')}
                      </Button>
                    </form>
                  )}
                </TabsContent>

                {/* TAB REGISTER */}
                <TabsContent value="register">
                  <form onSubmit={handleRegister} className="space-y-4">
                    {/* Type de compte - RadioGroup avec icônes */}
                    <div className="space-y-3">
                      <Label>{t('accountType')}</Label>
                      <RadioGroup
                        value={role}
                        onValueChange={(value) => setRole(value as "citizen" | "business")}
                        className="grid grid-cols-2 gap-4"
                      >
                        <div>
                          <RadioGroupItem
                            value="citizen"
                            id="citizen"
                            className="peer sr-only"
                          />
                          <Label
                            htmlFor="citizen"
                            className="flex flex-col items-center justify-center rounded-lg border-2 border-muted bg-card p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/10 cursor-pointer transition-all"
                          >
                            <User className="mb-2 h-8 w-8" />
                            <span className="font-medium">{t('citizen')}</span>
                          </Label>
                        </div>
                        <div>
                          <RadioGroupItem
                            value="business"
                            id="business"
                            className="peer sr-only"
                          />
                          <Label
                            htmlFor="business"
                            className="flex flex-col items-center justify-center rounded-lg border-2 border-muted bg-card p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/10 cursor-pointer transition-all"
                          >
                            <Building2 className="mb-2 h-8 w-8" />
                            <span className="font-medium">{t('business')}</span>
                          </Label>
                        </div>
                      </RadioGroup>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="first-name">{t('firstName')}</Label>
                        <Input
                          id="first-name"
                          type="text"
                          placeholder={t('firstNamePlaceholder')}
                          value={firstName}
                          onChange={(e) => setFirstName(e.target.value)}
                          maxLength={50}
                          required
                        />
                        {registerErrors.first_name && (
                          <p className="text-sm text-destructive">{registerErrors.first_name}</p>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="last-name">{t('lastName')}</Label>
                        <Input
                          id="last-name"
                          type="text"
                          placeholder={t('lastNamePlaceholder')}
                          value={lastName}
                          onChange={(e) => setLastName(e.target.value)}
                          maxLength={50}
                          required
                        />
                        {registerErrors.last_name && (
                          <p className="text-sm text-destructive">{registerErrors.last_name}</p>
                        )}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="register-email">{t('email')}</Label>
                      <Input
                        id="register-email"
                        type="email"
                        placeholder={t('emailPlaceholder')}
                        value={registerEmail}
                        onChange={(e) => setRegisterEmail(e.target.value)}
                        maxLength={254}
                        required
                      />
                      {registerErrors.email && (
                        <p className="text-sm text-destructive">{registerErrors.email}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="phone">{t('phone')}</Label>
                      <Input
                        id="phone"
                        type="tel"
                        placeholder={t('phonePlaceholder')}
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        maxLength={9}
                        required
                      />
                      {registerErrors.phone && (
                        <p className="text-sm text-destructive">{registerErrors.phone}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="register-password">{t('password')}</Label>
                      <Input
                        id="register-password"
                        type="password"
                        autoComplete="new-password"
                        placeholder={t('passwordPlaceholder')}
                        value={registerPassword}
                        onChange={(e) => setRegisterPassword(e.target.value)}
                        maxLength={100}
                        required
                      />
                      {registerErrors.password && (
                        <p className="text-sm text-destructive">{registerErrors.password}</p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        {t('passwordRequirements')}
                      </p>
                    </div>

                    <Button type="submit" className="w-full" disabled={registerLoading}>
                      {registerLoading ? t('registerButtonLoading') : t('registerButton')}
                    </Button>
                  </form>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  )
}
